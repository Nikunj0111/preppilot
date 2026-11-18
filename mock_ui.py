from __future__ import annotations

import time
from datetime import datetime, timezone
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from database import (
    list_questions, get_attempt, get_active_attempt, save_mock_answer,
    set_question_flag, add_question_time, submit_mock, get_mock_history,
    toggle_bookmark, utcnow
)
from mock_engine import start_mock

SUBJECTS = ["Physics", "Chemistry", "Mathematics"]


def _status(q: dict) -> str:
    if q["marked_for_review"] and q["selected_answer"]:
        return "answered_marked"
    if q["marked_for_review"]:
        return "marked"
    if q["selected_answer"]:
        return "answered"
    if q["visited"]:
        return "not_answered"
    return "not_visited"


def _answer_callback(user_id: int, attempt_id: int, aq_id: int, key: str):
    value = st.session_state.get(key)
    save_mock_answer(user_id, attempt_id, aq_id, value)


def _clear_answer_callback(user_id: int, attempt_id: int, aq_id: int, key: str, qtype: str):
    save_mock_answer(user_id, attempt_id, aq_id, None)
    st.session_state[key] = None if qtype == "MCQ" else ""


def _finish(user_id: int, attempt_id: int, timed_out: bool = False):
    submit_mock(user_id, attempt_id, force=timed_out)
    st.session_state.pop("mock_last_view", None)
    st.session_state["mock_result_attempt_id"] = attempt_id
    st.rerun()


def _render_results(user_id: int, attempt_id: int):
    attempt = get_attempt(user_id, attempt_id)
    if not attempt or attempt["status"] != "submitted":
        st.warning("This result is not available.")
        if st.button("Back to Mock Tests"):
            st.session_state.pop("mock_result_attempt_id", None)
            st.rerun()
        return

    st.title("📊 Mock Test Results")
    submitted_local = attempt["submitted_at"].replace(tzinfo=timezone.utc).astimezone() if attempt["submitted_at"] else None
    st.caption(f"{attempt['title']} · {submitted_local.strftime('%d %b %Y, %I:%M %p') if submitted_local else ''}")
    a, b, c, d, e = st.columns(5)
    a.metric("Score", f"{attempt['score']:g}/{attempt['max_score']}")
    b.metric("Correct", attempt["correct"])
    c.metric("Incorrect", attempt["incorrect"])
    d.metric("Unanswered", attempt["unanswered"])
    e.metric("Accuracy", f"{attempt['accuracy']:.1f}%")

    questions = attempt["questions"]
    by_subject = {}
    for item in questions:
        q = item["question"]
        subject = q.get("subject", "Other")
        data = by_subject.setdefault(subject, {"Correct": 0, "Incorrect": 0, "Unanswered": 0, "Score": 0})
        answer = item["selected_answer"]
        from database import _matches_answer
        if not answer:
            data["Unanswered"] += 1
        elif _matches_answer(q, answer):
            data["Correct"] += 1
            data["Score"] += 4
        else:
            data["Incorrect"] += 1
            data["Score"] -= 1
    st.subheader("Subject-wise analysis")
    st.dataframe(pd.DataFrame([{"Subject": k, **v} for k, v in by_subject.items()]), use_container_width=True, hide_index=True)

    answered = attempt["correct"] + attempt["incorrect"]
    st.write(f"**Attempt rate:** {answered}/{len(questions)} questions")
    st.write(f"**Time allowed:** {attempt['duration_seconds'] // 60} minutes")
    st.divider()
    st.subheader("Question-by-question review")
    for index, item in enumerate(questions, start=1):
        q = item["question"]
        answer = item["selected_answer"]
        from database import _matches_answer
        if not answer:
            label = "Not answered"
        elif _matches_answer(q, answer):
            label = "Correct"
        else:
            label = "Incorrect"
        with st.expander(f"Q{index}. {q.get('subject')} · {q.get('chapter')} · {label}"):
            st.markdown(q.get("question_text", ""))
            if q.get("question_type") == "MCQ":
                for option, value in q.get("options", {}).items():
                    st.write(f"**{option}.** {value}")
            st.write(f"**Your answer:** {answer or 'Not answered'}")
            st.write(f"**Correct answer:** {q.get('correct_answer')}")
            if q.get("explanation"):
                st.info(q["explanation"])
            st.caption(f"Time spent: {item['time_spent_seconds']} seconds · Marked for review: {'Yes' if item['marked_for_review'] else 'No'}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Start another mock", type="primary", use_container_width=True):
            st.session_state.pop("mock_result_attempt_id", None)
            st.rerun()
    with c2:
        csv_rows = []
        for i, item in enumerate(questions, start=1):
            q = item["question"]
            csv_rows.append({"Question": i, "Subject": q.get("subject"), "Chapter": q.get("chapter"),
                             "Your answer": item["selected_answer"], "Correct answer": q.get("correct_answer"),
                             "Time (seconds)": item["time_spent_seconds"]})
        st.download_button("Download question review CSV", pd.DataFrame(csv_rows).to_csv(index=False).encode("utf-8"),
                           file_name=f"preppilot_mock_{attempt_id}.csv", mime="text/csv", use_container_width=True)


