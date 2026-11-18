# PrepPilot

A JEE preparation workspace built with Streamlit, SQLAlchemy and SQLite/PostgreSQL. This is a fresh replacement for the earlier PrepPilot prototype. It uses a new local database file named `data/preppilot_v2.db`; it does **not** overwrite or migrate the old `preppilot.db`.

## Included modules

- **Accounts:** account creation, PBKDF2-SHA256 password hashing, persistent login-failure throttling and inactivity expiry.
- **Dashboard:** question-bank count, mock/practice totals, daily study progress, pending revisions and recent results.
- **Question bank:** manual MCQ/numerical question entry, CSV import/export, filters, preview and deletion of your own questions. Your imported questions are private to your account. Seed questions are shared read-only examples.
- **Practice:** subject/chapter/difficulty filters, MCQ and numerical answers, instant feedback, explanations and saved history.
- **JEE mock tests:** custom tests and a 75-question JEE Main template (20 MCQ + 5 numerical per subject), 3-hour timer, question palette, section filter, previous/next navigation, mark for review, answer autosave to the database, resume after refresh/re-login, automatic timeout submission, +4/−1/0 marking, subject analysis and question review.
- **Performance:** chapter-level accuracy, unanswered rate, mock score trend and subject comparison.
- **Recommendations:** prioritisation based on recorded performance.
- **Revision planner:** manual tasks, performance-based smart plans, completion/reopen/delete actions.
- **Study tracker:** daily target, study-session log and 30-day chart.
- **Mistake notebook:** incorrect practice and mock answers are collected for review; add notes and mark them resolved.
- **Bookmarks:** collect questions for later revision.
- **Reports:** PDF progress report, CSV exports and JSON export of progress, revision tasks, mistake notes and bookmarks.
- **AI doubt solver:** optional OpenAI API integration. It is disabled unless a key is configured. API usage may cost money.

## Requirements

- Python 3.10 or newer (Python 3.12 is recommended)
- macOS, Windows or Linux
- Internet connection only for installing packages and using the optional AI feature

## Run locally on macOS

Open Terminal in the project folder and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Or double-click `start_mac.command` to create the virtual environment, install dependencies and launch the app. The first run needs an internet connection to install packages. Open the local URL printed by Streamlit, usually `http://localhost:8501`, then create your account.

### Optional AI doubt solver

