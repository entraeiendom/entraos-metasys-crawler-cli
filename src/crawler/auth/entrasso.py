"""
Python Requests driver for auth against some internal XML-based SSO with Bearers - EntraSSO.
 """
import logging
import xml.etree.ElementTree as ET
import time

import requests


class EntraSSOToken(requests.auth.AuthBase):
    """ Auth driver + service class for EntraSSO. Used by the requests lib when accessing services
    protected by EntraSSO. """
    auth_url: str = None
    token: str = None
    expires: int = None
    appid: str = None
    appname: str = None
    secret: str = None


    def __init__(self, url: str, appid: str, appname: str, secret: str):
        """ Initialize the object with base_url, username and password. """
        self.auth_url = url
        self.appid = appid
        self.appname = appname
        self.secret = secret


    def __call__(self, r):
        """ This is the interface to the requests library.
        It validates the token and injects a auth header"""
        now = int(time.time())
        # Avoid recursion when using this object to refresh
        # Be careful not to end up calling yourself.

        if not self.token:
            self.login()
        delta = self.expires - now
        logging.debug(f"EntraSSO session time remaining: {delta}")
        if delta < 120:
            logging.info("EntraSSO token is expiring in less than 120 seconds. Deleting token.")
            self.token = None
            self.login()
        r.headers["authorization"] = "Bearer " + self.token
        return r

    def login(self):
        """Gets the LOGIN

        Fires of a login request. Stores the token and expiration."""
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            'applicationcredential':
                f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?> 
                <applicationcredential> 
                <params> <applicationID>{self.appid}</applicationID> 
                <applicationName>{self.appname}</applicationName>
                <applicationSecret>{self.secret}</applicationSecret> 
                </params> 
                </applicationcredential>"""
        }
        logging.info(f"EntraSSO: Logging in as appid: {self.appname} with id {self.appid}")

        response = requests.post(self.auth_url,
                                 headers=headers, data=data)
        response.raise_for_status()
        xml_response = response.text
        root = ET.fromstring(xml_response)
        token = root.find('params').find('applicationtokenID').text
        self.token = token
        expires = int(root.find('params').find('expires').text)
        self.expires = expires
