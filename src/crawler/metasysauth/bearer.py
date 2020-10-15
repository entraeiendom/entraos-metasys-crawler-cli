import requests
import datetime
from datetime import timezone
import logging

from dateutil.parser import isoparse

class BearerToken(requests.auth.AuthBase):
    base_url: str = None
    token: str = None
    expires: datetime.datetime = None
    username: str
    password: str

    def __init__(self, base_url, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password

    def __call__(self, r):
        self.validate()
        self.login()
        r.headers["authorization"] = "Bearer " + self.token
        return r

    def login(self):
        resp = requests.post(self.base_url + '/login',
                             json={'username': self.username, 'password': self.password})
        json = resp.json()
        self.token = json["accessToken"]
        self.expires = isoparse(json["expires"])

    def refresh(self):
        resp = requests.post(self.base_url + '/refreshToken')
        json = resp.json()
        self.token = json["accessToken"]
        self.expires = json["expires"]

    def validate(self):
        """Make sure everything is in place for auth. Calls refresh() or login()."""
        if not self.token:
            self.login()
            logging.info("Logging in")
        now = datetime.datetime.now(timezone.utc)
        delta = self.expires - now
        if delta.seconds < 600:
            # We have less than 600 seconds until the token expires.
            # Refresh it.
            self.refresh()
        pass


