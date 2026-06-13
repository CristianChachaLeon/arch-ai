"""Main module importing from sibling modules."""
from models import User, Config
from utils import format_user, validate_email


def process_user(data: dict) -> User:
    if not validate_email(data.get("email", "")):
        raise ValueError("Invalid email")
    return User(name=data["name"], email=data["email"])


def setup_app() -> Config:
    return Config(app_name="test-app", debug=True)
