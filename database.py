"""PrepPilot data layer. Supports SQLite locally and PostgreSQL in deployment."""
from __future__ import annotations

import json
import os
import secrets
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, create_engine, func, select, update, event
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker
from sqlalchemy.pool import StaticPool


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("PREPPILOT_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
def _configured_database_url() -> str:
    """Read DATABASE_URL from the host environment or Streamlit secrets."""
    value = os.getenv("DATABASE_URL", "").strip()
    if not value:
        try:
            import streamlit as st
            value = str(st.secrets.get("DATABASE_URL", "")).strip()
        except Exception:
            value = ""
    return value or f"sqlite:///{DATA_DIR / 'preppilot_v2.db'}"


DATABASE_URL = _configured_database_url()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

_engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    if DATABASE_URL.endswith(":memory:"):
        _engine_kwargs["poolclass"] = StaticPool
engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    username: Mapped[str] = mapped_column(String(40), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    window_started: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Question(Base):
    __tablename__ = "questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    code: Mapped[str] = mapped_column(String(80), default=lambda: secrets.token_hex(8), index=True)
    subject: Mapped[str] = mapped_column(String(30), index=True)
    chapter: Mapped[str] = mapped_column(String(120), default="General", index=True)
    topic: Mapped[str] = mapped_column(String(120), default="General")
    difficulty: Mapped[str] = mapped_column(String(20), default="Medium")
    question_type: Mapped[str] = mapped_column(String(20), default="MCQ")
    question_text: Mapped[str] = mapped_column(Text)
    options_json: Mapped[str] = mapped_column(Text, default="{}")
    correct_answer: Mapped[str] = mapped_column(String(100))
    numeric_tolerance: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[str] = mapped_column(Text, default="")
    exam: Mapped[str] = mapped_column(String(30), default="JEE Main")
    source: Mapped[str] = mapped_column(String(160), default="User added")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MockAttempt(Base):
    __tablename__ = "mock_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="JEE Mock Test")
    mode: Mapped[str] = mapped_column(String(30), default="Custom")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    deadline_at: Mapped[datetime] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float, default=0)
    max_score: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    incorrect: Mapped[int] = mapped_column(Integer, default=0)
    unanswered: Mapped[int] = mapped_column(Integer, default=0)
    accuracy: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", index=True)
    questions: Mapped[list["AttemptQuestion"]] = relationship(back_populates="attempt", cascade="all, delete-orphan", order_by="AttemptQuestion.order_index")


class AttemptQuestion(Base):
    __tablename__ = "attempt_questions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("mock_attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[str] = mapped_column(Text)
    selected_answer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    visited: Mapped[bool] = mapped_column(Boolean, default=False)
    marked_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)
    attempt: Mapped[MockAttempt] = relationship(back_populates="questions")
    __table_args__ = (UniqueConstraint("attempt_id", "order_index", name="uq_attempt_question_order"),)


class PracticeAttempt(Base):
    __tablename__ = "practice_attempts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    snapshot_json: Mapped[str] = mapped_column(Text)
    selected_answer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    time_spent_seconds: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class RevisionTask(Base):
    __tablename__ = "revision_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    subject: Mapped[str] = mapped_column(String(30))
    topic: Mapped[str] = mapped_column(String(120))
    task: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="Pending", index=True)
    source: Mapped[str] = mapped_column(String(30), default="Manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StudyLog(Base):
    __tablename__ = "study_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    study_date: Mapped[date] = mapped_column(Date, index=True)
    subject: Mapped[str] = mapped_column(String(30))
    minutes: Mapped[int] = mapped_column(Integer)
    activity: Mapped[str] = mapped_column(String(120), default="Self-study")
    notes: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Bookmark(Base):
    __tablename__ = "bookmarks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_user_bookmark"),)


class MistakeNote(Base):
    __tablename__ = "mistake_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int | None] = mapped_column(ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    snapshot_json: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(String(1500), default="")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "question_id", name="uq_user_mistake_question"),)


