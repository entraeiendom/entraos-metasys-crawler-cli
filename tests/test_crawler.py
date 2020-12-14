import base64
import os
import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

import crawler.crawler as crawler
import pytest
import pytest_mock
from crawler.db.models import MetasysObject


def setup_module():
    # logging.basicConfig(level=logging.DEBUG)
    os.environ["METASYS_USERNAME"] = 'testuser'
    os.environ["METASYS_PASSWORD"] = 'verysecret'
    os.environ["METASYS_BASEURL"] = 'http://localhost/api/v2'
    os.environ["ENTRAOS_SSO_URL"] = 'http://localhost/entrasso'
    os.environ["ENTRAOS_BAS_BASEURL"] = 'http://localhost/bas'
    os.environ["ENTRAOS_BAS_APPID"] = 'test'
    os.environ["ENTRAOS_BAS_APPNAME"] = 'test'
    os.environ["ENTRAOS_BAS_SECRET"] = 'test'
    os.environ["DSN"] = 'database://bazinga'  # This value is ignored. We mock the database. It only needs to exist.


def get_path(file) -> str:
    return os.path.join(os.path.dirname(__file__), file)


def test_get_objects(requests_mock, metasys_baseurl, logged_in_bearer):
    """Test the get_objects function. Mocks the request as well as the database."""
    with open(get_path('data/objects.page.1.json')) as fh:
        json_text1 = fh.read()
    with open(get_path('data/objects.page.2.json')) as fh:
        json_text2 = fh.read()
    requests_mock.get(metasys_baseurl + '/objects?page=1&', complete_qs=False, text=json_text1)
    requests_mock.get(metasys_baseurl + '/objects?page=2&', complete_qs=False, text=json_text2)
    mockdb_session = MagicMock()

    # Make sure that when the crawler queries for existing objects we make sure there are none.
    # Perhaps we wanna write another test with existing objects that then get ignored.
    mockdb_session.query.return_value.filter_by.return_value.first.return_value = None
    crawler.get_objects(mockdb_session, metasys_baseurl, logged_in_bearer, 165, 0.0)
    assert mockdb_session.add.call_count == 6  # We should have done 6 adds.
    assert mockdb_session.commit.call_count == 6
    assert mockdb_session.add.call_args_list[0][0][0].id == '3C30ACE2-9AD2-4C14-BB3E-480B99A3E9EE'
    assert mockdb_session.add.call_args_list[5][0][0].id == '7B599BFB-3A4A-4F75-85E4-D746FA4EA6E0'


def test_enrich_objects(requests_mock, metasys_baseurl, logged_in_bearer, mocker):
    """Test the enrich objects function. Mocks the request and the database."""
    with open(get_path('data/object.0.json')) as fh:
        json_text = fh.read()
    j_dict = json.loads(json_text)
    id = j_dict["item"]["id"]

    # Set up metasys mock
    requests_mock.get(metasys_baseurl + f'/objects/{id}', complete_qs=True, text=json_text)

    # EntraSSO mock.
    requests_mock.post(os.environ["ENTRAOS_SSO_URL"],
                       headers={'Content-Type': 'application/xml'},
                       text="""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<applicationtoken>
   <params>
       <applicationtokenID>14c670194462012d18facf00e2cc296f</applicationtokenID>
       <applicationid>11</applicationid>
       <applicationname>SSOLoginService</applicationname>       
 <expires>1291813232877</expires>
 </params>
 </applicationtoken>
""")

    # Set up the Bas mock.
    requests_mock.post(
        os.environ['ENTRAOS_BAS_BASEURL'] + '/metadata/bas/realestate/' + 'kjorbo',
        headers={'Content-Type': 'application/json'},
        text='{ "message": "object created"}', # Todo: Not sure how the response looks.
    )

    # Mock the database..
    return_obj = MetasysObject(id=id,
                               name="Energi_kWh",
                               itemReference="GP-SXD9E-113:SOKB16--NAE99/Powermeter.floor01",
                               successes=0,
                               discovered="2020-12-11 08:24:43.031630",
                               lastCrawl="2020-12-11 08:24:43.031630",
                               lastError=None,
                               type=129,
                               )
    mockdb_session = MagicMock()
    mockdb_session.query.return_value.all.return_value = [return_obj]  # This breaks if we filter the query....

    mocker.patch('crawler.crawler.get_type_description',
                 return_value='Powerthingy'
                 )
    crawler.enrich_things(mockdb_session, metasys_baseurl, logged_in_bearer, 0.0, True)

    # We expect one commit do be done.

    assert mockdb_session.commit.call_count == 1
    # Inspect the request mocker. See that 4 calls have been made. These are:
    # 1. call to the metasys sso
    # 2. call to the entraos sso
    # 3. call to metasys (the object)
    # 4. call to Bas (push the object)
    assert requests_mock.call_count == 4


def test_get_uuid_from_url():
    uuid = "bdecf964-a50c-4a44-a586-7e8d95d3d246"
    url = f"http://fla-fla.com/{uuid}"
    assert uuid == crawler.get_uuid_from_url(url)


def test_validate_metasys_object():
    invalid1 = '{ "message": "This is just a test"}'
    invalid2 = '{ "foo":"bar", "quux":"zoo"}'

    with pytest.raises(ValueError, match=r'Error message'):
        crawler.validate_metasys_object(invalid1)
    with pytest.raises(ValueError, match=r'No item'):
        crawler.validate_metasys_object(invalid2)
    with pytest.raises(json.decoder.JSONDecodeError) as e:
        crawler.validate_metasys_object('{This is not valid JSON')


def test__metasysid_to_real_estate():
    itemref = "GP-SXD9E-113:SOKP16-NAE4/FCB.434_121-1OU001.VAVmaks4"
    assert crawler._metasysid_to_real_estate(itemref) == 'kjorbo'


def test__json_converter():
    date = datetime.now(timezone.utc)
    datestr = crawler._json_converter(date)
    assert isinstance(datestr, str)


def test_get_type_description():
    mockdb_session = Mock()

    mockdb_session.query.return_value.filter_by.return_value.first.return_value.description = 'spork'
    type_str = crawler.get_type_description(mockdb_session, 232)
    assert type_str == 'spork'


def test_b64_encode_response():
    text = "hello";
    b64 = "aGVsbG8="
    assert crawler.b64_encode_response(text) == b64
    back = base64.b64decode(crawler.b64_encode_response(text))
    assert back == text.encode('utf8')



def test_grab_enumsets(requests_mock, metasys_baseurl, logged_in_bearer):
    enumset = 508

    with open(get_path('data/enumsets.0.json')) as fh:
        json_text = fh.read()
    requests_mock.get(f'http://localhost/api/v2/enumSets/{enumset}/members?page=1&pageSize=1000',
                      complete_qs=True, text=json_text)

    mockdb_session = Mock()

    # Mock up

    crawler.grab_enumsets(metasys_baseurl, logged_in_bearer, mockdb_session, enumset, 0)
    # We're doing 10 IDs, so 10 updates + 10 commits is 20 calls on the database.
    assert len(mockdb_session.mock_calls) == 20

    # We're doing two http calls. One auth and one to get the enumset.
    assert len(requests_mock.request_history) == 2

