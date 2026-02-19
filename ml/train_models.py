from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, precision_score, r2_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline

try:
    from tqdm import tqdm
except Exception:
    tqdm = None

try:
    from .ml_pipeline import build_feature_frame, load_dataset, make_supervised_data, prepare_dataframe
except ImportError:
    from ml_pipeline import build_feature_frame, load_dataset, make_supervised_data, prepare_dataframe


def select_candidate_models(candidates: dict[str, Any], model_family: str) -> dict[str, Any]:
    if model_family == "all":
        return candidates

    if model_family == "xgboost":
        if "xgboost" not in candidates:
            raise RuntimeError("XGBoost model requested, but xgboost is not available in this environment.")
        return {"xgboost": candidates["xgboost"]}

    raise ValueError(f"Unsupported model family: {model_family}")


def sanitize_metrics(report: dict[str, Any]) -> dict[str, Any]:
    def sanitize_value(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: sanitize_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [sanitize_value(item) for item in value]
        if isinstance(value, float) and not np.isfinite(value):
            return None
        return value

    return sanitize_value(report)


def build_validation_quality(train_y: pd.Series, valid_y: pd.Series) -> dict[str, Any]:
    train_classes = sorted(train_y.dropna().unique().tolist())
    valid_classes = sorted(valid_y.dropna().unique().tolist())
    return {
        "train_has_both_classes": len(train_classes) >= 2,
        "valid_has_both_classes": len(valid_classes) >= 2,
        "train_classes": train_classes,
        "valid_classes": valid_classes,
    }


def evaluate_relay_quality_gate(
    train_y: pd.Series,
    valid_y: pd.Series,
    min_class_count: int,
) -> tuple[bool, list[str], dict[str, Any]]:
    train_counts = train_y.value_counts(dropna=True).to_dict()
    valid_counts = valid_y.value_counts(dropna=True).to_dict()

    train_unique = sorted(train_y.dropna().unique().tolist())
    valid_unique = sorted(valid_y.dropna().unique().tolist())

    issues: list[str] = []

    if len(train_unique) < 2:
        issues.append("train split has a single class")
    if len(valid_unique) < 2:
        issues.append("validation split has a single class")

    for class_label in (0, 1):
        train_count = int(train_counts.get(class_label, 0))
        valid_count = int(valid_counts.get(class_label, 0))
        if train_count < min_class_count:
            issues.append(f"train class {class_label} count too low ({train_count} < {min_class_count})")
        if valid_count < min_class_count:
            issues.append(f"validation class {class_label} count too low ({valid_count} < {min_class_count})")

    summary = {
        "passed": len(issues) == 0,
        "min_class_count": int(min_class_count),
        "train_counts": {str(label): int(count) for label, count in train_counts.items()},
        "valid_counts": {str(label): int(count) for label, count in valid_counts.items()},
        "issues": issues,
    }

    return len(issues) == 0, issues, summary


def build_walk_forward_folds(
    total_rows: int,
    n_splits: int,
    min_train_rows: int = 80,
    min_valid_rows: int = 20,
) -> list[tuple[slice, slice]]:
    if total_rows < (min_train_rows + min_valid_rows):
        return []

    if n_splits < 2:
        return []

    folds: list[tuple[slice, slice]] = []
    remaining_rows = total_rows - min_train_rows
    step = max(min_valid_rows, remaining_rows // n_splits)
    train_end = min_train_rows

    while len(folds) < n_splits and (train_end + min_valid_rows) <= total_rows:
        valid_end = min(train_end + step, total_rows)
        if (valid_end - train_end) < min_valid_rows:
            break
        folds.append((slice(0, train_end), slice(train_end, valid_end)))
        train_end = valid_end

    return folds


def _mean_std(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "std": None}
    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
    }


def stability_adjusted_regression_loss(metrics: dict[str, Any]) -> float | None:
    mae_metrics = metrics.get("mae", {})
    mae_mean = mae_metrics.get("mean")
    if mae_mean is None:
        return None

    mae_std = mae_metrics.get("std") or 0.0
    return float(mae_mean) + (0.25 * float(mae_std))


def stability_adjusted_classification_score(metrics: dict[str, Any]) -> float | None:
    f1_metrics = metrics.get("f1", {})
    f1_mean = f1_metrics.get("mean")
    if f1_mean is None:
        return None

    f1_std = f1_metrics.get("std") or 0.0
    return float(f1_mean) - (0.10 * float(f1_std))


def run_walk_forward_regression(
    pipeline: Pipeline,
    features: pd.DataFrame,
    target: pd.Series,
    folds: list[tuple[slice, slice]],
) -> dict[str, Any]:
    by_fold: list[dict[str, Any]] = []
    maes: list[float] = []
    rmses: list[float] = []
    r2s: list[float] = []

    for idx, (train_slice, valid_slice) in enumerate(folds, start=1):
        fold_train_x = features.iloc[train_slice]
        fold_valid_x = features.iloc[valid_slice]
        fold_train_y = target.iloc[train_slice]
        fold_valid_y = target.iloc[valid_slice]

        model = clone(pipeline)
        model.fit(fold_train_x, fold_train_y)
        prediction = model.predict(fold_valid_x)

        fold_mae = float(mean_absolute_error(fold_valid_y, prediction))
        fold_rmse = float(np.sqrt(mean_squared_error(fold_valid_y, prediction)))
        fold_r2 = float(r2_score(fold_valid_y, prediction))

        maes.append(fold_mae)
        rmses.append(fold_rmse)
        r2s.append(fold_r2)

        by_fold.append(
            {
                "fold": idx,
                "train_rows": int(len(fold_train_x)),
                "valid_rows": int(len(fold_valid_x)),
                "mae": fold_mae,
                "rmse": fold_rmse,
                "r2": fold_r2,
            }
        )

    return {
        "folds_run": len(by_fold),
        "metrics": {
            "mae": _mean_std(maes),
            "rmse": _mean_std(rmses),
            "r2": _mean_std(r2s),
        },
        "by_fold": by_fold,
    }


def run_walk_forward_classification(
    pipeline: Pipeline,
    features: pd.DataFrame,
    target: pd.Series,
    folds: list[tuple[slice, slice]],
) -> dict[str, Any]:
    by_fold: list[dict[str, Any]] = []
    accuracies: list[float] = []
    precisions: list[float] = []
    recalls: list[float] = []
    f1s: list[float] = []
    aucs: list[float] = []
    skipped_folds = 0

    for idx, (train_slice, valid_slice) in enumerate(folds, start=1):
        fold_train_x = features.iloc[train_slice]
        fold_valid_x = features.iloc[valid_slice]
        fold_train_y = target.iloc[train_slice]
        fold_valid_y = target.iloc[valid_slice]

        if fold_train_y.nunique(dropna=True) < 2:
            skipped_folds += 1
            continue

        model = clone(pipeline)
        model.fit(fold_train_x, fold_train_y)
        prediction = model.predict(fold_valid_x)

        fold_entry: dict[str, Any] = {
            "fold": idx,
            "train_rows": int(len(fold_train_x)),
            "valid_rows": int(len(fold_valid_x)),
            "accuracy": float(accuracy_score(fold_valid_y, prediction)),
            "precision": float(precision_score(fold_valid_y, prediction, zero_division=0)),
            "recall": float(recall_score(fold_valid_y, prediction, zero_division=0)),
            "f1": float(f1_score(fold_valid_y, prediction, zero_division=0)),
        }

        accuracies.append(fold_entry["accuracy"])
        precisions.append(fold_entry["precision"])
        recalls.append(fold_entry["recall"])
        f1s.append(fold_entry["f1"])

        if fold_valid_y.nunique(dropna=True) > 1:
            try:
                probabilities = model.predict_proba(fold_valid_x)[:, 1]
                fold_auc = float(roc_auc_score(fold_valid_y, probabilities))
                fold_entry["roc_auc"] = fold_auc
                aucs.append(fold_auc)
            except Exception:
                pass

        by_fold.append(fold_entry)

    return {
        "folds_run": len(by_fold),
        "folds_skipped": skipped_folds,
        "metrics": {
            "accuracy": _mean_std(accuracies),
            "precision": _mean_std(precisions),
            "recall": _mean_std(recalls),
            "f1": _mean_std(f1s),
            "roc_auc": _mean_std(aucs),
        },
        "by_fold": by_fold,
    }


def build_regression_candidates(random_state: int, device: str) -> dict[str, Any]:
    candidates: dict[str, Any] = {
        "hist_gradient_boosting": HistGradientBoostingRegressor(
            learning_rate=0.05,
            max_depth=8,
            max_iter=400,
            min_samples_leaf=10,
            random_state=random_state,
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=500,
            max_depth=18,
            min_samples_leaf=3,
            random_state=random_state,
            n_jobs=-1,
        ),
    }

    try:
        from xgboost import XGBRegressor  # type: ignore

        xgb_params: dict[str, Any] = {
            "n_estimators": 700,
            "max_depth": 8,
            "learning_rate": 0.03,
            "subsample": 0.85,
            "colsample_bytree": 0.9,
            "objective": "reg:squarederror",
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
            "random_state": random_state,
            "n_jobs": -1,
            "tree_method": "hist",
        }

        if device in {"cuda", "auto"}:
            xgb_params["device"] = "cuda"

        candidates["xgboost"] = XGBRegressor(**xgb_params)
    except Exception:
        pass

    return candidates


def build_classification_candidates(random_state: int, device: str) -> dict[str, Any]:
    candidates: dict[str, Any] = {
        "hist_gradient_boosting": HistGradientBoostingClassifier(
            learning_rate=0.05,
            max_depth=8,
            max_iter=400,
            random_state=random_state,
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=500,
            max_depth=16,
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=random_state,
            n_jobs=-1,
        ),
    }

    try:
        from xgboost import XGBClassifier  # type: ignore

        xgb_params: dict[str, Any] = {
            "n_estimators": 700,
            "max_depth": 8,
            "learning_rate": 0.03,
            "subsample": 0.85,
            "colsample_bytree": 0.9,
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "random_state": random_state,
            "n_jobs": -1,
            "tree_method": "hist",
        }

        if device in {"cuda", "auto"}:
            xgb_params["device"] = "cuda"

        candidates["xgboost"] = XGBClassifier(**xgb_params)
    except Exception:
        pass

    return candidates


def fit_best_regressor(
    train_x: pd.DataFrame,
    train_y: pd.Series,
    valid_x: pd.DataFrame,
    valid_y: pd.Series,
    all_features: pd.DataFrame,
    all_target: pd.Series,
    walk_forward_folds: list[tuple[slice, slice]],
    random_state: int,
    device: str,
    model_family: str,
    show_progress: bool,
) -> tuple[str, Pipeline, dict[str, dict[str, Any]], str, list[str]]:
    candidate_models = build_regression_candidates(random_state=random_state, device=device)
    candidate_models = select_candidate_models(candidate_models, model_family=model_family)
    scores: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    best_name = ""
    best_pipeline: Pipeline | None = None
    best_selection_loss = float("inf")
    selection_mode = "holdout_mae"

    model_items = list(candidate_models.items())
    model_iterator = model_items
    if show_progress and tqdm is not None:
        model_iterator = tqdm(
            model_items,
            desc="Regressor search",
            unit="model",
            leave=False,
        )

    for model_name, model in model_iterator:
        pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("regressor", TransformedTargetRegressor(regressor=model, func=np.log1p, inverse_func=np.expm1)),
            ]
        )
        try:
            pipeline.fit(train_x, train_y)
            prediction = pipeline.predict(valid_x)
        except Exception as exc:
            warnings.append(f"Skipped regression model '{model_name}': {exc}")
            continue

        mae_score = float(mean_absolute_error(valid_y, prediction))
        rmse_score = float(np.sqrt(mean_squared_error(valid_y, prediction)))
        r2_value = float(r2_score(valid_y, prediction))

        metric_entry: dict[str, Any] = {"mae": mae_score, "rmse": rmse_score, "r2": r2_value}
        model_selection_loss = mae_score
        model_selection_mode = "holdout_mae"

        if walk_forward_folds:
            walk_forward = run_walk_forward_regression(
                pipeline=pipeline,
                features=all_features,
                target=all_target,
                folds=walk_forward_folds,
            )
            metric_entry["walk_forward"] = walk_forward.get("metrics", {})
            metric_entry["walk_forward_folds_run"] = int(walk_forward.get("folds_run", 0))

            if int(walk_forward.get("folds_run", 0)) >= 2:
                stable_loss = stability_adjusted_regression_loss(walk_forward.get("metrics", {}))
                if stable_loss is not None:
                    model_selection_loss = stable_loss
                    model_selection_mode = "walk_forward_stability"

        scores[model_name] = metric_entry

        if model_selection_loss < best_selection_loss:
            best_selection_loss = model_selection_loss
            selection_mode = model_selection_mode
            best_name = model_name
            best_pipeline = pipeline

    if best_pipeline is None:
        raise RuntimeError("No regression model could be trained.")

    return best_name, best_pipeline, scores, selection_mode, warnings


