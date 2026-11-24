# Folio Campus

A responsive full-stack student planner built with Flask, Jinja and SQLite. The study desk opens with a private sample workspace containing three courses, assignments and a recurring timetable. Students can add assignments, track completion and register to save their workspace across devices. Course enrollment and class times are seeded sample data.

## Run locally

Use Python 3.12 and run these commands from the repository root.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
waitress-serve --listen=127.0.0.1:8080 --call app:create_app
```

Open http://localhost:8080. On Windows activate the environment with `.venv\Scripts\activate`.

The server stores the database and cookie-signing key in the ignored instance directory. Preserve this directory across restarts. Passwords use Werkzeug password hashing. State-changing forms check session-bound CSRF tokens and assignment updates check ownership.
