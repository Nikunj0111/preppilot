from __future__ import annotations
from io import BytesIO
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from xml.sax.saxutils import escape
from database import get_report_data, get_topic_performance, get_dashboard_stats, list_revision_tasks, list_questions


def _pdf_safe(value) -> str:
    return str(value if value is not None else "").encode("ascii", "replace").decode("ascii")


def build_pdf_report(user: dict, data: dict, topics: list[dict], stats: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    safe_name = _pdf_safe(user["display_name"])
    story = [Paragraph("PrepPilot - JEE Preparation Report", styles["Title"]),
             Paragraph(f"Student: {escape(safe_name)} | Username: {escape(user['username'])}", styles["Normal"]),
             Spacer(1, 12)]
    summary = [["Metric", "Value"], ["Questions in accessible bank", str(stats["questions"])],
               ["Completed mock tests", str(stats["mocks"])], ["Practice attempts", str(stats["practice"])],
               ["Pending revision tasks", str(stats["pending_tasks"])], ["Today's study time", f"{stats['today_minutes']} min"]]
    table = Table(summary, colWidths=[260, 220])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1f3a5f")),
                               ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .4, colors.grey),
                               ("PADDING", (0,0), (-1,-1), 7)]))
    story += [Paragraph("Overview", styles["Heading2"]), table, Spacer(1, 14)]
    story.append(Paragraph("Mock test history", styles["Heading2"]))
    mock_rows = [["Date", "Test", "Score", "Accuracy"]]
    for m in data["mocks"][-15:]:
        mock_rows.append([m["date"][:10], _pdf_safe(m["title"][:28]), f"{m['score']}/{m['max_score']}", f"{m['accuracy']:.1f}%"])
    if len(mock_rows) == 1: mock_rows.append(["No mock tests completed", "", "", ""])
    t = Table(mock_rows, repeatRows=1, colWidths=[75, 220, 85, 75])
    t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#dce6f1")), ("GRID", (0,0), (-1,-1), .35, colors.grey), ("PADDING", (0,0), (-1,-1), 5)]))
    story += [t, Spacer(1, 14), Paragraph("Chapter performance", styles["Heading2"])]
    topic_rows = [["Subject", "Chapter", "Attempts", "Accuracy"]]
    for x in sorted(topics, key=lambda v: v["accuracy"])[:20]:
        topic_rows.append([_pdf_safe(x["subject"]), _pdf_safe(x["topic"][:30]), str(x["questions"]), f"{x['accuracy']:.1f}%"])
    if len(topic_rows) == 1: topic_rows.append(["No data yet", "", "", ""])
    t2 = Table(topic_rows, repeatRows=1, colWidths=[100, 220, 70, 65])
    t2.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#dce6f1")), ("GRID", (0,0), (-1,-1), .35, colors.grey), ("PADDING", (0,0), (-1,-1), 5)]))
    story.append(t2)
    story += [Spacer(1, 12), Paragraph("Study log summary", styles["Heading2"])]
    total_minutes = sum(x["minutes"] for x in data["study"])
    story.append(Paragraph(f"Recorded study time in the available report data: {total_minutes} minutes.", styles["BodyText"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph("This report reflects information recorded in PrepPilot. It is not an official JEE score report.", styles["Italic"]))
    doc.build(story)
    return buffer.getvalue()


def render_reports(user: dict):
    st.title("📄 Reports & Data Export")
    data = get_report_data(user["id"])
    topics = get_topic_performance(user["id"])
    stats = get_dashboard_stats(user["id"])
    st.write("Download your progress data for personal review or backup.")
    c1, c2 = st.columns(2)
    with c1:
        pdf = build_pdf_report(user, data, topics, stats)
        st.download_button("Download progress PDF", pdf, file_name="PrepPilot_Progress_Report.pdf", mime="application/pdf", type="primary", use_container_width=True)
    with c2:
        export = {"mock_history": data["mocks"], "study_logs": data["study"], "practice_history": data["practice"],
                  "revision_tasks": data["revision_tasks"], "mistake_notes": data["mistake_notes"],
                  "bookmarks": data["bookmarks"], "chapter_performance": topics,
                  "accessible_question_bank": list_questions(user["id"], limit=10000)}
        import json
        st.download_button("Download progress data JSON", json.dumps(export, indent=2, default=str).encode("utf-8"), file_name="PrepPilot_Data_Export.json", mime="application/json", use_container_width=True)
    st.divider()
    st.subheader("CSV exports")
    c1, c2, c3 = st.columns(3)
    c1.download_button("Mock history CSV", pd.DataFrame(data["mocks"]).to_csv(index=False).encode(), file_name="mock_history.csv", mime="text/csv", use_container_width=True)
    c2.download_button("Study logs CSV", pd.DataFrame(data["study"]).to_csv(index=False).encode(), file_name="study_logs.csv", mime="text/csv", use_container_width=True)
    practice_rows = []
    for item in data["practice"]:
        q = item["question"]
        practice_rows.append({"date": item["date"], "subject": q.get("subject"), "chapter": q.get("chapter"),
                              "question": q.get("question_text"), "selected_answer": item["selected_answer"],
                              "correct_answer": q.get("correct_answer"), "is_correct": item["correct"],
                              "time_seconds": item["seconds"]})
    c3.download_button("Practice history CSV", pd.DataFrame(practice_rows).to_csv(index=False).encode(), file_name="practice_history.csv", mime="text/csv", use_container_width=True)
    tasks = list_revision_tasks(user["id"])
    if tasks:
        st.download_button("Revision tasks CSV", pd.DataFrame([{**x, "due_date": str(x["due_date"])} for x in tasks]).to_csv(index=False).encode(), file_name="revision_tasks.csv", mime="text/csv")
