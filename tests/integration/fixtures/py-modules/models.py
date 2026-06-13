"""Data models."""


class User:
    def __init__(self, name: str, email: str) -> None:
        self.name = name
        self.email = email


class Config:
    def __init__(self, app_name: str, debug: bool = False) -> None:
        self.app_name = app_name
        self.debug = debug
