"""Shared fixtures are placed here and automagically discovered by pytest."""

import datetime

import pytest

from crawler.metasysauth.bearer import BearerToken  # pylint: disable=wrong-import-position

@pytest.fixture
def username():
    return 'testuser'


@pytest.fixture()
def password():
    return 'verysecret'


@pytest.fixture()
def baseurl():
    return 'http://localhost/api/v2'



@pytest.fixture()
def generate_token():
    return 'bazinga_token'


@pytest.fixture()
def bearer(username, password, baseurl):
    """ Creates a fresh bearer object. No token created at this point. """
    bearer_object = BearerToken(baseurl, username, password)
    return bearer_object


@pytest.fixture()
def logged_in_bearer(requests_mock, baseurl, bearer, generate_token):
    now_plus_one_hour = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    requests_mock.post(baseurl + '/login',
                       json={'accessToken': generate_token,
                             'expires': now_plus_one_hour.isoformat()
                             })
    bearer.login()
    return bearer