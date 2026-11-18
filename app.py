from __future__ import annotations
import time
from datetime import timezone
import streamlit as st

from database import init_db, get_dashboard_stats, get_mock_history, list_revision_tasks, get_study_logs, get_topic_performance
from auth_ui import render_auth
from mock_ui import render_mock_ui
from question_bank_ui import render_question_bank
from study_ui import (render_practice, render_performance, render_recommendations,
                      render_revision_planner, render_study_tracker, render_bookmarks,
                      render_mistake_notebook)
from reports_ui import render_reports
from ai_tutor_ui import render_ai_tutor

st.set_page_config(page_title="PrepPilot | JEE Preparation", page_icon="📘", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
:root { --pp-accent: #2563eb; }
.block-container { padding-top: 1.8rem; padding-bottom: 3rem; max-width: 1450px; }
[data-testid="stSidebar"] { border-right: 1px solid rgba(120,120,120,.18); }
[data-testid="stMetric"] { background: rgba(120,120,120,.07); border: 1px solid rgba(120,120,120,.12); padding: 12px 14px; border-radius: 12px; }
.stButton > button, .stDownloadButton > button { border-radius: 9px; }
.auth-wrap { max-width: 620px; margin: 2rem auto; }
.small-muted { opacity: .72; font-size: .9rem; }
</style>
""", unsafe_allow_html=True)

init_db()

# Streamlit session state expires after a period of inactivity.
if "user" in st.session_state:
    last_seen = st.session_state.get("auth_last_seen", time.time())
    if time.time() - last_seen > 8 * 60 * 60:
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.warning("Your session expired. Please log in again.")
        st.rerun()
    st.session_state.auth_last_seen = time.time()

if "user" not in st.session_state:
    render_auth()
    st.stop()

user = st.session_state.user
PAGES = ["Dashboard", "Practice", "JEE Mock Tests", "Question Bank", "Performance Analysis",
         "Recommendations", "Revision Planner", "Study Tracker", "Mistake Notebook",
         "Bookmarks", "Reports & Export", "AI Doubt Solver"]

with st.sidebar:
    st.markdown("# 📘 PrepPilot")
    st.caption("JEE preparation workspace")
    st.write(f"Signed in as **{user['display_name']}**")
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.divider()
    stats = get_dashboard_stats(user["id"])
    st.caption(f"Today's study: {stats['today_minutes']} / {stats['daily_target']} min")
    st.progress(min(1.0, stats["today_minutes"] / max(1, stats["daily_target"])))
    if st.button("Log out", use_container_width=True):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    st.caption("Keep your account password private. Back up your database regularly.")


def render_dashboard():
    st.title(f"Welcome back, {user['display_name']} 👋")
    st.write("A clear view of your JEE preparation, practice and revision.")
    stats = get_dashboard_stats(user["id"])
    a, b, c, d = st.columns(4)
    a.metric("Questions available", stats["questions"])
    b.metric("Completed mocks", stats["mocks"])
    c.metric("Practice attempts", stats["practice"])
    d.metric("Pending revision", stats["pending_tasks"])
    st.subheader("Today's study target")
    left, right = st.columns([3, 1])
    with left:
        st.progress(min(1.0, stats["today_minutes"] / max(1, stats["daily_target"])))
        st.caption(f"{stats['today_minutes']} of {stats['daily_target']} minutes logged today")
    with right:
        st.metric("Completion", f"{min(100, stats['today_minutes'] / max(1, stats['daily_target']) * 100):.0f}%")
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Recent mock tests")
        history = get_mock_history(user["id"], limit=5)
        if history:
            import pandas as pd
            st.dataframe(pd.DataFrame([{"Date": x["created_at"].replace(tzinfo=timezone.utc).astimezone().strftime("%d %b %Y") if x["created_at"] else "", "Test": x["title"], "Score": f"{x['score']:g}/{x['max_score']}", "Accuracy": f"{x['accuracy']:.1f}%"} for x in history]), use_container_width=True, hide_index=True)
        else: st.info("Your completed mock tests will appear here.")
    with col2:
        st.subheader("Next revision tasks")
        tasks = list_revision_tasks(user["id"], include_done=False)[:5]
        if tasks:
            for task in tasks:
                due = task["due_date"].strftime("%d %b") if hasattr(task["due_date"], "strftime") else task["due_date"]
                st.write(f"**{due} · {task['subject']} · {task['topic']}**")
                st.caption(task["task"])
        else: st.info("No pending tasks. Add one in Revision Planner.")
    topics = get_topic_performance(user["id"])
    if topics:
        st.divider()
        st.subheader("Your current focus areas")
        weak = sorted([x for x in topics if x["questions"] >= 2], key=lambda x: x["accuracy"])[:3]
        if weak:
            for x in weak: st.warning(f"{x['subject']} · {x['topic']} · {x['accuracy']:.1f}% accuracy")
        else: st.caption("Complete a few more questions per chapter to build reliable performance signals.")

if page == "Dashboard": render_dashboard()
elif page == "Practice": render_practice(user)
elif page == "JEE Mock Tests": render_mock_ui(user)
elif page == "Question Bank": render_question_bank(user)
elif page == "Performance Analysis": render_performance(user)
elif page == "Recommendations": render_recommendations(user)
elif page == "Revision Planner": render_revision_planner(user)
elif page == "Study Tracker": render_study_tracker(user)
elif page == "Mistake Notebook": render_mistake_notebook(user)
elif page == "Bookmarks": render_bookmarks(user)
elif page == "Reports & Export": render_reports(user)
elif page == "AI Doubt Solver": render_ai_tutor()