Set the API key in the same Terminal window before starting the app:

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-4o-mini"
streamlit run app.py
```

Do not commit API keys or put them in source code. The AI page sends prompts to OpenAI and may incur usage charges.

## Question bank CSV

Use **Download CSV template** in Question Bank. Required columns:

`subject, chapter, difficulty, question_type, question_text, correct_answer`

For MCQ, also provide `option_a, option_b, option_c, option_d`; `correct_answer` must be A/B/C/D. For NUMERICAL, `correct_answer` must be a number and `numeric_tolerance` is optional. Subjects are `Physics`, `Chemistry`, `Mathematics`; difficulty is `Easy`, `Medium`, `Hard`; question type is `MCQ` or `NUMERICAL`.

Only import questions you have permission to use. Check every answer and explanation before relying on it. The small built-in set is illustrative sample content, not a complete or officially verified JEE question bank.

## Mock-test behaviour

- Custom tests let you choose subjects, chapters, difficulty, question count and duration.
- JEE Main 75 mode requires at least 20 MCQs and 5 numerical questions per subject from the question bank. It uses a 180-minute timer and +4/−1/0 scoring. If your bank does not contain enough questions, the app explains which quota is missing. Use Custom mode until your bank is large enough.
- Answers and mark-for-review flags are saved in the database. An in-progress test can be resumed after a page refresh or a new login.
- The timer is checked by the server on each app refresh; the app submits when the deadline has passed. Keep the browser tab open during an exam so the countdown refreshes. The server deadline remains stored even if the browser closes.
- A submitted attempt is immutable in the UI and is saved once. A repeated submit request returns the already-saved result.

## Database and backups

Local development uses SQLite at `data/preppilot_v2.db`. The earlier database is left untouched. Keep the project folder private and back up the database regularly.

Create a consistent SQLite backup:

```bash
python scripts/backup_sqlite.py
```

For PostgreSQL deployments, use your provider's automated backups and `pg_dump`. Do not rely on a container's local filesystem for persistent production data.

## Deploy with Docker

Build and run locally:

```bash
docker build -t preppilot .
docker run --rm -p 8501:8501 -e PORT=8501 -v "$PWD/data:/app/data" preppilot
```

For a hosted deployment, use a managed PostgreSQL database and set `DATABASE_URL` to a PostgreSQL connection string. `render.yaml` is included as a starting point for Render Blueprint deployment. Review the selected hosting plan, database storage, costs, region and backup settings before creating paid resources.

## Free cloud deployment (Streamlit Community Cloud + Neon)

1. Push the contents of this project folder to a GitHub repository. Keep `.env`, `.streamlit/secrets.toml`, database files and passwords out of Git.
2. Create a PostgreSQL project on Neon and copy its pooled connection string from **Connect**. Keep the full URL private.
3. Deploy `app.py` from that GitHub repository on Streamlit Community Cloud.
4. In the app deployment's **Advanced settings → Secrets**, add:

   ```toml
   DATABASE_URL = "paste-your-Neon-pooled-connection-string-here"
   ```

5. Optionally add `OPENAI_API_KEY = "your-key"` to the same Secrets panel to enable the AI doubt solver. API usage may cost money.
6. Choose Python 3.12 in Advanced settings, deploy, then test account creation, login, question import, practice, mock autosave and report export.

The database layer reads `DATABASE_URL` from Streamlit secrets or the host environment. Cloud data is stored in PostgreSQL rather than the app's temporary local filesystem. The free hosting tiers have usage limits and are suitable for a personal project or prototype, not a guaranteed production service. Keep separate backups of important data and do not invite users to enter sensitive information.

## Security and production deployment checklist

This project includes parameterised ORM queries, password hashing, login throttling, user-scoped private questions and user-owned records, session inactivity expiry, Streamlit XSRF protection, non-root Docker execution and PostgreSQL support. However, a code package cannot be certified as production-ready without testing in the actual deployment environment.

Before inviting real users:

1. Deploy behind HTTPS and use a managed PostgreSQL database.
2. Set database credentials and API keys as hosting secrets, never in Git.
3. Configure automated database backups and test a restore.
4. Set sensible hosting limits, monitoring and alerting.
5. Test concurrent logins, concurrent mock submissions, large CSV imports and network interruptions.
6. Review privacy terms, retention, account recovery and applicable data-protection requirements.
7. Run the automated tests and perform a manual end-to-end test on the hosted URL.
8. Add an email verification and password-reset flow before treating it as a public multi-user service. The current local account system has no email recovery.

Streamlit is a rapid application framework, not a full custom identity platform. For a high-traffic commercial service, consider moving authentication to a dedicated identity provider and separating the API/backend from the UI.

## Run tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

The test suite uses an isolated temporary SQLite database and does not touch your local PrepPilot data.

## Replace your old project

1. Download and extract the new project ZIP.
2. Keep the old project folder and old database as a backup.
3. Open the extracted `PrepPilot_Production` folder in VS Code.
4. Follow the local install steps above.
5. Create a new account and import your question CSV.
6. Verify the features before deleting or archiving anything from the old project.

The new build starts with a separate database so the old data remains untouched. If you want to migrate the previous prototype's data, first make a copy of the old `preppilot.db`, then run this from the new project folder:

```bash
python scripts/migrate_legacy_sqlite.py "/full/path/to/old/preppilot.db"
```

Type `YES` when prompted. The script opens the old database read-only, converts the old PBKDF2 password-hash format without needing plaintext passwords, and imports users, questions, mock history, practice history and revision tasks. It refuses to import into a target database that already contains user data. You can add `--yes` to skip the confirmation prompt. Check that the new accounts and records work before archiving the old database.
