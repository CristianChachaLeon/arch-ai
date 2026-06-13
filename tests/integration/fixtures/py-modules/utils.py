"""Utility functions."""
import re

EMAIL_RE = re.compile(r"[^@]+@[^@]+\.[^@]+")

def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email))

def format_user(name: str, email: str) -> str:
    return f"{name} <{email}>"
