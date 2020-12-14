"""
Tests for the bearer authentication class in the crawler.
Note that fixtures from conftest.py are automagically available here.
"""

import datetime
import requests


def test_login(logged_in_bearer, generate_token):
    assert logged_in_bearer.token == generate_token


def test_refresh(requests_mock, metasys_baseurl, logged_in_bearer, generate_token):
    new_token = generate_token + 'zapp'
    now_plus_one_hour = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    requests_mock.get(metasys_baseurl + '/refreshToken',
                      json={'accessToken': new_token,
                            'expires': now_plus_one_hour.isoformat()
                            })
    logged_in_bearer.refresh()
    assert logged_in_bearer.token == new_token
    assert logged_in_bearer.expires == now_plus_one_hour


def test_validate(requests_mock, logged_in_bearer, generate_token):
    """ We test validate on the bearer object. Since this is a brand new
    object nothing should happen. If this fails then something is wrong.
    """
    logged_in_bearer.validate()
    # The only call done through the mock is the call to /login
    assert requests_mock.call_count == 1
    # Inspect requests_mock.request_history if you wanna see what has happened.


def test_validate_with_refresh(requests_mock, metasys_baseurl, logged_in_bearer, generate_token):
    """ We test validate on the bearer object. Since this is a brand new
    object nothing should happen. If this fails then something is wrong.
    """
    new_token = "snafu"
    # Make the token almost expire to trigger refresh:
    logged_in_bearer.expires = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=9)

    now_plus_one_hour = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    requests_mock.get(metasys_baseurl + '/refreshToken',
                      json={'accessToken': new_token,
                            'expires': now_plus_one_hour.isoformat()
                            })
    logged_in_bearer.validate()
    # The only call done through the mock is the call to /login
    assert requests_mock.call_count == 2
    assert requests_mock.request_history[0].url.split('/')[-1] == 'login'
    assert requests_mock.request_history[1].url.split('/')[-1] == 'refreshToken'
    assert logged_in_bearer.token == new_token
    assert logged_in_bearer.expires == now_plus_one_hour


def test_bearer_token_dunder_call(requests_mock, metasys_baseurl, generate_token, bearer):
    """ Tests the authentication driver class as a whole, as invoked by the requests library. """
    unicorn_name = 'Elgar'
    no_of_horns = 1
    requests_mock.post(metasys_baseurl + '/make_unicorn',
                       json={'name': unicorn_name,
                             'no_of_horns': no_of_horns
                             })
    now_plus_one_hour = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)

    requests_mock.post(metasys_baseurl + '/login',
                       json={'accessToken': generate_token,
                             'expires': now_plus_one_hour.isoformat()
                             })

    resp = requests.post(metasys_baseurl + '/make_unicorn', auth=bearer)
    assert resp.json()["name"] == unicorn_name
    assert resp.json()["no_of_horns"] == no_of_horns
