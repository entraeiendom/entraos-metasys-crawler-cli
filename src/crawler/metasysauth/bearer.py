"""Containes the BearerToken class which is our driver
for the bearer token auth used by metasys. """

import datetime
from datetime import timezone
import logging

import requests
from dateutil.parser import isoparse


class BearerToken(requests.auth.AuthBase):
    """ Auth driver + service class for metasys. Used by the requests lib. """
    base_url: str = None
    token: str = None
    expires: datetime.datetime = None
    username: str
    password: str

    def __init__(self, base_url, username: str, password: str):
        """ Initialize the object with base_url, username and password. """
        self.base_url = base_url
        self.username = username
        self.password = password

    def __call__(self, r):
        """ This is the interface to the requests library.
        It validates the token and injects a auth header"""
        self.validate()
        r.headers["authorization"] = "Bearer " + self.token
        return r

    def login(self):
        """Fires of a login request. Stores the token and its expiration."""
        resp = requests.post(self.base_url + '/login',
                             json={'username': self.username, 'password': self.password})
        json = resp.json()
        self.token = json["accessToken"]
        self.expires = isoparse(json["expires"])

    def refresh(self):
        """ Refreshes a still valid token. """
        resp = requests.post(self.base_url + '/refreshToken')
        json = resp.json()
        self.token = json["accessToken"]
        self.expires = json["expires"]

    def validate(self):
        """Make sure everything is in place for auth.
        Calls refresh() (if less than 600s left) or login()."""
        if not self.token:
            self.login()
            logging.info("Logging in")
        now = datetime.datetime.now(timezone.utc)
        delta = self.expires - now
        if delta.seconds < 600:
            # We have less than 600 seconds until the token expires.
            # Refresh it.
            self.refresh()
