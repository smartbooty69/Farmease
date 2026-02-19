# FARMEASE Frontend Theme

This file documents the new frontend theme CSS and how to include it in templates.

Files added:
- app/static/css/farmease-theme.css — CSS custom properties, gradients, and a few utility classes.

Quick include (example):

```html
<link rel="stylesheet" href="/static/css/farmease-theme.css">
```

Suggested usage for the dashboard:

- Background: `--cream-light` (page background)
- Sidebar: `.sidebar` (uses `--deep-teal`)
- Cards: `.card` (soft card gradient)
- Primary actions: `.btn-primary` or `.btn-accent`
- Status indicators: `.status-ok` / `.status-alert`

If you want, I can:
- Inject the `<link>` into your dashboard template(s).
- Add a smaller CSS import for only variables (no helpers) for other services.
