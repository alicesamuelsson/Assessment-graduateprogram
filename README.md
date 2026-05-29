# Graduate Candidate Assessment App

A Streamlit MVP for collecting qualitative observations during graduate assessment nights. Assessors can submit written feedback for candidates across two moments, while admins can manage nights, candidates, assignments, results, and Excel exports.

## Features

- Assessor View with step-by-step assessment flow
- Admin View for assessment nights, candidates, and assignments
- Two fixed assessment moments: Group Exercise and Individual Interview
- Required qualitative fields and optional assessor name/comments
- SQLite persistence with automatic database initialization
- Demo data seeded on first run without overwriting existing data
- Results overview grouped by candidate and moment
- Completion overview showing missing feedback by moment
- Excel export with Overview, Raw Evaluations, By Candidate, and Comments Summary sheets
- Optional CSV export

Authentication is intentionally not included in this MVP. The code is organized so login and permissions can be added later.

## Project Structure

```text
app.py
db.py
schema.py
services/
  admin.py
  evaluations.py
  export.py
tests/
  test_services.py
requirements.txt
README.md
```

## Run Locally

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the app:

```bash
streamlit run app.py
```

The app creates `graduate_assessment.db` automatically in the project folder.

## Reset the Database

Stop the app, delete `graduate_assessment.db`, then start the app again:

```bash
streamlit run app.py
```

Demo data is inserted only when the database is empty.

## Run Tests

```bash
pytest
```

The tests cover database initialization, creating nights and candidates, assignments, evaluation saving, validation, and Excel export sheet generation.

## Deployment

### Streamlit Community Cloud

1. Push this project to a GitHub repository.
2. Go to [Streamlit Community Cloud](https://streamlit.io/cloud).
3. Create a new app from the repository.
4. Set the main file path to `app.py`.
5. Deploy.

Streamlit Cloud installs dependencies from `requirements.txt`. The SQLite database is local to the running app environment, so for serious production use you should move persistence to a managed database.

### Render or Similar Hosting

Use a Python web service with these settings:

- Build command: `pip install -r requirements.txt`
- Start command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

If the platform does not preserve local disk between deploys, use an external database before production use.

## Privacy and Production Notes

Assessment comments, candidate notes, and candidate contact details should be treated as sensitive. Before production use, add authentication, role-based access control, backups, data retention rules, audit logging where appropriate, and a durable database.

Do not hardcode secrets in the app. Keep environment-specific configuration outside the repository.

## Manual Test Checklist

1. Start app locally.
2. Confirm demo assessment night appears.
3. Add a new assessment night.
4. Add candidates.
5. Assign candidates to the assessment night.
6. Submit a Group Exercise evaluation.
7. Submit an Individual Interview evaluation.
8. Check admin results overview.
9. Confirm qualitative observations are displayed correctly.
10. Export Excel file.
11. Open Excel file and confirm sheets and columns are correct.
