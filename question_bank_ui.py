from __future__ import annotations
import io
import math
import pandas as pd
import streamlit as st
from database import list_questions, add_question, bulk_add_questions, delete_question

SUBJECTS = ["Physics", "Chemistry", "Mathematics"]
DIFFICULTIES = ["Easy", "Medium", "Hard"]

CSV_COLUMNS = ["code", "subject", "chapter", "topic", "difficulty", "question_type", "question_text",
               "option_a", "option_b", "option_c", "option_d", "correct_answer", "numeric_tolerance",
               "explanation", "exam", "source", "year", "tags"]


def _template_bytes():
    example = [{"code":"PHY-KIN-001", "subject":"Physics", "chapter":"Kinematics", "topic":"Equations of motion",
                "difficulty":"Easy", "question_type":"MCQ", "question_text":"Example question text",
                "option_a":"Option A", "option_b":"Option B", "option_c":"Option C", "option_d":"Option D",
                "correct_answer":"B", "numeric_tolerance":0, "explanation":"Write a short explanation.",
                "exam":"JEE Main", "source":"Your source reference", "year":"2025", "tags":"kinematics,pyq"}]
    return pd.DataFrame(example, columns=CSV_COLUMNS).to_csv(index=False).encode("utf-8")


def _parse_row(row: dict) -> dict:
    subject = str(row.get("subject", "")).strip().title()
    if subject not in SUBJECTS: raise ValueError("subject must be Physics, Chemistry or Mathematics")
    difficulty = str(row.get("difficulty", "Medium")).strip().title()
    if difficulty not in DIFFICULTIES: raise ValueError("difficulty must be Easy, Medium or Hard")
    qtype = str(row.get("question_type", "MCQ")).strip().upper()
    if qtype not in {"MCQ", "NUMERICAL"}: raise ValueError("question_type must be MCQ or NUMERICAL")
    text = str(row.get("question_text", "")).strip()
    chapter = str(row.get("chapter", row.get("topic", "General"))).strip()
    if not text or not chapter: raise ValueError("question_text and chapter are required")
    if qtype == "MCQ":
        options = {letter: str(row.get(f"option_{letter.lower()}", "")).strip() for letter in "ABCD"}
        if any(not value or value.lower() == "nan" for value in options.values()): raise ValueError("MCQ requires all four options")
        answer = str(row.get("correct_answer", "")).strip().upper()
        if answer not in "ABCD" or len(answer) != 1: raise ValueError("MCQ correct_answer must be A, B, C or D")
    else:
        options = {}
        answer = str(row.get("correct_answer", "")).strip()
        numeric_answer = float(answer)
        if not math.isfinite(numeric_answer): raise ValueError("correct numerical answer must be finite")
    tolerance = float(row.get("numeric_tolerance", 0) or 0)
    if not math.isfinite(tolerance) or tolerance < 0: raise ValueError("numeric_tolerance must be a finite, non-negative number")
    year_value = str(row.get("year", "")).strip()
    year = int(float(year_value)) if year_value and year_value.lower() != "nan" else None
    code = str(row.get("code", "")).strip()
    if not code or code.lower() == "nan": code = None
    return {"code": code, "subject": subject, "chapter": chapter, "topic": str(row.get("topic", chapter)).strip() or chapter,
            "difficulty": difficulty, "question_type": qtype, "question_text": text, "options": options,
            "correct_answer": answer, "numeric_tolerance": tolerance,
            "explanation": str(row.get("explanation", "")).strip(), "exam": str(row.get("exam", "JEE Main")).strip(),
            "source": str(row.get("source", "CSV import")).strip(), "year": year,
            "tags": str(row.get("tags", "")).strip()}


