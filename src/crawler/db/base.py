import os


def get_dsn() -> str:
    return os.environ["DSN"]