def _render_active(user: dict, attempt: dict):
    user_id, attempt_id = user["id"], attempt["id"]
    questions = attempt["questions"]
    if not questions:
        st.error("This mock has no questions.")
        return

    remaining = max(0, int((attempt["deadline_at"] - utcnow()).total_seconds()))
    if remaining <= 0:
        st.warning("Time is up. Your test is being submitted automatically.")
        _finish(user_id, attempt_id, timed_out=True)
        return

    st_autorefresh(interval=1000, key=f"mock_timer_{attempt_id}")
    current = int(st.session_state.get(f"mock_current_{attempt_id}", 0))
    current = max(0, min(current, len(questions) - 1))
    current_item = questions[current]

    # Record active-question time across reruns without counting long browser suspensions.
    now = time.time()
    previous = st.session_state.get("mock_last_view")
    if previous and previous.get("attempt_id") == attempt_id:
        delta = min(5, max(0, int(now - previous["time"])))
        if delta:
            add_question_time(user_id, attempt_id, previous["aq_id"], delta)
    st.session_state["mock_last_view"] = {"attempt_id": attempt_id, "aq_id": current_item["id"], "time": now}
    set_question_flag(user_id, attempt_id, current_item["id"], visited=True)

    # Reload after writes so the palette and answer state always reflect persisted data.
    attempt = get_attempt(user_id, attempt_id)
    questions = attempt["questions"]
    current_item = questions[current]
    q = current_item["question"]

    st.title("🎯 JEE Mock Examination")
    top1, top2, top3 = st.columns([2, 1, 1])
    with top1:
        st.markdown(f"**{attempt['title']}**")
        st.caption(f"{attempt['mode']} · {len(questions)} questions · +4 / −1 / 0")
    with top2:
        st.metric("Time remaining", f"{remaining // 60:02d}:{remaining % 60:02d}")
    with top3:
        st.metric("Answered", sum(bool(x["selected_answer"]) for x in questions))
    st.progress(remaining / max(1, attempt["duration_seconds"]))
    st.divider()

    subject_filter = st.radio("Question section", ["All", *SUBJECTS], horizontal=True, key=f"mock_section_{attempt_id}", label_visibility="collapsed")
    visible = [(i, x) for i, x in enumerate(questions) if subject_filter == "All" or x["question"].get("subject") == subject_filter]
    visible_indices = {i for i, _ in visible}
    if visible and current not in visible_indices:
        st.session_state[f"mock_current_{attempt_id}"] = visible[0][0]
        st.rerun()
    st.caption("Question palette: ○ Not visited · — Visited, unanswered · ✓ Answered · ★ Marked · ✓★ Answered and marked")
    palette_cols = st.columns(10)
    for pos, (global_index, item) in enumerate(visible):
        status = _status(item)
        symbols = {"not_visited": "○", "not_answered": "—", "answered": "✓", "marked": "★", "answered_marked": "✓★"}
        label = f"{symbols[status]} {global_index + 1}"
        with palette_cols[pos % 10]:
            if st.button(label, key=f"palette_{attempt_id}_{global_index}", use_container_width=True,
                         type="primary" if global_index == current else "secondary"):
                st.session_state[f"mock_current_{attempt_id}"] = global_index
                st.rerun()

    st.divider()
    qleft, qright = st.columns([3, 1])
    with qleft:
        st.caption(f"Question {current + 1} of {len(questions)} · {q.get('subject')} · {q.get('chapter')} · {q.get('difficulty')} · {q.get('question_type')}")
        st.markdown(q.get("question_text", ""))
        answer_key = f"mock_answer_{attempt_id}_{current_item['id']}"
        saved_answer = current_item["selected_answer"]
        if answer_key not in st.session_state:
            st.session_state[answer_key] = saved_answer if saved_answer is not None else (None if q.get("question_type") == "MCQ" else "")
        if q.get("question_type") == "MCQ":
            options = list(q.get("options", {}).keys())
            st.radio("Select one option", options=options, format_func=lambda x: f"{x}. {q['options'].get(x, '')}",
                     key=answer_key, index=None, on_change=_answer_callback,
                     args=(user_id, attempt_id, current_item["id"], answer_key))
        else:
            st.text_input("Enter numerical answer", key=answer_key, max_chars=30,
                          on_change=_answer_callback, args=(user_id, attempt_id, current_item["id"], answer_key),
                          placeholder="Enter your numerical answer")
        st.caption("Your answer is saved automatically when you change it.")

    with qright:
        st.markdown("**Question status**")
        st.write("Answered" if current_item["selected_answer"] else "Not answered")
        st.write("Marked for review" if current_item["marked_for_review"] else "Not marked")
        if st.button("★ Unmark for review" if current_item["marked_for_review"] else "☆ Mark for review", use_container_width=True):
            set_question_flag(user_id, attempt_id, current_item["id"], marked=not current_item["marked_for_review"])
            st.rerun()
        qid = q.get("id")
        if qid and st.button("☆ Bookmark question", use_container_width=True):
            toggle_bookmark(user_id, qid)
            st.toast("Bookmark updated")

    st.divider()
    nav1, nav2, nav3, nav4 = st.columns(4)
    with nav1:
        if st.button("← Previous", disabled=current == 0, use_container_width=True):
            st.session_state[f"mock_current_{attempt_id}"] = current - 1
            st.rerun()
    with nav2:
        st.button("Clear response", use_container_width=True,
                  on_click=_clear_answer_callback,
                  args=(user_id, attempt_id, current_item["id"], answer_key, q.get("question_type")))
    with nav3:
        if st.button("Save & Next →", disabled=current >= len(questions) - 1, type="primary", use_container_width=True):
            # Persist current widget value before changing questions.
            save_mock_answer(user_id, attempt_id, current_item["id"], st.session_state.get(answer_key))
            st.session_state[f"mock_current_{attempt_id}"] = current + 1
            st.rerun()
    with nav4:
        if st.button("Review & Submit", use_container_width=True):
            save_mock_answer(user_id, attempt_id, current_item["id"], st.session_state.get(answer_key))
            st.session_state[f"mock_show_submit_{attempt_id}"] = True
            st.rerun()

    if st.session_state.get(f"mock_show_submit_{attempt_id}"):
        latest = get_attempt(user_id, attempt_id)
        answered = sum(bool(x["selected_answer"]) for x in latest["questions"])
        marked = sum(bool(x["marked_for_review"]) for x in latest["questions"])
        st.warning(f"You have answered {answered} of {len(questions)} questions. {len(questions) - answered} are unanswered and {marked} are marked for review.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Confirm final submission", type="primary", use_container_width=True):
                _finish(user_id, attempt_id)
        with c2:
            if st.button("Continue test", use_container_width=True):
                st.session_state[f"mock_show_submit_{attempt_id}"] = False
                st.rerun()


