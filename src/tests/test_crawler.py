import os
import pytest


@pytest.fixture(scope="module")
def setup_module(username, password, baseurl):
    os.environ["METASYS_USERNAME"] = username
    os.environ["METASYS_PASSWORD"] = password
    os.environ["METASYS_BASEURL"] = baseurl

