from __future__ import annotations
import random
from datetime import date, timedelta
import pandas as pd
import streamlit as st

from database import (
    list_questions, save_practice, get_practice_history, get_topic_performance,
    add_revision_task, list_revision_tasks, update_revision_task, replace_smart_tasks,
    add_study_log, get_study_logs, set_daily_target, get_dashboard_stats,
    get_bookmarks, toggle_bookmark, get_mistakes, update_mistake, remove_mistake,
    get_mock_history
)

SUBJECTS = ["Physics", "Chemistry", "Mathematics"]


def render_practice(user: dict):
    st.title("✍️ Practice")
    questions = list_questions(user["id"], limit=5000)
    if not questions:
        st.info("Add questions to your bank first.")
        return
    c1, c2, c3 = st.columns(3)
    subject = c1.selectbox("Subject", ["All", *SUBJECTS], key="practice_subject")
    available = [q for q in questions if subject == "All" or q["subject"] == subject]
    chapters = sorted({q["chapter"] for q in available})
    chapter = c2.selectbox("Chapter", ["All", *chapters], key="practice_chapter")
    difficulty = c3.selectbox("Difficulty", ["All", "Easy", "Medium", "Hard"], key="practice_difficulty")
    available = [q for q in available if (chapter == "All" or q["chapter"] == chapter) and (difficulty == "All" or q["difficulty"] == difficulty)]
    if not available:
        st.warning("No questions match these filters.")
        return

    load_new = st.button("Load a new question")
    if st.session_state.get("practice_question_id") not in {q["id"] for q in available} or load_new:
        st.session_state.practice_question_id = random.choice(available)["id"]
        st.session_state.pop("practice_feedback", None)
    q = next((x for x in available if x["id"] == st.session_state.practice_question_id), random.choice(available))
    st.session_state.practice_question_id = q["id"]
    st.caption(f"{q['subject']} · {q['chapter']} · {q['difficulty']} · {q['question_type']}")
    st.markdown(q["question_text"])
    if q["question_type"] == "MCQ":
        for letter, value in q["options"].items(): st.write(f"**{letter}.** {value}")

    with st.form(f"practice_form_{q['id']}"):
        if q["question_type"] == "MCQ":
            answer = st.radio("Your answer", list(q["options"].keys()), format_func=lambda x: f"{x}. {q['options'][x]}", index=None)
        else:
            answer = st.text_input("Your numerical answer")
        seconds = st.number_input("Time spent (seconds)", min_value=0, max_value=7200, value=0, step=15)
        submitted = st.form_submit_button("Check answer", type="primary", use_container_width=True)
    if submitted:
        if answer is None or not str(answer).strip():
            st.warning("Choose or enter an answer first.")
        else:
            feedback = save_practice(user["id"], q, answer, int(seconds))
            st.session_state.practice_feedback = {"question_id": q["id"], **feedback, "answer": answer}
            st.rerun()

    feedback = st.session_state.get("practice_feedback")
    if feedback and feedback.get("question_id") == q["id"]:
        if feedback["correct"]: st.success("Correct answer. Nice work.")
        else: st.error(f"Not quite. Correct answer: {feedback['correct_answer']}")
        if feedback.get("explanation"): st.info(feedback["explanation"])
        if not feedback["correct"]: st.caption("This question has been added to your Mistake Notebook.")
        if st.button("Next question", type="primary"):
            st.session_state.practice_question_id = random.choice(available)["id"]
            st.session_state.pop("practice_feedback", None)
            st.rerun()
    if st.button("☆ Bookmark / remove bookmark", key=f"practice_bookmark_{q['id']}"):
        toggle_bookmark(user["id"], q["id"])
        st.toast("Bookmark updated")

    st.divider()
    st.subheader("Recent practice")
    history = get_practice_history(user["id"], limit=10)
    if history:
        st.dataframe(pd.DataFrame([{"Date": h["created_at"].strftime("%d %b %H:%M"), "Subject": h["question"].get("subject"), "Chapter": h["question"].get("chapter"), "Result": "Correct" if h["is_correct"] else "Incorrect", "Your answer": h["answer"]} for h in history]), use_container_width=True, hide_index=True)
    else: st.caption("No practice attempts yet.")


