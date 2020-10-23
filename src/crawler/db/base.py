"""Service stuff for the database. If we wanna override the Base class we can do that here."""

import os


def get_dsn() -> str:
    """Return DSN - throws an exception if it isn't set."""
    return os.environ["DSN"]