class UserSetting(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    daily_target_minutes: Mapped[int] = mapped_column(Integer, default=240)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


Index("ix_attempt_user_started", MockAttempt.user_id, MockAttempt.started_at)
Index("ix_attempt_question_attempt", AttemptQuestion.attempt_id, AttemptQuestion.order_index)


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _question_dict(q: Question) -> dict[str, Any]:
    return {
        "id": q.id, "owner_id": q.owner_id, "is_public": q.is_public, "code": q.code,
        "subject": q.subject, "chapter": q.chapter, "topic": q.topic,
        "difficulty": q.difficulty, "question_type": q.question_type,
        "question_text": q.question_text, "options": json.loads(q.options_json or "{}"),
        "correct_answer": q.correct_answer, "numeric_tolerance": q.numeric_tolerance,
        "explanation": q.explanation, "exam": q.exam, "source": q.source,
        "year": q.year, "tags": q.tags, "created_at": q.created_at.isoformat() if q.created_at else ""
    }


def question_snapshot(q: Question | dict[str, Any]) -> dict[str, Any]:
    if isinstance(q, Question):
        return _question_dict(q)
    return {k: v for k, v in q.items() if k not in {"owner_id", "is_public", "created_at"}}


def init_db() -> None:
    Base.metadata.create_all(engine)
    with session_scope() as db:
        if db.scalar(select(func.count(Question.id))) == 0:
            samples = [
                ("Physics", "Kinematics", "Easy", "MCQ", "A body starts from rest and moves with constant acceleration 2 m/s². Its speed after 5 s is:", {"A":"5 m/s","B":"10 m/s","C":"15 m/s","D":"20 m/s"}, "B", "Use v = u + at = 0 + 2 × 5 = 10 m/s."),
                ("Physics", "Laws of Motion", "Easy", "MCQ", "A 2 kg object experiences a net force of 10 N. Its acceleration is:", {"A":"2 m/s²","B":"5 m/s²","C":"10 m/s²","D":"20 m/s²"}, "B", "Newton's second law gives a = F/m = 10/2 = 5 m/s²."),
                ("Physics", "Work, Energy and Power", "Medium", "MCQ", "A force of 5 N moves an object 4 m in its direction. Work done is:", {"A":"5 J","B":"9 J","C":"20 J","D":"25 J"}, "C", "W = Fs cos 0° = 5 × 4 = 20 J."),
                ("Physics", "Current Electricity", "Medium", "NUMERICAL", "A 6 Ω resistor is connected across 12 V. Find the current in amperes.", {}, "2", "Ohm's law: I = V/R = 12/6 = 2 A."),
                ("Chemistry", "Mole Concept", "Easy", "MCQ", "How many moles are present in 18 g of water? (Molar mass = 18 g mol⁻¹)", {"A":"0.5","B":"1","C":"2","D":"18"}, "B", "Moles = mass / molar mass = 18/18 = 1."),
                ("Chemistry", "Atomic Structure", "Medium", "MCQ", "The maximum number of electrons in the n = 2 shell is:", {"A":"2","B":"8","C":"18","D":"32"}, "B", "Maximum electrons in a shell = 2n² = 8."),
                ("Chemistry", "Chemical Bonding", "Easy", "MCQ", "Which type of bond involves sharing of electron pairs?", {"A":"Ionic","B":"Covalent","C":"Metallic","D":"Hydrogen"}, "B", "A covalent bond is formed by sharing electron pairs."),
                ("Chemistry", "Chemical Equilibrium", "Medium", "NUMERICAL", "For a reaction at equilibrium, if the forward and reverse rates are both 0.25 mol L⁻¹ s⁻¹, find their sum.", {}, "0.5", "The requested sum is 0.25 + 0.25 = 0.5."),
                ("Mathematics", "Quadratic Equations", "Easy", "MCQ", "The sum of the roots of x² - 5x + 6 = 0 is:", {"A":"2","B":"3","C":"5","D":"6"}, "C", "For ax² + bx + c = 0, sum of roots = -b/a = 5."),
                ("Mathematics", "Straight Lines", "Medium", "MCQ", "The slope of the line 2x + 3y - 6 = 0 is:", {"A":"2/3","B":"-2/3","C":"3/2","D":"-3/2"}, "B", "Write y = (-2/3)x + 2, so the slope is -2/3."),
                ("Mathematics", "Limits", "Medium", "MCQ", "Evaluate lim(x→0) sin(3x)/x.", {"A":"0","B":"1","C":"3","D":"Does not exist"}, "C", "Using lim(u→0) sin u/u = 1, the limit is 3."),
                ("Mathematics", "Sequences and Series", "Easy", "NUMERICAL", "Find the 5th term of the AP 2, 5, 8, ...", {}, "14", "a₅ = a + 4d = 2 + 4×3 = 14."),
            ]
            for subject, chapter, difficulty, qtype, text, options, answer, explanation in samples:
                db.add(Question(
                    owner_id=None, is_public=True, subject=subject, chapter=chapter,
                    topic=chapter, difficulty=difficulty, question_type=qtype,
                    question_text=text, options_json=json.dumps(options),
                    correct_answer=answer, explanation=explanation,
                    exam="JEE Main", source="PrepPilot sample", tags="sample"
                ))


def create_user(username: str, display_name: str, password_hash: str) -> tuple[dict | None, str | None]:
    username = username.strip().lower()
    try:
        with session_scope() as db:
            if db.scalar(select(User.id).where(User.username == username)):
                return None, "That username is already registered."
            user = User(username=username, display_name=display_name.strip(), password_hash=password_hash)
            db.add(user)
            db.flush()
            db.add(UserSetting(user_id=user.id))
            return {"id": user.id, "username": user.username, "display_name": user.display_name}, None
    except IntegrityError:
        return None, "That username is already registered."


def get_user_by_username(username: str) -> dict | None:
    with session_scope() as db:
        user = db.scalar(select(User).where(User.username == username.strip().lower(), User.is_active.is_(True)))
        if not user:
            return None
        return {"id": user.id, "username": user.username, "display_name": user.display_name, "password_hash": user.password_hash}


def login_lock_status(username: str) -> datetime | None:
    with session_scope() as db:
        row = db.get(LoginAttempt, username.strip().lower())
        if row and row.locked_until and row.locked_until > utcnow():
            return row.locked_until
        return None


def record_login_failure(username: str) -> None:
    key = username.strip().lower()
    now = utcnow()
    with session_scope() as db:
        row = db.get(LoginAttempt, key)
        if not row:
            row = LoginAttempt(username=key, failures=0, window_started=now)
            db.add(row)
        if now - row.window_started > timedelta(minutes=15):
            row.failures = 0
            row.window_started = now
        row.failures += 1
        if row.failures >= 6:
            row.locked_until = now + timedelta(minutes=15)


def clear_login_failures(username: str) -> None:
    with session_scope() as db:
        row = db.get(LoginAttempt, username.strip().lower())
        if row:
            db.delete(row)


def list_questions(user_id: int, subject: str | None = None, chapter: str | None = None,
                   difficulty: str | None = None, question_type: str | None = None,
                   search: str = "", limit: int = 1000) -> list[dict]:
    with session_scope() as db:
        stmt = select(Question).where(Question.is_active.is_(True)).where(
            (Question.is_public.is_(True)) | (Question.owner_id == user_id)
        )
        if subject and subject != "All": stmt = stmt.where(Question.subject == subject)
        if chapter and chapter != "All": stmt = stmt.where(Question.chapter == chapter)
        if difficulty and difficulty != "All": stmt = stmt.where(Question.difficulty == difficulty)
        if question_type and question_type != "All": stmt = stmt.where(Question.question_type == question_type)
        if search.strip():
            like = f"%{search.strip()}%"
            stmt = stmt.where((Question.question_text.ilike(like)) | (Question.chapter.ilike(like)) | (Question.tags.ilike(like)))
        rows = db.scalars(stmt.order_by(Question.subject, Question.chapter, Question.id).limit(limit)).all()
        return [_question_dict(q) for q in rows]


def add_question(user_id: int, data: dict) -> int:
    with session_scope() as db:
        supplied_code = str(data.get("code") or "").strip()
        if supplied_code and db.scalar(select(Question.id).where(Question.owner_id == user_id, Question.code == supplied_code)):
            raise ValueError(f"Question code '{supplied_code}' already exists in your bank.")
        q = Question(owner_id=user_id, is_public=False, code=supplied_code or secrets.token_hex(8),
                     subject=data["subject"], chapter=data["chapter"], topic=data.get("topic") or data["chapter"],
                     difficulty=data["difficulty"], question_type=data["question_type"],
                     question_text=data["question_text"], options_json=json.dumps(data.get("options", {})),
                     correct_answer=str(data["correct_answer"]).strip(), numeric_tolerance=float(data.get("numeric_tolerance", 0)),
                     explanation=data.get("explanation", ""), exam=data.get("exam", "JEE Main"),
                     source=data.get("source", "User added"), year=data.get("year"), tags=data.get("tags", ""))
        db.add(q)
        db.flush()
        return q.id


def bulk_add_questions(user_id: int, items: list[dict]) -> tuple[int, list[str]]:
    added, errors = 0, []
    for idx, item in enumerate(items, start=2):
        try:
            add_question(user_id, item)
            added += 1
        except Exception as exc:
            errors.append(f"Row {idx}: {str(exc)[:180]}")
    return added, errors


def delete_question(user_id: int, question_id: int) -> bool:
    with session_scope() as db:
        q = db.scalar(select(Question).where(Question.id == question_id, Question.owner_id == user_id))
        if not q:
            return False
        q.is_active = False
        return True


def get_question_by_id(user_id: int, question_id: int) -> dict | None:
    with session_scope() as db:
        q = db.scalar(select(Question).where(Question.id == question_id, Question.is_active.is_(True),
                                               (Question.is_public.is_(True)) | (Question.owner_id == user_id)))
        return _question_dict(q) if q else None


def _matches_answer(question: dict, answer: str | None) -> bool:
    if answer is None or not str(answer).strip():
        return False
    correct = str(question.get("correct_answer", "")).strip()
    if question.get("question_type") == "NUMERICAL":
        try:
            return abs(float(str(answer).strip()) - float(correct)) <= float(question.get("numeric_tolerance", 0.0) or 0.0)
        except (TypeError, ValueError):
            return False
    return str(answer).strip().upper() == correct.upper()


def start_mock(user_id: int, title: str, mode: str, duration_minutes: int,
               subjects: list[str], chapters: list[str] | None = None,
               difficulties: list[str] | None = None, count: int = 30) -> tuple[int | None, str | None]:
    with session_scope() as db:
        base = select(Question).where(Question.is_active.is_(True)).where(
            (Question.is_public.is_(True)) | (Question.owner_id == user_id)
        ).where(Question.subject.in_(subjects))
        if chapters: base = base.where(Question.chapter.in_(chapters))
        if difficulties: base = base.where(Question.difficulty.in_(difficulties))
        chosen: list[Question] = []
        if mode == "JEE Main 75":
            for subject in ["Physics", "Chemistry", "Mathematics"]:
                for qtype, quota in [("MCQ", 20), ("NUMERICAL", 5)]:
                    rows = db.scalars(base.where(Question.subject == subject, Question.question_type == qtype).order_by(func.random()).limit(quota)).all()
                    if len(rows) < quota:
                        return None, f"Standard JEE Main mode needs {quota} {qtype.lower()} questions for {subject}; only {len(rows)} available with these filters. Add more questions or use Custom mode."
                    chosen.extend(rows)
            title = title or "JEE Main Full Mock (75 Questions)"
        else:
            rows = db.scalars(base.order_by(func.random()).limit(int(count))).all()
            if len(rows) < int(count):
                return None, f"Only {len(rows)} questions match your filters. Reduce the test size or add more questions."
            chosen = list(rows)
        # Mix subjects while preserving a random order.
        import random
        random.shuffle(chosen)
        now = utcnow()
        attempt = MockAttempt(user_id=user_id, title=title[:120], mode=mode,
                              started_at=now, deadline_at=now + timedelta(minutes=int(duration_minutes)),
                              duration_seconds=int(duration_minutes) * 60,
                              max_score=len(chosen) * 4, status="in_progress")
        db.add(attempt)
        db.flush()
        for index, q in enumerate(chosen):
            db.add(AttemptQuestion(attempt_id=attempt.id, question_id=q.id, order_index=index,
                                   snapshot_json=json.dumps(_question_dict(q)), visited=False,
                                   marked_for_review=False, time_spent_seconds=0))
        db.flush()
        return attempt.id, None


def get_attempt(user_id: int, attempt_id: int) -> dict | None:
    with session_scope() as db:
        a = db.scalar(select(MockAttempt).where(MockAttempt.id == attempt_id, MockAttempt.user_id == user_id))
        if not a: return None
        return _attempt_dict(a)


def get_active_attempt(user_id: int) -> dict | None:
    with session_scope() as db:
        a = db.scalar(select(MockAttempt).where(MockAttempt.user_id == user_id, MockAttempt.status == "in_progress").order_by(MockAttempt.started_at.desc()))
        return _attempt_dict(a) if a else None


def _attempt_dict(a: MockAttempt) -> dict:
    return {
        "id": a.id, "title": a.title, "mode": a.mode, "started_at": a.started_at,
        "deadline_at": a.deadline_at, "submitted_at": a.submitted_at,
        "duration_seconds": a.duration_seconds, "score": a.score, "max_score": a.max_score,
        "correct": a.correct, "incorrect": a.incorrect, "unanswered": a.unanswered,
        "accuracy": a.accuracy, "status": a.status,
        "questions": [{"id": aq.id, "question_id": aq.question_id, "order_index": aq.order_index,
                       "question": json.loads(aq.snapshot_json), "selected_answer": aq.selected_answer,
                       "visited": aq.visited, "marked_for_review": aq.marked_for_review,
                       "time_spent_seconds": aq.time_spent_seconds} for aq in a.questions]
    }


def save_mock_answer(user_id: int, attempt_id: int, attempt_question_id: int, answer: str | None) -> None:
    with session_scope() as db:
        aq = db.scalar(select(AttemptQuestion).join(MockAttempt).where(
            AttemptQuestion.id == attempt_question_id, MockAttempt.id == attempt_id,
            MockAttempt.user_id == user_id, MockAttempt.status == "in_progress"))
        if aq:
            aq.selected_answer = str(answer).strip() if answer is not None and str(answer).strip() else None
            aq.visited = True


def set_question_flag(user_id: int, attempt_id: int, attempt_question_id: int,
                      visited: bool | None = None, marked: bool | None = None) -> None:
    with session_scope() as db:
        aq = db.scalar(select(AttemptQuestion).join(MockAttempt).where(
            AttemptQuestion.id == attempt_question_id, MockAttempt.id == attempt_id,
            MockAttempt.user_id == user_id, MockAttempt.status == "in_progress"))
        if aq:
            if visited is not None: aq.visited = visited
            if marked is not None: aq.marked_for_review = marked


def add_question_time(user_id: int, attempt_id: int, attempt_question_id: int, seconds: int) -> None:
    if seconds <= 0: return
    with session_scope() as db:
        aq = db.scalar(select(AttemptQuestion).join(MockAttempt).where(
            AttemptQuestion.id == attempt_question_id, MockAttempt.id == attempt_id,
            MockAttempt.user_id == user_id, MockAttempt.status == "in_progress"))
        if aq: aq.time_spent_seconds = min(86400, aq.time_spent_seconds + int(seconds))


def submit_mock(user_id: int, attempt_id: int, force: bool = False) -> dict | None:
    with session_scope() as db:
        a = db.scalar(select(MockAttempt).where(MockAttempt.id == attempt_id, MockAttempt.user_id == user_id).with_for_update())
        if not a: return None
        if a.status == "submitted": return _attempt_dict(a)
        if not force and a.deadline_at > utcnow():
            # Manual submit is allowed; force only distinguishes automatic timeout in UI logs.
            pass
        correct = incorrect = unanswered = 0
        max_score = len(a.questions) * 4
        for aq in a.questions:
            snap = json.loads(aq.snapshot_json)
            if not aq.selected_answer:
                unanswered += 1
            elif _matches_answer(snap, aq.selected_answer):
                correct += 1
            else:
                incorrect += 1
                if aq.question_id:
                    existing = db.scalar(select(MistakeNote).where(
                        MistakeNote.user_id == user_id, MistakeNote.question_id == aq.question_id
                    ))
                    if not existing:
                        db.add(MistakeNote(
                            user_id=user_id, question_id=aq.question_id,
                            snapshot_json=aq.snapshot_json,
                            note="Review this question. Identify the concept or step that caused the error."
                        ))
        a.correct, a.incorrect, a.unanswered = correct, incorrect, unanswered
        a.score = correct * 4 - incorrect
        a.max_score = max_score
        a.accuracy = (correct / (correct + incorrect) * 100) if correct + incorrect else 0.0
        a.submitted_at = utcnow()
        a.status = "submitted"
        db.flush()
        return _attempt_dict(a)


def get_mock_history(user_id: int, limit: int = 30) -> list[dict]:
    with session_scope() as db:
        rows = db.scalars(select(MockAttempt).where(MockAttempt.user_id == user_id, MockAttempt.status == "submitted").order_by(MockAttempt.submitted_at.desc()).limit(limit)).all()
        return [{"id": a.id, "title": a.title, "mode": a.mode, "created_at": a.submitted_at,
                 "score": a.score, "max_score": a.max_score, "correct": a.correct,
                 "incorrect": a.incorrect, "unanswered": a.unanswered, "accuracy": a.accuracy,
                 "duration_seconds": a.duration_seconds} for a in rows]


def save_practice(user_id: int, question: dict, answer: str | None, seconds: int = 0) -> dict:
    correct = _matches_answer(question, answer)
    with session_scope() as db:
        db.add(PracticeAttempt(user_id=user_id, question_id=question.get("id"),
                               snapshot_json=json.dumps(question_snapshot(question)),
                               selected_answer=str(answer).strip() if answer else None,
                               is_correct=correct, time_spent_seconds=max(0, int(seconds))))
        if answer and not correct:
            qid = question.get("id")
            if qid:
                existing = db.scalar(select(MistakeNote).where(MistakeNote.user_id == user_id, MistakeNote.question_id == qid))
                if not existing:
                    db.add(MistakeNote(user_id=user_id, question_id=qid,
                                       snapshot_json=json.dumps(question_snapshot(question)), note="Review the concept and write down why this answer was incorrect."))
    return {"correct": correct, "correct_answer": question.get("correct_answer"), "explanation": question.get("explanation", "")}


def get_practice_history(user_id: int, limit: int = 100) -> list[dict]:
    with session_scope() as db:
        rows = db.scalars(select(PracticeAttempt).where(PracticeAttempt.user_id == user_id).order_by(PracticeAttempt.created_at.desc()).limit(limit)).all()
        return [{"id": r.id, "question": json.loads(r.snapshot_json), "answer": r.selected_answer,
                 "is_correct": r.is_correct, "time_spent_seconds": r.time_spent_seconds, "created_at": r.created_at} for r in rows]


def get_topic_performance(user_id: int) -> list[dict]:
    records: list[dict] = []
    with session_scope() as db:
        practice = db.scalars(select(PracticeAttempt).where(PracticeAttempt.user_id == user_id)).all()
        mocks = db.scalars(select(AttemptQuestion).join(MockAttempt).where(MockAttempt.user_id == user_id, MockAttempt.status == "submitted")).all()
        for r in practice:
            q = json.loads(r.snapshot_json)
            records.append({"subject": q.get("subject", ""), "topic": q.get("chapter") or q.get("topic", "Unknown"), "correct": bool(r.is_correct), "answered": bool(r.selected_answer), "seconds": r.time_spent_seconds})
        for r in mocks:
            q = json.loads(r.snapshot_json)
            records.append({"subject": q.get("subject", ""), "topic": q.get("chapter") or q.get("topic", "Unknown"), "correct": _matches_answer(q, r.selected_answer), "answered": bool(r.selected_answer), "seconds": r.time_spent_seconds})
    grouped: dict[tuple[str, str], dict] = {}
    for r in records:
        key = (r["subject"], r["topic"])
        g = grouped.setdefault(key, {"subject": key[0], "topic": key[1], "attempted": 0, "correct": 0, "unanswered": 0, "seconds": 0})
        g["attempted"] += 1
        g["correct"] += int(r["correct"])
        g["unanswered"] += int(not r["answered"])
        g["seconds"] += r["seconds"]
    result = []
    for g in grouped.values():
        g["accuracy"] = g["correct"] / max(1, g["attempted"] - g["unanswered"]) * 100 if g["attempted"] > g["unanswered"] else 0
        g["unanswered_rate"] = g["unanswered"] / max(1, g["attempted"]) * 100
        g["questions"] = g["attempted"]
        result.append(g)
    return sorted(result, key=lambda x: (x["subject"], x["topic"]))


def get_dashboard_stats(user_id: int) -> dict:
    today = date.today()
    with session_scope() as db:
        question_count = db.scalar(select(func.count(Question.id)).where(Question.is_active.is_(True), (Question.is_public.is_(True)) | (Question.owner_id == user_id))) or 0
        mocks = db.scalar(select(func.count(MockAttempt.id)).where(MockAttempt.user_id == user_id, MockAttempt.status == "submitted")) or 0
        practice = db.scalar(select(func.count(PracticeAttempt.id)).where(PracticeAttempt.user_id == user_id)) or 0
        pending = db.scalar(select(func.count(RevisionTask.id)).where(RevisionTask.user_id == user_id, RevisionTask.status == "Pending")) or 0
        minutes = db.scalar(select(func.coalesce(func.sum(StudyLog.minutes), 0)).where(StudyLog.user_id == user_id, StudyLog.study_date == today)) or 0
        setting = db.get(UserSetting, user_id)
        target = setting.daily_target_minutes if setting else 240
    return {"questions": question_count, "mocks": mocks, "practice": practice, "pending_tasks": pending, "today_minutes": int(minutes), "daily_target": target}


def add_revision_task(user_id: int, due_date: date, subject: str, topic: str, task: str, source: str = "Manual") -> int:
    with session_scope() as db:
        row = RevisionTask(user_id=user_id, due_date=due_date, subject=subject, topic=topic, task=task, source=source)
        db.add(row); db.flush(); return row.id


def list_revision_tasks(user_id: int, include_done: bool = True) -> list[dict]:
    with session_scope() as db:
        stmt = select(RevisionTask).where(RevisionTask.user_id == user_id)
        if not include_done: stmt = stmt.where(RevisionTask.status == "Pending")
        rows = db.scalars(stmt.order_by(RevisionTask.due_date, RevisionTask.id)).all()
        return [{"id": r.id, "due_date": r.due_date, "subject": r.subject, "topic": r.topic, "task": r.task, "status": r.status, "source": r.source} for r in rows]


def update_revision_task(user_id: int, task_id: int, status: str | None = None, delete: bool = False) -> None:
    with session_scope() as db:
        row = db.scalar(select(RevisionTask).where(RevisionTask.id == task_id, RevisionTask.user_id == user_id))
        if row:
            if delete: db.delete(row)
            elif status in {"Pending", "Completed"}: row.status = status


def replace_smart_tasks(user_id: int, tasks: list[dict]) -> None:
    with session_scope() as db:
        db.query(RevisionTask).filter(RevisionTask.user_id == user_id, RevisionTask.source == "Smart plan", RevisionTask.status == "Pending").delete(synchronize_session=False)
        for t in tasks:
            db.add(RevisionTask(user_id=user_id, due_date=t["due_date"], subject=t["subject"], topic=t["topic"], task=t["task"], source="Smart plan"))


def add_study_log(user_id: int, study_date: date, subject: str, minutes: int, activity: str, notes: str) -> None:
    with session_scope() as db:
        db.add(StudyLog(user_id=user_id, study_date=study_date, subject=subject, minutes=minutes, activity=activity[:120], notes=notes[:1000]))


def get_study_logs(user_id: int, days: int = 30) -> list[dict]:
    start = date.today() - timedelta(days=days - 1)
    with session_scope() as db:
        rows = db.scalars(select(StudyLog).where(StudyLog.user_id == user_id, StudyLog.study_date >= start).order_by(StudyLog.study_date.desc(), StudyLog.id.desc())).all()
        return [{"id": r.id, "date": r.study_date, "subject": r.subject, "minutes": r.minutes, "activity": r.activity, "notes": r.notes} for r in rows]


def set_daily_target(user_id: int, minutes: int) -> None:
    with session_scope() as db:
        row = db.get(UserSetting, user_id)
        if not row:
            db.add(UserSetting(user_id=user_id, daily_target_minutes=minutes))
        else:
            row.daily_target_minutes = minutes
            row.updated_at = utcnow()


def toggle_bookmark(user_id: int, question_id: int) -> bool:
    with session_scope() as db:
        row = db.scalar(select(Bookmark).where(Bookmark.user_id == user_id, Bookmark.question_id == question_id))
        if row:
            db.delete(row); return False
        db.add(Bookmark(user_id=user_id, question_id=question_id)); return True


def get_bookmarks(user_id: int) -> list[dict]:
    with session_scope() as db:
        rows = db.execute(select(Bookmark, Question).join(Question, Bookmark.question_id == Question.id).where(Bookmark.user_id == user_id, Question.is_active.is_(True)).order_by(Bookmark.created_at.desc())).all()
        return [{**_question_dict(q), "bookmark_id": b.id} for b, q in rows]


def get_mistakes(user_id: int) -> list[dict]:
    with session_scope() as db:
        rows = db.scalars(select(MistakeNote).where(MistakeNote.user_id == user_id).order_by(MistakeNote.resolved, MistakeNote.created_at.desc())).all()
        return [{"id": r.id, "question_id": r.question_id, "question": json.loads(r.snapshot_json), "note": r.note, "resolved": r.resolved, "created_at": r.created_at} for r in rows]


def update_mistake(user_id: int, mistake_id: int, note: str | None = None, resolved: bool | None = None) -> None:
    with session_scope() as db:
        row = db.scalar(select(MistakeNote).where(MistakeNote.id == mistake_id, MistakeNote.user_id == user_id))
        if row:
            if note is not None: row.note = note[:1500]
            if resolved is not None: row.resolved = resolved


def remove_mistake(user_id: int, mistake_id: int) -> None:
    with session_scope() as db:
        row = db.scalar(select(MistakeNote).where(MistakeNote.id == mistake_id, MistakeNote.user_id == user_id))
        if row: db.delete(row)


def get_report_data(user_id: int) -> dict:
    with session_scope() as db:
        attempts = db.scalars(select(MockAttempt).where(MockAttempt.user_id == user_id, MockAttempt.status == "submitted").order_by(MockAttempt.submitted_at)).all()
        logs = db.scalars(select(StudyLog).where(StudyLog.user_id == user_id).order_by(StudyLog.study_date)).all()
        practices = db.scalars(select(PracticeAttempt).where(PracticeAttempt.user_id == user_id).order_by(PracticeAttempt.created_at)).all()
    with session_scope() as db:
        tasks = db.scalars(select(RevisionTask).where(RevisionTask.user_id == user_id).order_by(RevisionTask.due_date)).all()
        mistakes = db.scalars(select(MistakeNote).where(MistakeNote.user_id == user_id).order_by(MistakeNote.created_at)).all()
        bookmarks = db.execute(select(Bookmark, Question).join(Question, Bookmark.question_id == Question.id).where(Bookmark.user_id == user_id)).all()
    return {
        "mocks": [{"id": a.id, "title": a.title, "mode": a.mode, "date": a.submitted_at.isoformat() if a.submitted_at else "", "score": a.score, "max_score": a.max_score, "correct": a.correct, "incorrect": a.incorrect, "unanswered": a.unanswered, "accuracy": a.accuracy} for a in attempts],
        "study": [{"date": l.study_date.isoformat(), "subject": l.subject, "minutes": l.minutes, "activity": l.activity, "notes": l.notes} for l in logs],
        "practice": [{"date": p.created_at.isoformat(), "question": json.loads(p.snapshot_json), "selected_answer": p.selected_answer, "correct": p.is_correct, "seconds": p.time_spent_seconds} for p in practices],
        "revision_tasks": [{"due_date": t.due_date.isoformat(), "subject": t.subject, "topic": t.topic, "task": t.task, "status": t.status, "source": t.source} for t in tasks],
        "mistake_notes": [{"question": json.loads(m.snapshot_json), "note": m.note, "resolved": m.resolved, "created_at": m.created_at.isoformat()} for m in mistakes],
        "bookmarks": [_question_dict(q) for _, q in bookmarks],
    }


def get_attempt_review(user_id: int, attempt_id: int) -> dict | None:
    return get_attempt(user_id, attempt_id)