def render_performance(user: dict):
    st.title("📈 Performance Analysis")
    topics = get_topic_performance(user["id"])
    mocks = get_mock_history(user["id"], limit=100)
    if not topics and not mocks:
        st.info("Complete practice questions or mock tests to build your performance dashboard.")
        return
    if mocks:
        scores = pd.DataFrame([{"Date": h["created_at"], "Score": h["score"], "Accuracy": h["accuracy"]} for h in reversed(mocks)])
        st.subheader("Mock test trend")
        st.line_chart(scores.set_index("Date")[["Score"]])
        st.caption("Accuracy is calculated from answered questions. Mock scores use +4 / −1 / 0.")
    if topics:
        frame = pd.DataFrame(topics)
        st.subheader("Chapter performance")
        st.dataframe(frame[["subject", "topic", "questions", "correct", "accuracy", "unanswered_rate", "seconds"]].rename(columns={"subject":"Subject","topic":"Chapter","questions":"Attempts","correct":"Correct","accuracy":"Accuracy %","unanswered_rate":"Unanswered %","seconds":"Time (s)"}), use_container_width=True, hide_index=True)
        chart = frame.groupby("subject", as_index=True)["accuracy"].mean().to_frame("Average accuracy")
        st.subheader("Average accuracy by subject")
        st.bar_chart(chart)
        weakest = sorted([x for x in topics if x["questions"] >= 2], key=lambda x: x["accuracy"])[:5]
        if weakest:
            st.subheader("Topics to prioritise")
            for item in weakest:
                st.warning(f"{item['subject']} · {item['topic']}: {item['accuracy']:.1f}% accuracy across {item['questions']} recorded attempts.")


def render_recommendations(user: dict):
    st.title("🎯 Study Recommendations")
    topics = get_topic_performance(user["id"])
    tasks = list_revision_tasks(user["id"], include_done=False)
    if not topics:
        st.info("Complete some practice questions or mock tests. Recommendations will be based on your actual results.")
    else:
        ranked = sorted(topics, key=lambda t: (t["accuracy"], -t["unanswered_rate"], -t["questions"]))
        st.write("These suggestions are based on your saved practice and mock-test answers.")
        for index, item in enumerate(ranked[:10], start=1):
            if item["questions"] < 2:
                priority, action = "Collect more data", "Complete at least 10 focused questions before judging this topic."
            elif item["accuracy"] < 50:
                priority, action = "High priority", "Revisit core concepts and solved examples, then practise basic questions."
            elif item["accuracy"] < 70 or item["unanswered_rate"] >= 25:
                priority, action = "Medium priority", "Revise formulas and mistakes, then complete a timed set."
            else:
                priority, action = "Maintenance", "Keep the topic fresh with mixed questions and periodic revision."
            with st.container(border=True):
                st.markdown(f"**{index}. {item['subject']} · {item['topic']}**")
                st.caption(f"{priority} · {item['accuracy']:.1f}% accuracy · {item['questions']} attempts")
                st.write(action)
    st.divider()
    st.subheader("Upcoming revision")
    if tasks:
        for task in tasks[:5]: st.write(f"**{task['due_date']} · {task['subject']} · {task['topic']}**  \n{task['task']}")
    else: st.caption("No pending revision tasks.")


