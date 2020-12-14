"""Shared fixtures are placed here and automagically discovered by pytest."""
import logging
import os
import sys

import datetime
import time

import pytest
from crawler.auth.entrasso import EntraSSOToken

from crawler.auth.metasysbearer import BearerToken  # pylint: disable=wrong-import-position


def pytest_sessionstart(session):
    # Setup logging to stdout so pytest captures it.
    # It seems to ignore stderr.
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    root.addHandler(handler)


@pytest.fixture
def username():
    return 'testuser'


@pytest.fixture()
def password():
    return 'verysecret'


@pytest.fixture()
def metasys_baseurl():
    return 'http://localhost/api/v2'


@pytest.fixture()
def generate_token():
    return 'bazinga_token'


@pytest.fixture()
def metasys_bearer(username, password, metasys_baseurl):
    """ Creates a fresh bearer object. No token created at this point. """
    bearer_object = BearerToken(metasys_baseurl, username, password)
    return bearer_object


@pytest.fixture()
def logged_in_metasys_bearer(requests_mock, metasys_baseurl, metasys_bearer, generate_token):
    now_plus_one_hour = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    requests_mock.post(metasys_baseurl + '/login',
                       json={'accessToken': generate_token,
                             'expires': now_plus_one_hour.isoformat()
                             })
    metasys_bearer.login()
    return metasys_bearer


# Fixtures for EntraSSO

@pytest.fixture()
def entrasso_auth_url():
    return 'http://localhost/entrasso'

@pytest.fixture()
def entrasso_bearer(entrasso_auth_url):
    """ Creates a fresh bearer object. No token created at this point but it should be ready to go.. """
    bearer_object = EntraSSOToken(entrasso_auth_url, appid=666, appname='test', secret="entrasso secret")
    return bearer_object


@pytest.fixture()
def logged_in_entrasso_bearer(requests_mock, entrasso_bearer, generate_token, entrasso_auth_url) -> EntraSSOToken:
    """ Logs in entrasso. This can also happen explicitly or lazily, whenever it is used"""
    now_plus_one_hour = int(time.time()) + 3600

    response = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<applicationtoken>
   <params>
       <applicationtokenID>{generate_token}</applicationtokenID>
       <applicationid>11</applicationid>
       <applicationname>SSOLoginService</applicationname>       
       <expires>{now_plus_one_hour}</expires>
 </params>
 </applicationtoken>
"""

    requests_mock.post(entrasso_auth_url,
                       headers={'Content-Type': 'application/xml'},
                       text=response)
    entrasso_bearer.login()
    return entrasso_bearer

# Fixtures for BAS
@pytest.fixture()
def bas_target_url():
    return "http://localhost/bas/metadata/bas/realestate"