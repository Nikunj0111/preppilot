<div align="center">

# 📘 PrepPilot

### A focused JEE preparation workspace

Practice questions, take timed mock tests, track performance, plan revision, and keep your study progress in one place.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Database](https://img.shields.io/badge/Database-SQLite%20%7C%20PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Tests](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white)](https://pytest.org/)
[![Version](https://img.shields.io/badge/Version-2.0.0-informational)](VERSION)

**[Open the live demo](https://preppilot-rynuvkenttuwnmobmkvshz.streamlit.app/)**

</div>

---

## Overview

PrepPilot is a web-based study companion for students preparing for JEE. It combines question practice, exam-style mock tests, performance insights, revision planning, and study tracking in a single Streamlit application.

The project runs locally with SQLite and can use PostgreSQL when deployed. It is designed as a practical learning and portfolio project. It is not an official JEE platform and does not provide an official or complete question bank.

## Features

| Area | What it includes |
|---|---|
| **Accounts** | Account creation, PBKDF2-SHA256 password hashing, login-failure throttling, and session inactivity expiry |
| **Dashboard** | Study progress, available questions, mock-test totals, practice activity, and pending revision tasks |
| **Question bank** | Add MCQ and numerical questions, import/export CSV, filter by subject/chapter/difficulty, and manage private questions |
| **Practice** | Filtered practice sessions, instant feedback, explanations, and saved attempt history |
| **JEE mock tests** | Custom tests and a 75-question JEE Main-style template, timed attempts, question palette, mark-for-review, autosave, resume, and result analysis |
| **Performance** | Chapter accuracy, unanswered rate, mock-test trends, and subject comparisons |
| **Recommendations** | Suggested focus areas based on recorded performance |
| **Revision planner** | Manual revision tasks and performance-informed task suggestions |
| **Study tracker** | Daily study target, session logging, and a 30-day progress view |
| **Mistake notebook** | Review incorrect answers, add notes, and mark items resolved |
| **Bookmarks** | Save questions for later review |
| **Reports** | PDF progress report and CSV/JSON exports |
| **AI doubt solver** | Optional OpenAI-powered explanations, disabled unless an API key is configured |

> **Question-bank note:** The built-in bank contains 12 illustrative sample questions so a new account can explore the app. It is not a complete, official, or independently verified JEE question bank. Import material only when you have permission to use it, and verify answers before relying on them.

## Technology

- **Application:** Python, Streamlit
- **Data layer:** SQLAlchemy
- **Databases:** SQLite for local use; PostgreSQL for hosted deployments
- **Data and reports:** Pandas, ReportLab
- **Optional AI:** OpenAI API
- **Testing:** pytest
- **Deployment examples:** Streamlit Community Cloud, Neon PostgreSQL, Docker

## Quick start

### Requirements

- Python 3.10 or newer (Python 3.12 recommended)
- macOS, Windows, or Linux
- Internet access to install dependencies

### macOS / Linux

```bash
git clone https://github.com/YOUR_GITHUB_USERNAME/preppilot.git
cd preppilot
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Open the local address printed by Streamlit, usually `http://localhost:8501`, and create an account.

On macOS, you can also run `./start_mac.command` from the project folder.

### Windows

```powershell
git clone https://github.com/YOUR_GITHUB_USERNAME/preppilot.git
cd preppilot
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

Or run `start_windows.bat` from the project folder.

## Configuration

PrepPilot works without optional API credentials. Local development uses SQLite by default and creates `data/preppilot_v2.db`.

| Variable | Required | Purpose |
|---|---:|---|
| `PREPPILOT_DATA_DIR` | No | Directory for the local SQLite database; defaults to `./data` |
| `DATABASE_URL` | Hosted PostgreSQL only | SQLAlchemy database connection URL |
| `OPENAI_API_KEY` | No | Enables the optional AI doubt solver; API usage may incur charges |
| `OPENAI_MODEL` | No | OpenAI model name; defaults to `gpt-4o-mini` |

For local environment variables, copy `.env.example` to `.env` and edit it. Do not commit `.env`, `.streamlit/secrets.toml`, database files, or API keys. The app reads `DATABASE_URL` and `OPENAI_API_KEY` from environment variables or Streamlit secrets.

Example Streamlit secrets file (use placeholders only in source control):

```toml
DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require"
# OPENAI_API_KEY = "your-api-key"
# OPENAI_MODEL = "gpt-4o-mini"
```

## Deploying

For the current hosted demo, see the [deployment guide](docs/DEPLOYMENT.md). It covers Streamlit Community Cloud with Neon PostgreSQL, environment secrets, validation checks, and backup considerations.

A Dockerfile and a Render Blueprint example are also included. Review the hosting provider's current pricing, resource limits, database retention, region, and backup options before deploying. The included Render configuration uses paid plan identifiers and may create billable resources.

## Question-bank CSV format

Use **Download CSV template** in Question Bank to get a starter file.

Required columns:

```text
subject, chapter, difficulty, question_type, question_text, correct_answer
```

For MCQs, also include `option_a`, `option_b`, `option_c`, and `option_d`. Set `correct_answer` to `A`, `B`, `C`, or `D`. For numerical questions, use a numeric `correct_answer`; `numeric_tolerance` is optional.

Accepted values:

- Subjects: `Physics`, `Chemistry`, `Mathematics`
- Difficulty: `Easy`, `Medium`, `Hard`
- Question type: `MCQ`, `NUMERICAL`

## Mock-test behaviour

- Custom tests let you select subjects, chapters, difficulty, question count, and duration.
- The 75-question JEE Main-style mode requires at least 20 MCQs and 5 numerical questions per subject in the question bank.
- The standard mode uses a 180-minute timer and +4 / -1 / 0 marking.
- Answers and review flags are saved to the database. An in-progress attempt can be resumed after a refresh or a later login.
- The server-side deadline is stored. Keep the browser tab open during a test to see the countdown refresh; the attempt is submitted when the app next checks after the deadline.
- Submitted attempts are not editable through the app.

## Data, privacy, and limitations

- Local data is stored in `data/preppilot_v2.db`. Back it up before moving or replacing a local project folder.
- Hosted deployments should use managed PostgreSQL and provider-managed backups. Do not depend on ephemeral application storage for user data.
- The current account system does not include email verification, password reset, or account recovery.
- The optional AI feature sends the entered prompt and recent conversation context to OpenAI. Do not enter passwords, private records, or sensitive personal information.
- The project has automated tests, but those tests do not constitute a security audit or a guarantee of production readiness.
- Before inviting a wider audience, review authentication, privacy, data retention, abuse controls, backup restoration, accessibility, and applicable legal requirements.

## Development

Install development dependencies and run the test suite:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q .
```

The tests use a temporary SQLite database and do not modify your personal PrepPilot database.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow, [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the application structure, [PRIVACY.md](PRIVACY.md) for the project data-handling summary, and [GITHUB_SETUP.md](GITHUB_SETUP.md) for repository settings and release steps.

## Repository layout

```text
.
├── app.py                    # Streamlit entry point and navigation
├── database.py               # SQLAlchemy models, queries, and initialization
├── auth_ui.py                # Login and registration UI
├── security.py               # Password hashing and validation
├── mock_engine.py            # Mock-test scoring helpers
├── mock_ui.py                # Timed mock-test interface
├── question_bank_ui.py       # Question bank and CSV workflows
├── study_ui.py               # Practice, analytics, revision, and study tracking
├── reports_ui.py             # PDF and data exports
├── ai_tutor_ui.py            # Optional AI doubt solver
├── scripts/                  # Backup and legacy migration utilities
├── tests/                    # Automated tests
├── docs/                     # Architecture and deployment guides
└── .github/                  # CI, issue templates, and repository automation
```

## Roadmap

Potential next steps include:

- Add email verification and secure password recovery.
- Add a reviewed and properly licensed larger question bank.
- Expand automated tests for PostgreSQL and concurrent mock submissions.
- Add accessibility and mobile-layout checks.
- Add database schema migrations for future releases.

## License

No open-source license has been selected for this repository yet. All rights are reserved by default; public visibility does not grant permission to reuse, redistribute, or modify the source. Choose and add a license before inviting outside contributions or presenting the project as open source.

---

<div align="center">

Built as an independent JEE preparation project.

</div>
