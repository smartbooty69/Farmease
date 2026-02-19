from app.dashboard import *  # noqa: F401,F403


def main() -> None:
    """Start the desktop dashboard by importing the `app.dashboard` module.

    The `app.dashboard` module performs its UI startup at import-time (legacy
    behavior from the prototype). Importing it here triggers the same behavior
    when run as a console script: `farmease-dashboard`.
    """
    # import is idempotent; module-level code in `app.dashboard` starts the UI
    import app.dashboard as _dashboard  # noqa: F401