def fit_best_classifier(
    train_x: pd.DataFrame,
    train_y: pd.Series,
    valid_x: pd.DataFrame,
    valid_y: pd.Series,
    all_features: pd.DataFrame,
    all_target: pd.Series,
    walk_forward_folds: list[tuple[slice, slice]],
    random_state: int,
    device: str,
    model_family: str,
    show_progress: bool,
) -> tuple[str | None, Pipeline | None, dict[str, dict[str, Any]], str | None, str, list[str]]:
    warnings: list[str] = []
    unique_labels = sorted(train_y.dropna().unique().tolist())
    if len(unique_labels) < 2:
        reason = "Skipping relay_light classifier: target has only one class in training split."
        return None, None, {}, reason, "holdout_f1", warnings

    candidate_models = build_classification_candidates(random_state=random_state, device=device)
    candidate_models = select_candidate_models(candidate_models, model_family=model_family)
    scores: dict[str, dict[str, Any]] = {}
    best_name: str | None = None
    best_pipeline: Pipeline | None = None
    best_selection_score = -1.0
    selection_mode = "holdout_f1"

    model_items = list(candidate_models.items())
    model_iterator = model_items
    if show_progress and tqdm is not None:
        model_iterator = tqdm(
            model_items,
            desc="Classifier search",
            unit="model",
            leave=False,
        )

    for model_name, model in model_iterator:
        pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("classifier", model),
            ]
        )
        try:
            pipeline.fit(train_x, train_y)
            prediction = pipeline.predict(valid_x)
        except Exception as exc:
            warnings.append(f"Skipped classification model '{model_name}': {exc}")
            continue

        metric_entry: dict[str, Any] = {
            "accuracy": float(accuracy_score(valid_y, prediction)),
            "precision": float(precision_score(valid_y, prediction, zero_division=0)),
            "recall": float(recall_score(valid_y, prediction, zero_division=0)),
            "f1": float(f1_score(valid_y, prediction, zero_division=0)),
        }
        model_selection_score = float(metric_entry["f1"])
        model_selection_mode = "holdout_f1"

        if valid_y.nunique(dropna=True) > 1:
            try:
                probabilities = pipeline.predict_proba(valid_x)[:, 1]
                metric_entry["roc_auc"] = float(roc_auc_score(valid_y, probabilities))
            except Exception:
                pass

        if walk_forward_folds:
            walk_forward = run_walk_forward_classification(
                pipeline=pipeline,
                features=all_features,
                target=all_target,
                folds=walk_forward_folds,
            )
            metric_entry["walk_forward"] = walk_forward.get("metrics", {})
            metric_entry["walk_forward_folds_run"] = int(walk_forward.get("folds_run", 0))

            if int(walk_forward.get("folds_run", 0)) >= 2:
                stable_score = stability_adjusted_classification_score(walk_forward.get("metrics", {}))
                if stable_score is not None:
                    model_selection_score = stable_score
                    model_selection_mode = "walk_forward_stability"

        scores[model_name] = metric_entry

        if model_selection_score > best_selection_score:
            best_selection_score = model_selection_score
            selection_mode = model_selection_mode
            best_name = model_name
            best_pipeline = pipeline

    if best_pipeline is None:
        return None, None, {}, "No classification model could be trained.", "holdout_f1", warnings

    return best_name, best_pipeline, scores, None, selection_mode, warnings


