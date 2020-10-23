import os
import json
import logging
from unittest.mock import MagicMock

import crawler.crawler as crawler
from crawler.db.models import MetasysObject


def setup_module():
    # logging.basicConfig(level=logging.DEBUG)
    os.environ["METASYS_USERNAME"] = 'testuser'
    os.environ["METASYS_PASSWORD"] = 'verysecret'
    os.environ["METASYS_BASEURL"] = 'http://localhost/api/v2'
    os.environ["DSN"] = 'database://bazinga'  # This value is ignored. We mock the database. It only needs to exist.


def get_path(file) -> str:
    return os.path.join(os.path.dirname(__file__), file)


def test_get_object(requests_mock, baseurl, logged_in_bearer):
    """Test the get_objects function. Mocks the request as well as the database."""
    with open(get_path('data/objects.page.1.json')) as fh:
        json_text1 = fh.read()
    with open(get_path('data/objects.page.2.json')) as fh:
        json_text2 = fh.read()
    requests_mock.get(baseurl + '/objects?page=1&', complete_qs=False, text=json_text1)
    requests_mock.get(baseurl + '/objects?page=2&', complete_qs=False, text=json_text2)
    mockdb_session = MagicMock()

    # Make sure that when the crawler queries for existing objects we make sure there are none.
    # Perhaps we wanna write another test with existing objects that then get ignored.
    mockdb_session.query.return_value.filter_by.return_value.first.return_value = None
    crawler.get_objects(mockdb_session, baseurl, logged_in_bearer, 165, 0.0)
    assert mockdb_session.add.call_count == 6  # We should have done 6 adds.
    assert mockdb_session.commit.call_count == 6
    assert mockdb_session.add.call_args_list[0][0][0].id == '3C30ACE2-9AD2-4C14-BB3E-480B99A3E9EE'
    assert mockdb_session.add.call_args_list[5][0][0].id == '7B599BFB-3A4A-4F75-85E4-D746FA4EA6E0'


def test_enrich_objects(requests_mock, baseurl, logged_in_bearer):
    """Test the enrich objects function. Mocks the request and the database."""
    with open(get_path('data/object.0.json')) as fh:
        json_text = fh.read()
    j_dict = json.loads(json_text)
    id = j_dict["item"]["id"]

    requests_mock.get(baseurl + f'/objects/{id}', complete_qs=True, text=json_text)

    return_obj = MetasysObject(id='3C30ACE2-9AD2-4C14-BB3E-480B99A3E9EE',
                               itemReference='SD001:BA76-NAE99/Powermeter.floor01',
                               name="Powermeter.floor01",
                               successes=0
                               )
    mockdb_session = MagicMock()
    mockdb_session.query.return_value.all.return_value = [return_obj]
    crawler.enrich_things(mockdb_session, MetasysObject, baseurl, logged_in_bearer, 0.0)
    # assert mockdb_session.
    # I would like to assert more on the db mock, but it becomes very fragile.
    # Specifically, I'd like to check that the object I supplied gets committed to the database.
    # For now we'll see if we ended up doing a commit... :-/
    assert mockdb_session.commit.call_count == 1