def render_revision_planner(user: dict):
    st.title("🗓️ Revision Planner")
    user_id = user["id"]
    performance = get_topic_performance(user_id)
    with st.expander("Create a revision task", expanded=True):
        with st.form("manual_revision_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            due = c1.date_input("Due date", value=date.today())
            subject = c2.selectbox("Subject", SUBJECTS)
            topic = st.text_input("Chapter / topic")
            task = st.text_input("What will you revise?", value="Revise concepts, formulas and solve practice questions.")
            submitted = st.form_submit_button("Add task", type="primary")
        if submitted:
            if not topic.strip() or not task.strip(): st.error("Enter a topic and task description.")
            else:
                add_revision_task(user_id, due, subject, topic.strip(), task.strip())
                st.success("Revision task added.")
                st.rerun()

    with st.expander("Generate a smart plan from performance"):
        days = st.selectbox("Plan length", [7, 14, 21, 30], index=0)
        per_day = st.slider("Target revision time per day (minutes)", 30, 300, 90, step=15)
        if st.button("Generate smart revision plan", type="primary"):
            if not performance:
                st.warning("Complete practice or a mock first so the plan uses real performance data.")
            else:
                ranked = sorted(performance, key=lambda x: (x["accuracy"], -x["unanswered_rate"]))
                generated = []
                for i in range(days):
                    item = ranked[i % len(ranked)]
                    if item["questions"] < 2 or item["accuracy"] < 50:
                        action = "Relearn the core concept, review solved examples and solve 15 basic questions."
                    elif item["accuracy"] < 75 or item["unanswered_rate"] > 25:
                        action = "Revise formulas and previous mistakes, then solve 20 timed questions."
                    else:
                        action = "Complete a short mixed practice set and recall key concepts without notes."
                    generated.append({"due_date": date.today() + timedelta(days=i), "subject": item["subject"], "topic": item["topic"], "task": f"{action} Target time: {per_day} minutes."})
                replace_smart_tasks(user_id, generated)
                st.success(f"Generated {len(generated)} revision tasks. Existing pending smart-plan tasks were replaced.")
                st.rerun()

    tasks = list_revision_tasks(user_id)
    st.divider()
    st.subheader("All revision tasks")
    if not tasks:
        st.info("No tasks yet. Add one above or generate a smart plan.")
        return
    for item in tasks:
        with st.container(border=True):
            c1, c2, c3 = st.columns([1, 4, 1])
            c1.write(item["due_date"].strftime("%d %b") if hasattr(item["due_date"], "strftime") else str(item["due_date"]))
            c2.markdown(f"**{item['subject']} · {item['topic']}**  \n{item['task']}")
            c2.caption(f"{item['source']} · {item['status']}")
            if item["status"] == "Pending":
                if c3.button("Complete", key=f"task_done_{item['id']}"):
                    update_revision_task(user_id, item["id"], status="Completed"); st.rerun()
            else:
                if c3.button("Reopen", key=f"task_reopen_{item['id']}"):
                    update_revision_task(user_id, item["id"], status="Pending"); st.rerun()
            if st.button("Delete task", key=f"task_delete_{item['id']}"):
                update_revision_task(user_id, item["id"], delete=True); st.rerun()


def render_study_tracker(user: dict):
    st.title("⏱️ Study Tracker")
    user_id = user["id"]
    stats = get_dashboard_stats(user_id)
    c1, c2 = st.columns(2)
    c1.metric("Today's study time", f"{stats['today_minutes']} min")
    c2.metric("Daily target", f"{stats['daily_target']} min")
    st.progress(min(1.0, stats["today_minutes"] / max(1, stats["daily_target"])))
    with st.expander("Daily target", expanded=False):
        target = st.number_input("Target minutes per day", min_value=15, max_value=900, value=int(stats["daily_target"]), step=15)
        if st.button("Save daily target"):
            set_daily_target(user_id, int(target)); st.success("Daily target updated."); st.rerun()
    with st.form("study_log_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        study_date = c1.date_input("Study date", value=date.today())
        subject = c2.selectbox("Subject", [*SUBJECTS, "General"])
        minutes = c3.number_input("Minutes studied", min_value=1, max_value=1440, value=60, step=5)
        activity = st.selectbox("Activity", ["Concept learning", "Practice questions", "Mock test", "Revision", "Lecture", "Doubt solving", "Other"])
        notes = st.text_input("Notes (optional)")
        submitted = st.form_submit_button("Log study session", type="primary")
    if submitted:
        add_study_log(user_id, study_date, subject, int(minutes), activity, notes)
        st.success("Study session saved."); st.rerun()
    logs = get_study_logs(user_id, 30)
    st.divider()
    st.subheader("Last 30 days")
    if logs:
        frame = pd.DataFrame(logs)
        daily = frame.groupby("date", as_index=True)["minutes"].sum().sort_index()
        st.bar_chart(daily)
        st.dataframe(frame.rename(columns={"date":"Date","subject":"Subject","minutes":"Minutes","activity":"Activity","notes":"Notes"})[["Date","Subject","Minutes","Activity","Notes"]], use_container_width=True, hide_index=True)
    else: st.info("Your study sessions will appear here.")


def render_bookmarks(user: dict):
    st.title("🔖 Bookmarks")
    items = get_bookmarks(user["id"])
    if not items:
        st.info("Bookmark questions from Practice or Mock Tests to collect them here.")
        return
    for q in items:
        with st.expander(f"{q['subject']} · {q['chapter']} · {q['question_text'][:90]}"):
            st.markdown(q["question_text"])
            for letter, value in q["options"].items(): st.write(f"**{letter}.** {value}")
            st.caption(f"Answer: {q['correct_answer']} · {q['explanation']}")
            if st.button("Remove bookmark", key=f"remove_bookmark_{q['id']}"):
                toggle_bookmark(user["id"], q["id"]); st.rerun()


def render_mistake_notebook(user: dict):
    st.title("🧠 Mistake Notebook")
    st.write("Incorrect practice answers are added automatically. Add your own notes and mark topics resolved after reviewing them.")
    items = get_mistakes(user["id"])
    if not items:
        st.info("No mistakes recorded yet. Incorrect practice answers will appear here.")
        return
    pending = [x for x in items if not x["resolved"]]
    st.metric("Unresolved mistakes", len(pending))
    for item in items:
        q = item["question"]
        with st.expander(f"{'✅' if item['resolved'] else '🔴'} {q.get('subject')} · {q.get('chapter')} · {q.get('question_text','')[:75]}"):
            st.markdown(q.get("question_text", ""))
            for letter, value in q.get("options", {}).items(): st.write(f"**{letter}.** {value}")
            st.write(f"**Correct answer:** {q.get('correct_answer')}")
            if q.get("explanation"): st.info(q["explanation"])
            note = st.text_area("Your learning note", value=item["note"], key=f"mistake_note_{item['id']}", height=90)
            c1, c2 = st.columns(2)
            if c1.button("Save note", key=f"save_mistake_{item['id']}"):
                update_mistake(user["id"], item["id"], note=note); st.success("Note saved.")
            if c2.button("Mark resolved" if not item["resolved"] else "Reopen", key=f"resolve_mistake_{item['id']}"):
                update_mistake(user["id"], item["id"], resolved=not item["resolved"]); st.rerun()
            if st.button("Remove from notebook", key=f"delete_mistake_{item['id']}"):
                remove_mistake(user["id"], item["id"]); st.rerun()
