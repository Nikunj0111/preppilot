import os
import streamlit as st


def _configured_key():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        try: key = str(st.secrets.get("OPENAI_API_KEY", "")).strip()
        except Exception: key = ""
    return key


def render_ai_tutor():
    st.title("🤖 AI JEE Doubt Solver")
    st.write("Ask for a concept explanation, a worked example or help understanding a step.")
    key = _configured_key()
    with st.expander("AI setup and cost notice", expanded=not bool(key)):
        st.caption("This optional feature sends your prompt to OpenAI. API usage may incur charges. Never paste passwords, personal records or private information into the chat.")
        entered = st.text_input("OpenAI API key for this session", type="password", key="ai_session_key")
        if entered: key = entered.strip()
    if not key:
        st.info("Set OPENAI_API_KEY in your environment or enter a key above. The rest of PrepPilot works without AI.")
        return
    if "ai_messages" not in st.session_state: st.session_state.ai_messages = []
    if "ai_request_count" not in st.session_state: st.session_state.ai_request_count = 0
    for message in st.session_state.ai_messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
    prompt = st.chat_input("Ask your JEE doubt...")
    if prompt:
        if len(prompt) > 6000:
            st.error("Please keep each prompt under 6,000 characters.")
            return
        if st.session_state.ai_request_count >= 25:
            st.warning("This session has reached the 25-request limit. Start a new session later if needed.")
            return
        st.session_state.ai_messages.append({"role":"user", "content":prompt})
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key, timeout=45, max_retries=1)
            messages = [{"role":"system", "content":("You are PrepPilot, a careful JEE Main and Advanced tutor. Explain the reasoning step by step, define symbols, show relevant formulas and units, and point out common mistakes. If a question is ambiguous, state the assumption. Do not invent a question's missing data.")} ] + st.session_state.ai_messages[-10:]
            with st.chat_message("assistant"):
                with st.spinner("Working through the doubt..."):
                    response = client.chat.completions.create(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"), messages=messages, temperature=0.2, max_tokens=1200)
                    answer = response.choices[0].message.content or "I could not generate a response."
                    st.markdown(answer)
            st.session_state.ai_messages.append({"role":"assistant", "content":answer})
            st.session_state.ai_request_count += 1
        except Exception:
            st.error("The AI request failed. Check the API key, connection and API account status. The key is not displayed in this error message.")
    if st.session_state.ai_messages and st.button("Clear AI conversation"):
        st.session_state.ai_messages = []
        st.rerun()