def train_pipeline(
    dataset_path: Path,
    output_dir: Path,
    horizon_steps: int,
    train_ratio: float,
    random_state: int,
    device: str,
    model_family: str,
    show_progress: bool,
    walk_forward_splits: int,
    min_relay_class_count: int,
    strict_relay_quality: bool,
) -> dict[str, Any]:
    stage_bar = None
    if show_progress and tqdm is not None:
        stage_bar = tqdm(total=6, desc="Training pipeline", unit="stage")

    def advance_stage() -> None:
        if stage_bar is not None:
            stage_bar.update(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    advance_stage()

    raw_frame = load_dataset(dataset_path)
    clean_frame = prepare_dataframe(raw_frame)
    feature_frame = build_feature_frame(clean_frame)
    features, target_light, target_relay = make_supervised_data(feature_frame, horizon_steps=horizon_steps)
    advance_stage()

    minimum_rows = 40
    if len(features) < minimum_rows:
        raise ValueError(
            f"Need at least {minimum_rows} usable rows for stable training, found {len(features)}."
        )

    split_index = int(len(features) * train_ratio)
    split_index = max(split_index, 20)
    split_index = min(split_index, len(features) - 10)

    train_x = features.iloc[:split_index]
    valid_x = features.iloc[split_index:]
    train_y_light = target_light.iloc[:split_index]
    valid_y_light = target_light.iloc[split_index:]
    train_y_relay = target_relay.iloc[:split_index]
    valid_y_relay = target_relay.iloc[split_index:]
    relay_validation_quality = build_validation_quality(train_y_relay, valid_y_relay)
    relay_quality_ok, relay_quality_issues, relay_quality_gate = evaluate_relay_quality_gate(
        train_y=train_y_relay,
        valid_y=valid_y_relay,
        min_class_count=max(1, int(min_relay_class_count)),
    )

    walk_forward_folds = build_walk_forward_folds(
        total_rows=len(features),
        n_splits=walk_forward_splits,
        min_train_rows=max(80, int(len(features) * 0.25)),
        min_valid_rows=max(20, int(len(features) * 0.08)),
    )

    if strict_relay_quality and not relay_quality_ok:
        issue_text = "; ".join(relay_quality_issues)
        raise ValueError(
            "Relay classifier quality gate failed: "
            f"{issue_text}. Collect more ON/OFF transitions or lower --min-relay-class-count."
        )
    advance_stage()

    reg_name, reg_pipeline, regression_metrics, regression_selection_mode, regression_warnings = fit_best_regressor(
        train_x=train_x,
        train_y=train_y_light,
        valid_x=valid_x,
        valid_y=valid_y_light,
        all_features=features,
        all_target=target_light,
        walk_forward_folds=walk_forward_folds,
        random_state=random_state,
        device=device,
        model_family=model_family,
        show_progress=show_progress,
    )
    advance_stage()

    cls_name: str | None
    cls_pipeline: Pipeline | None
    classification_metrics: dict[str, dict[str, Any]]
    skip_reason: str | None
    classification_selection_mode: str
    classification_warnings: list[str]

    if relay_quality_ok:
        cls_name, cls_pipeline, classification_metrics, skip_reason, classification_selection_mode, classification_warnings = fit_best_classifier(
            train_x=train_x,
            train_y=train_y_relay,
            valid_x=valid_x,
            valid_y=valid_y_relay,
            all_features=features,
            all_target=target_relay,
            walk_forward_folds=walk_forward_folds,
            random_state=random_state,
            device=device,
            model_family=model_family,
            show_progress=show_progress,
        )
    else:
        cls_name, cls_pipeline, classification_metrics, skip_reason, classification_selection_mode, classification_warnings = (
            None,
            None,
            {},
            "Skipping relay_light classifier: quality gate failed.",
            "holdout_f1",
            [],
        )
    advance_stage()

    joblib.dump(reg_pipeline, output_dir / "light_forecast_model.joblib")
    if cls_pipeline is not None:
        joblib.dump(cls_pipeline, output_dir / "relay_light_model.joblib")

    feature_columns = list(features.columns)
    with (output_dir / "feature_columns.json").open("w", encoding="utf-8") as feature_file:
        json.dump(feature_columns, feature_file, indent=2)

    walk_forward_report: dict[str, Any] = {
        "requested_splits": walk_forward_splits,
        "generated_folds": len(walk_forward_folds),
    }

    if walk_forward_folds:
        walk_forward_report["regression"] = run_walk_forward_regression(
            pipeline=reg_pipeline,
            features=features,
            target=target_light,
            folds=walk_forward_folds,
        )

        if cls_pipeline is not None:
            walk_forward_report["classification"] = run_walk_forward_classification(
                pipeline=cls_pipeline,
                features=features,
                target=target_relay,
                folds=walk_forward_folds,
            )

    report: dict[str, Any] = {
        "dataset": str(dataset_path),
        "rows_total": int(len(clean_frame)),
        "rows_used": int(len(features)),
        "horizon_steps": horizon_steps,
        "train_rows": int(len(train_x)),
        "valid_rows": int(len(valid_x)),
        "requested_device": device,
        "model_family": model_family,
        "cuda_requested": device in {"cuda", "auto"},
        "cuda_used_by_best_model": "xgboost" in {reg_name, cls_name},
        "best_models": {
            "light_forecast": reg_name,
            "relay_light": cls_name,
        },
        "model_selection": {
            "light_forecast": regression_selection_mode,
            "relay_light": classification_selection_mode,
        },
        "metrics": {
            "regression": regression_metrics,
            "classification": classification_metrics,
        },
        "walk_forward": walk_forward_report,
        "validation_quality": {
            "relay_light": relay_validation_quality,
        },
        "class_distribution_relay_light": {
            "train": {
                str(label): int(count)
                for label, count in train_y_relay.value_counts(dropna=False).to_dict().items()
            },
            "valid": {
                str(label): int(count)
                for label, count in valid_y_relay.value_counts(dropna=False).to_dict().items()
            },
        },
        "quality_gate": {
            "relay_light": relay_quality_gate,
        },
        "notes": [
            "Validation split is time-ordered to avoid lookahead leakage.",
            "Best model prefers walk-forward stability when >=2 folds run; falls back to holdout MAE/F1.",
        ],
    }

    report["notes"].extend(regression_warnings)
    report["notes"].extend(classification_warnings)

    if not relay_validation_quality["valid_has_both_classes"]:
        report["notes"].append(
            "Classification validation set has a single class; accuracy/F1 can be non-informative. "
            "Collect more ON/OFF transitions in later time windows or adjust split horizon."
        )

    if not relay_quality_ok:
        report["notes"].append(
            "Relay classifier quality gate failed; classifier artifact was not produced for this run. "
            "Collect more balanced ON/OFF samples or adjust --min-relay-class-count."
        )

    if walk_forward_folds and "classification" in walk_forward_report:
        fold_quality = walk_forward_report["classification"]
        if fold_quality.get("folds_run", 0) == 0:
            report["notes"].append(
                "Walk-forward classification had zero runnable folds with two training classes. "
                "Collect more relay transitions for reliable classification evaluation."
            )

    if skip_reason:
        report["notes"].append(skip_reason)

    report = sanitize_metrics(report)

    with (output_dir / "training_report.json").open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2)

    advance_stage()

    if stage_bar is not None:
        stage_bar.close()

    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train greenhouse models with time-aware validation.")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data") / "greenhouse_training_data.csv",
        help="Path to the logged CSV dataset.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("models"),
        help="Directory where trained artifacts are written.",
    )
    parser.add_argument(
        "--horizon-steps",
        type=int,
        default=1,
        help="How many rows ahead to predict.",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="Time-ordered train split ratio (0,1).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed.",
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda", "auto"],
        default="cuda",
        help="Training device for XGBoost candidates (default: cuda).",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable terminal progress bars.",
    )
    parser.add_argument(
        "--model-family",
        choices=["all", "xgboost"],
        default="all",
        help="Candidate model family: all models or xgboost-only (GPU-first).",
    )
    parser.add_argument(
        "--walk-forward-splits",
        type=int,
        default=4,
        help="Number of expanding-window folds for walk-forward validation.",
    )
    parser.add_argument(
        "--min-relay-class-count",
        type=int,
        default=10,
        help="Minimum samples required per relay class (0/1) in both train and validation splits.",
    )
    parser.add_argument(
        "--strict-relay-quality",
        action="store_true",
        help="Fail training if relay quality gate conditions are not met.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not (0.6 <= args.train_ratio < 1.0):
        raise ValueError("--train-ratio should be between 0.6 and 1.0")

    report = train_pipeline(
        dataset_path=args.data,
        output_dir=args.out,
        horizon_steps=args.horizon_steps,
        train_ratio=args.train_ratio,
        random_state=args.seed,
        device=args.device,
        model_family=args.model_family,
        show_progress=not args.no_progress,
        walk_forward_splits=args.walk_forward_splits,
        min_relay_class_count=args.min_relay_class_count,
        strict_relay_quality=args.strict_relay_quality,
    )

    print("Training complete")
    print(json.dumps(report["best_models"], indent=2))
    print(f"Report: {args.out / 'training_report.json'}")

    relay_quality = report.get("validation_quality", {}).get("relay_light", {})
    if relay_quality and not relay_quality.get("valid_has_both_classes", True):
        print(
            "Warning: relay_light validation has one class only; classification metrics are limited."
        )

    relay_gate = report.get("quality_gate", {}).get("relay_light", {})
    if relay_gate and not relay_gate.get("passed", True):
        print("Warning: relay_light quality gate failed; classifier was skipped for this run.")


if __name__ == "__main__":
    main()
