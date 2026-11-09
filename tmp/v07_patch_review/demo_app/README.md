# Offline source-scanning fixture

This is a **non-running**, harmless source fixture for the default CLI target
`./demo_app`. `cursor.execute(` is present so DemoPlanner can find a genuine
source match. It is a parameterized query, **not** evidence of SQL injection.

No web server is started here. For `check_http_baseline`, supply a separately
authorized HTTP origin with `--origin` and an appropriate VERIFY-phase task.
