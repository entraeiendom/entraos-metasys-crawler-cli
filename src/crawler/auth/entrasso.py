"""
Python Requests driver for auth against some internal XML-based SSO with Bearers.
 """
import logging
import os
import xml.etree.ElementTree as ET

import requests


class EntraSSOToken(requests.auth.AuthBase):
    """ Auth driver + service class for metasys. Used by the requests lib. """
    auth_url: str = None
    token: str = None

    def __init__(self):
        """ Initialize the object with base_url, username and password. """
        self.auth_url = os.environ['ENTRAOS_SSO_URL']

    def __call__(self, r):
        """ This is the interface to the requests library.
        It validates the token and injects a auth header"""

        # Avoid recursion when using this object to refresh:
        if not self.token:
            self.login()
        r.headers["authorization"] = "Bearer " + self.token
        return r

    def login(self):
        """Gets the LOGIN

        Fires of a login request. Stores the token. Ignores expiration."""
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        appid = os.environ['ENTRAOS_BAS_APPID']      # Will raise if not found.
        appname = os.environ['ENTRAOS_BAS_APPNAME']
        secret = os.environ['ENTRAOS_BAS_SECRET']

        data = {
            'applicationcredential': f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?> <applicationcredential> <params> <applicationID>{appid}</applicationID> <applicationName>{appname}</applicationName> <applicationSecret>{secret}</applicationSecret> </params> </applicationcredential>'
        }
        logging.info(f"EntraSSO: Logging in as appid: {appname} with id {appid}")

        response = requests.post(self.auth_url,
                                 headers=headers, data=data)
        response.raise_for_status()
        xml_response = response.text
        root = ET.fromstring(xml_response)
        token = root.find('params').find('applicationtokenID').text
        self.token = token



