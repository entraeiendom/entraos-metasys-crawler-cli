"""
Tests for the bearer authentication class for EntraSSO.
Note that fixtures from conftest.py are automagically available here.
"""

import datetime
import time

import requests


def test_login(logged_in_entrasso_bearer, generate_token):
    """ This seemingly simple test does quite a bit of work.
    It asks for the fixture logged_in_entrasso_bearer which
    mocks the EntraSSO API and does a call aginst it.

    Internally that asks for generate_token and uses it as a token.

    If the logic works then the EntraSSO object gets token set with an
    expiry of one hour.
    """
    now = int(time.time())
    # Check that the expires more than 3555 into the future.
    assert logged_in_entrasso_bearer.expires - now > 3555
    # Check that the token is set.
    assert logged_in_entrasso_bearer.token == generate_token