def render_mock_ui(user: dict):
    st.title("JEE Mock Tests")
    user_id = user["id"]
    result_id = st.session_state.get("mock_result_attempt_id")
    if result_id:
        _render_results(user_id, result_id)
        return

    active = get_active_attempt(user_id)
    if active:
        _render_active(user, active)
        return

    st.write("Build exam stamina with timed tests, a live question palette and detailed review.")
    all_questions = list_questions(user_id, limit=5000)
    if not all_questions:
        st.warning("Your question bank is empty. Add questions in Question Bank before creating a mock.")
        return

    mode = st.selectbox("Test mode", ["Custom", "JEE Main 75"], help="JEE Main 75 requires 20 MCQs and 5 numerical questions in each subject.")
    if mode == "JEE Main 75":
        st.info("Full-length pattern: 75 questions, 180 minutes, +4 for correct, −1 for incorrect and 0 for unanswered.")
        with st.form("standard_mock_form"):
            title = st.text_input("Test title", value="JEE Main Full Mock")
            start = st.form_submit_button("Start 3-hour JEE Main mock", type="primary", use_container_width=True)
        if start:
            attempt_id, error = start_mock(user_id, title, mode, 180, SUBJECTS, None, None, 75)
            if error: st.error(error)
            else:
                st.session_state.pop("mock_result_attempt_id", None)
                st.rerun()
    else:
        subjects = st.multiselect("Subjects", SUBJECTS, default=SUBJECTS)
        available = [q for q in all_questions if q["subject"] in subjects]
        chapters = sorted({q["chapter"] for q in available})
        difficulties = ["Easy", "Medium", "Hard"]
        selected_chapters = st.multiselect("Chapters", chapters, default=chapters)
        selected_difficulties = st.multiselect("Difficulty", difficulties, default=difficulties)
        matching = [q for q in available if q["chapter"] in selected_chapters and q["difficulty"] in selected_difficulties]
        st.caption(f"Questions matching your filters: {len(matching)}")
        with st.form("custom_mock_form"):
            count = st.number_input("Number of questions", min_value=1, max_value=max(1, len(matching)), value=min(20, max(1, len(matching))), step=1)
            duration = st.number_input("Duration (minutes)", min_value=5, max_value=180, value=45, step=5)
            title = st.text_input("Test title", value="Custom JEE Mock")
            start = st.form_submit_button("Generate & start mock", type="primary", use_container_width=True)
        if start:
            if not subjects or not selected_chapters or not selected_difficulties or not matching:
                st.error("Choose at least one subject, chapter and difficulty with available questions.")
            else:
                attempt_id, error = start_mock(user_id, title, "Custom", int(duration), subjects, selected_chapters, selected_difficulties, int(count))
                if error: st.error(error)
                else: st.rerun()

    history = get_mock_history(user_id, limit=10)
    st.divider()
    st.subheader("Recent mock history")
    if history:
        st.dataframe(pd.DataFrame([{"Date": h["created_at"].replace(tzinfo=timezone.utc).astimezone().strftime("%d %b %Y %H:%M") if h["created_at"] else "", "Test": h["title"], "Mode": h["mode"], "Score": f"{h['score']:g}/{h['max_score']}", "Accuracy": f"{h['accuracy']:.1f}%"} for h in history]), use_container_width=True, hide_index=True)
    else:
        st.info("Your completed mock tests will appear here.")
