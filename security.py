"""Password hashing and basic persistent login throttling helpers."""
import base64
import hashlib
import hmac
import os
import re

PBKDF2_ROUNDS = 420_000
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,29}$")


def validate_registration(username: str, display_name: str, password: str) -> str | None:
    username = username.strip().lower()
    if not USERNAME_RE.fullmatch(username):
        return "Username must be 3–30 characters and use letters, numbers, dots, underscores or hyphens."
    if not display_name.strip() or len(display_name.strip()) > 80:
        return "Enter a display name between 1 and 80 characters."
    if len(password) < 10:
        return "Use a password with at least 10 characters."
    if len(password) > 128:
        return "Password must be 128 characters or fewer."
    return None


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
