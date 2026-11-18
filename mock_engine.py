"""Mock test domain logic kept separate from Streamlit presentation."""
from database import start_mock, get_attempt, get_active_attempt, save_mock_answer, set_question_flag, add_question_time, submit_mock

__all__ = ["start_mock", "get_attempt", "get_active_attempt", "save_mock_answer", "set_question_flag", "add_question_time", "submit_mock"]
