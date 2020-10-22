"""Containes the BearerToken class which is our driver
for the bearer token auth used by metasys. """

import datetime
from datetime import timezone
import requests
from dateutil.parser import isoparse
import logging


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
        self.validating = False
        logging.info(f"Created a bearer object for {username} @ {base_url} ")

    def __call__(self, r):
        """ This is the interface to the requests library.
        It validates the token and injects a auth header"""

        # Avoid recursion when using this object to refresh:
        if not self.validating:
            self.validate()
        r.headers["authorization"] = "Bearer " + self.token
        return r

    def login(self):
        """Fires of a login request. Stores the token and its expiration."""
        logging.info(f"Logging in user {self.username}")
        resp = requests.post(self.base_url + '/login',
                             json={'username': self.username, 'password': self.password})
        json_resp = resp.json()
        self.token = json_resp["accessToken"]
        self.expires = isoparse(json_resp["expires"])

    def refresh(self):
        """ Refreshes a still valid token. """
        logging.info("Refreshing token")
        self.validating = True
        resp = requests.post(self.base_url + '/refreshToken', auth=self)  # This feels a bit wonky...
        self.validating = False
        json_resp = resp.json()
        print("JSON:", json_resp)
        self.token = json_resp["accessToken"]
        self.expires = json_resp["expires"]

    def validate(self) -> int:
        """Make sure everything is in place for auth.
        Calls refresh() (if less than 600s left) or login()."""
        if not self.token:
            self.login()
            return
        now = datetime.datetime.now(timezone.utc)
        delta = self.expires - now
        if delta.seconds < 600:
            # We have less than 600 seconds until the token expires.
            # Refresh it.
            logging.info(f"Token is about to expire ({delta.seconds}s left). Refreshing.")
            self.refresh()