def render_question_bank(user: dict):
    st.title("📚 Question Bank")
    st.write("Create your own private question collection or import a CSV. Sample questions are shared read-only.")
    st.download_button("Download CSV template", _template_bytes(), file_name="preppilot_question_template.csv", mime="text/csv")
    add_tab, import_tab, browse_tab = st.tabs(["Add question", "Import CSV", "Browse questions"])

    with add_tab:
        c1, c2, c3 = st.columns(3)
        subject = c1.selectbox("Subject", SUBJECTS, key="add_subject")
        difficulty = c2.selectbox("Difficulty", DIFFICULTIES, index=1, key="add_difficulty")
        qtype = c3.selectbox("Question type", ["MCQ", "NUMERICAL"], key="add_qtype")
        with st.form("add_question_form", clear_on_submit=True):
            chapter = st.text_input("Chapter", placeholder="e.g. Kinematics")
            topic = st.text_input("Topic / subtopic", placeholder="Optional, defaults to chapter")
            question_text = st.text_area("Question", height=120)
            options = {}
            if qtype == "MCQ":
                c1, c2 = st.columns(2)
                options["A"] = c1.text_input("Option A")
                options["B"] = c2.text_input("Option B")
                options["C"] = c1.text_input("Option C")
                options["D"] = c2.text_input("Option D")
                correct = st.selectbox("Correct option", ["A", "B", "C", "D"])
                tolerance = 0.0
            else:
                correct = st.text_input("Correct numerical answer")
                tolerance = st.number_input("Accepted tolerance", min_value=0.0, value=0.0, step=0.01, format="%.4f")
            explanation = st.text_area("Explanation / solution", height=100)
            c1, c2, c3 = st.columns(3)
            exam = c1.selectbox("Exam", ["JEE Main", "JEE Advanced", "Other"])
            source = c2.text_input("Source", value="User added")
            year = c3.number_input("PYQ year (optional)", min_value=2002, max_value=2035, value=2025)
            tags = st.text_input("Tags (comma separated)")
            submitted = st.form_submit_button("Save question", type="primary", use_container_width=True)
        if submitted:
            try:
                data = {"subject": subject, "chapter": chapter, "topic": topic or chapter, "difficulty": difficulty,
                        "question_type": qtype, "question_text": question_text, "options": options,
                        "correct_answer": correct, "numeric_tolerance": tolerance, "explanation": explanation,
                        "exam": exam, "source": source, "year": int(year) if year else None, "tags": tags}
                parsed = _parse_row({**data, "option_a": options.get("A"), "option_b": options.get("B"), "option_c": options.get("C"), "option_d": options.get("D")})
                add_question(user["id"], parsed)
                st.success("Question saved to your private bank.")
            except Exception as exc:
                st.error(str(exc))

    with import_tab:
        uploaded = st.file_uploader("Upload CSV", type=["csv"], help="Use the template above. Imported questions are private to your account.")
        if uploaded:
            try:
                frame = pd.read_csv(uploaded).fillna("")
                st.write(f"Found {len(frame)} rows.")
                st.dataframe(frame.head(8), use_container_width=True, hide_index=True)
                if st.button("Validate and import CSV", type="primary"):
                    parsed, errors = [], []
                    for idx, row in frame.iterrows():
                        try: parsed.append(_parse_row(row.to_dict()))
                        except Exception as exc: errors.append(f"Row {idx + 2}: {exc}")
                    if parsed:
                        added, insert_errors = bulk_add_questions(user["id"], parsed)
                        errors.extend(insert_errors)
                        st.success(f"Imported {added} questions.")
                    if errors:
                        st.warning("Some rows were skipped:")
                        for err in errors[:30]: st.write(f"• {err}")
            except Exception as exc:
                st.error(f"Could not read CSV: {exc}")

    with browse_tab:
        subject_filter = st.selectbox("Subject filter", ["All", *SUBJECTS], key="qb_subject_filter")
        search = st.text_input("Search question text, chapter or tags")
        rows = list_questions(user["id"], subject=subject_filter, search=search, limit=2000)
        st.caption(f"{len(rows)} questions available to you")
        if rows:
            table = [{"ID": q["id"], "Owner": "Your question" if q["owner_id"] == user["id"] else "Sample", "Subject": q["subject"], "Chapter": q["chapter"], "Difficulty": q["difficulty"], "Type": q["question_type"], "Question": q["question_text"][:120]} for q in rows]
            st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
            choices = {f"#{q['id']} · {q['subject']} · {q['chapter']} · {q['question_text'][:55]}": q for q in rows}
            selected_label = st.selectbox("Preview a question", list(choices.keys()))
            selected = choices[selected_label]
            with st.expander("Question details", expanded=True):
                st.markdown(selected["question_text"])
                for letter, value in selected["options"].items(): st.write(f"**{letter}.** {value}")
                st.write(f"**Correct answer:** {selected['correct_answer']}")
                st.caption(selected.get("explanation", ""))
                if selected["owner_id"] == user["id"]:
                    if st.button("Delete this question", type="secondary"):
                        delete_question(user["id"], selected["id"])
                        st.success("Question removed from your bank.")
                        st.rerun()
            export_rows = []
            for q in rows:
                export_rows.append({"code":q["code"],"subject":q["subject"],"chapter":q["chapter"],"topic":q["topic"],"difficulty":q["difficulty"],"question_type":q["question_type"],"question_text":q["question_text"],"option_a":q["options"].get("A",""),"option_b":q["options"].get("B",""),"option_c":q["options"].get("C",""),"option_d":q["options"].get("D",""),"correct_answer":q["correct_answer"],"numeric_tolerance":q["numeric_tolerance"],"explanation":q["explanation"],"exam":q["exam"],"source":q["source"],"year":q["year"],"tags":q["tags"]})
            st.download_button("Export visible questions as CSV", pd.DataFrame(export_rows).to_csv(index=False).encode(), file_name="preppilot_question_bank.csv", mime="text/csv")
        else:
            st.info("No questions match this filter.")
