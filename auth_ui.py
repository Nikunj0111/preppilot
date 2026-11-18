import streamlit as st
from database import create_user, get_user_by_username, login_lock_status, record_login_failure, clear_login_failures
from security import hash_password, verify_password, validate_registration


def render_auth():
    st.markdown("<div class='auth-wrap'>", unsafe_allow_html=True)
    st.title("📘 PrepPilot")
    st.caption("Your JEE preparation workspace")
    login_tab, signup_tab = st.tabs(["Log in", "Create account"])

    with login_tab:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", max_chars=30).strip().lower()
            password = st.text_input("Password", type="password", max_chars=128)
            submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
        if submitted:
            locked = login_lock_status(username)
            if locked:
                st.error("Too many failed attempts. Try again in about 15 minutes.")
            else:
                user = get_user_by_username(username)
                if user and verify_password(password, user["password_hash"]):
                    clear_login_failures(username)
                    st.session_state.user = {"id": user["id"], "username": user["username"], "display_name": user["display_name"]}
                    st.session_state.auth_last_seen = __import__("time").time()
                    st.rerun()
                else:
                    record_login_failure(username)
                    st.error("Username or password is incorrect.")

    with signup_tab:
        with st.form("signup_form", clear_on_submit=True):
            display_name = st.text_input("Your name", max_chars=80)
            new_username = st.text_input("Choose a username", max_chars=30).strip().lower()
            new_password = st.text_input("Create password", type="password", max_chars=128)
            confirm = st.text_input("Confirm password", type="password", max_chars=128)
            submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
        if submitted:
            error = validate_registration(new_username, display_name, new_password)
            if error:
                st.error(error)
            elif new_password != confirm:
                st.error("The passwords do not match.")
            else:
                user, error = create_user(new_username, display_name, hash_password(new_password))
                if error:
                    st.error(error)
                else:
                    st.session_state.user = user
                    st.session_state.auth_last_seen = __import__("time").time()
                    st.success("Account created.")
                    st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
