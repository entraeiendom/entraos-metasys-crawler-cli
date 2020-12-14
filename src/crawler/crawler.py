""" Crawler for the Metasys API."""
import base64
import json
import os
import re
import sys
import time
import uuid
from datetime import timezone, datetime
import logging
from functools import lru_cache

import click
import requests
import sqlalchemy
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Local modules. Fix the somewhat braindead import path...
sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))

from db.models import MetasysObject, EnumSet, Base
from db.base import get_dsn
from auth.metasysbearer import BearerToken
from auth.entrasso import EntraSSOToken
from model.bas import Bas

from metadata.buildingmap import BUILDING_MAP

# Constants:

REQUESTS_TIMEOUT = 30.0  # 30 second timeout on the requests sent.


def db_engine() -> sqlalchemy.engine.Engine:
    """ Acquire a database engine. Mostly used by session.
    Uses the DSN env variable. """
    dsn = get_dsn()
    engine = create_engine(dsn)
    return engine


def db_session(engine: sqlalchemy.engine.Engine = None) -> sqlalchemy.orm.session.Session:
    """ Get a database session. """
    # Engine default to None. If it isn't set then we set it ourselves.
    if not engine:
        engine = db_engine()
    Session = sessionmaker(bind=engine)  # pylint: disable=invalid-name
    session = Session()
    return session


def get_uuid_from_url(url: str) -> str:
    """ Strip the URL from the string. Returns the UUID. """
    return url.split('/')[-1]


def insert_object(session, item, object_type):
    """ Insert an item into the database if it doesn't exists. """
    obj_id = item["id"]

    existing_item = session.query(MetasysObject).filter_by(id=obj_id).first()
    if existing_item and existing_item.discovered:
        logging.info(f"Ignoring {obj_id} as we've already discovered it.")
        return

    logging.info(f"Inserting {obj_id}")

    parent_url = item["parentUrl"]
    if parent_url:
        parent_id = get_uuid_from_url(item["parentUrl"])
    else:
        parent_id = None

    session.add(MetasysObject(id=obj_id,
                              parentId=parent_id,
                              itemReference=item["itemReference"],
                              name=item["name"],
                              discovered=datetime.now(timezone.utc),
                              type=object_type
                              ))
    session.commit()


def get_objects(session: sqlalchemy.orm.session.Session, base_url: str,
                bearer: BearerToken, object_type: int, delay: float):
    """ Get the list of objects from Metasys and store them in the database."""
    page = 1
    while True:
        resp = requests.get(base_url +
                            f"/objects?page={page}&type={object_type}&pageSize=1000&sort=name",
                            auth=bearer, timeout=REQUESTS_TIMEOUT)
        json_response = resp.json()
        items = json_response["items"]
        logging.info(f"Working on page ({page} - {len(items)} items")
        for item in json_response["items"]:
            insert_object(session, item, object_type)
        logging.info(f"Page({page}) complete.")
        page = page + 1
        if json_response["next"] is None:  # the last page has a none link to next.
            break
        time.sleep(delay)


def validate_metasys_object(response: str):
    """Validate that the JSON we get is valid JSON and doesn't
    contain errors.

    Throws ValueError upon failure. The JSON parser might also throw errors.
    """

    j = json.loads(response)
    if 'message' in j:
        raise ValueError(f'Error message found in response: {j["message"]}')

    if 'item' not in j:
        raise ValueError('No item in reponse.')


def enrich_single_thing(session: sqlalchemy.orm.session.Session,
                        base_url: str,
                        metasys_bearer: BearerToken,
                        item_object: MetasysObject,
                        entrasso: EntraSSOToken
                        ):
    """ Fetch a single object from Metasys and store the response.
    Note that this modifies the DBO object we've been handled and
    we expect the caller to commit() these changes at some point
    if you wanna persist them.

    """
    try:
        resp = requests.get(base_url + f"/objects/{item_object.id}",
                            auth=metasys_bearer, timeout=REQUESTS_TIMEOUT)
        validate_metasys_object(resp.text)  # Validate the response. Throws exceptions.
        item_object.lastCrawl = datetime.now(timezone.utc)
        push_reponse_to_bas(session, resp.text, item_object, entrasso)  # Push to Bas. Throws exceptions.
        item_object.successes += 1
        item_object.lastSync = datetime.now(tz=timezone.utc)

    except requests.exceptions.RequestException as requests_exception:
        item_object.lastError = datetime.now(timezone.utc)
        item_object.errors += 1
        logging.error(requests_exception)
    except Exception as response_exception:
        item_object.lastError = datetime.now(timezone.utc)
        item_object.errors += 1
        logging.error(response_exception)


# This is the deep crawl. Might wanna try to cut down on the number of arguments.
def enrich_things(session: sqlalchemy.orm.session.Session,
                  base_url: str,
                  bearer: BearerToken,
                  delay: float,
                  refresh: bool,
                  item_prefix: str = None) -> None:
    """ Get a list of Metasys Objects we should enrich.

    ATM we can query both the Objects and the Network Device tables. It needs a itemReference if
    we are to do filtering."""

    # Build query.
    query = session.query(MetasysObject)
    if item_prefix:
        query = query.filter(MetasysObject.itemReference.like(item_prefix + '%'))
    if not refresh:  # Disregard successes. Fetch new data:
        query = query.filter(MetasysObject.successes == 0)

    item_objects = query.all()

    entrasso = EntraSSOToken()
    entrasso.login()  # fetches info from environment variables

    total_objects = len(item_objects)
    objects_crawled = 0
    for item_object in item_objects:
        objects_crawled = objects_crawled + 1
        logging.info(f"Enriching object {item_object.id} - {item_object.name} ({objects_crawled}/{total_objects})")
        enrich_single_thing(session, base_url, bearer, item_object, entrasso)
        # Note that item_object has mutated here. error/success and lastSync has updated.
        # So we need to commit.
        session.commit()  # Commit after each object. Might throw.

        time.sleep(delay)


def count_object_by_type(base_url: str, bearer: BearerToken, delay: float, start: int, finish: int):
    """ Used to list counts of different object types in the API. Used during exploration. """
    logging.info(f"Starting count {start} --> {finish} with {delay}s delay on {base_url}")
    logging.info("We ignore types with 0 entries so it'll take some time before you see output.")
    print('type,count', flush=True)
    for type_idx in range(start, finish):
        resp = requests.get(base_url +
                            f"/objects?type={type_idx}",
                            auth=bearer, timeout=REQUESTS_TIMEOUT)
        json_resp = resp.json()
        total = json_resp["total"]
        if total > 0:
            print(f'{type_idx},{total}', flush=True)
        time.sleep(delay)


def _metasysid_to_real_estate(metasysid: str) -> str:
    """Takes something like 'GP-SXD9E-113:SOKP16-NAE4/FCB.434_121-1OU001.VAVmaks4'
    and spits out 'kjorbo' using BUILDING_MAP (dict)

    This is used when we push data into the Bas API.

    """

    try:
        rx = re.compile('^([^:]+):([^-]+)')
        sd, building = rx.findall(metasysid)[0]
    except Exception as e:
        logging.error(f"_metasysid_to_real_estate: Could not make sense of {metasysid}")
        raise ValueError("Regular expression error") from e
    if not building in BUILDING_MAP:
        logging.error(f"Can't find {building} in BUILDING_MAP - please update.")
        return 'ukjent'
    return BUILDING_MAP[building]


def _json_converter(whatever) -> str:
    """Helper to match various types into something that the JSON lib can grok."""
    if isinstance(whatever, datetime):
        return whatever.utcnow().isoformat() + 'Z'  # somewhat of a hack. Forces UTC.
    if isinstance(whatever, uuid.UUID):
        return str(whatever)


@lru_cache(maxsize=256)
def get_type_description(session: sqlalchemy.orm.session.Session, object_type: int) -> str:
    """Returns the string representation of the object type. Note that
    functools will cache the result of this so we don't have to hit
    the database for every lookup. """
    enumset = session.query(EnumSet).filter_by(id=object_type).first()
    if not enumset.description:
        # Note that this will only fire off once per input as the result is cached.
        logging.error(f"No description found for type {object_type}")
        logging.error(f"Make sure you've fetched the enumsets from metasys (508 and 507)")
        sys.exit(1)  # I consider this a fatal error.
    return enumset.description


def b64_encode_response(metasysresp: str) -> str:
    return base64.b64encode(metasysresp.encode('utf8')).decode('utf8')


def push_reponse_to_bas(session: sqlalchemy.orm.session.Session,
                        metasysresp: str, metadata: MetasysObject, entrasso: EntraSSOToken):
    """ Push a single Response from the Metasys API to the Bas API. """
    j = json.loads(metasysresp)
    # Build the DTO useing model (model/bas.py)
    try:
        base_url = os.environ['ENTRAOS_BAS_BASEURL']
    except KeyError:
        logging.error("Environment variable ENTRAOS_BAS_BASEURL is not set")
        sys.exit(1)
    try:
        bas = Bas(
            id=metadata.id,  # id - get from item or metadata
            realEstate=_metasysid_to_real_estate(metadata.itemReference),  # generate from building
            parentId=metadata.parentId,  # from metadata or parse parentUrl
            type=get_type_description(session, metadata.type),  # generate from metadata type - Looks up enumtype.
            discovered=_json_converter(metadata.discovered),  # datetime        # metadata
            lastCrawl=_json_converter(metadata.lastCrawl),  # metadata
            lastError=_json_converter(metadata.lastError),  # metadata
            successes=metadata.successes,  # metadata
            errors=metadata.errors,  # metadata
            response=b64_encode_response(metasysresp),  # generate from response. just b64-encode the string.
            name=metadata.name,  # from item or metadata
            itemReference=metadata.itemReference,  # from item or metadata
            tfm=metadata.name,
            description=j['item']['description']
        )
    except Exception as e:
        logging.error(f"Exception caugh while creating DTO: {e}")
        logging.error("Aborting. Please investigate.")
        sys.exit(1)
    url = f"{base_url}/metadata/bas/realestate/{bas.realEstate}"

    json_data = bas.asDict()
    try:
        resp = requests.post(url,
                             headers={'Content-Type': 'application/json'},
                             json=bas.asDict(), timeout=REQUESTS_TIMEOUT,
                             auth=entrasso)
    except Exception as e:
        logging.error(f'Unknown error while creating/sending requst to Base: {e}')
        sys.exit(1)
    # Bail on error.
    if resp.status_code >= 400:
        logging.error(f'Got error ({resp.status_code}/{resp.reason}) POSTing to {url}')
        logging.error(f'Aborting')
        sys.exit(1)
    logging.info("Object pushed to Bas")


def grab_enumsets(base_url: str,
                  bearer: BearerToken,
                  dbsess: sqlalchemy.orm.session.Session,
                  enumset: int, delay: float) -> None:
    """This function gets invoked when running crawler enumset and it grabs the enumsets.
    These are used to translate the type field into a somewhat meaningful string.
    """
    page = 1
    count = 0
    while True:
        logging.info(f'Getting enumset {enumset}')
        resp = requests.get(base_url + f'/enumSets/{enumset}/members?page={page}&pageSize=1000',
                            auth=bearer, timeout=REQUESTS_TIMEOUT)
        resp.raise_for_status()

        json_response = resp.json()
        for item in json_response['items']:
            enumset_id = item['id']
            description = item['description']
            db_item = EnumSet(id=enumset_id, description=description or "", enumset=enumset)
            logging.debug(f"Adding enumset ID {enumset_id}, description: {description} in set {enumset}")
            dbsess.merge(db_item)
            dbsess.commit()
            count = count + 1

        page = page + 1
        if json_response["next"] is None:  # the last page has a none link to next.
            break
        time.sleep(delay)


#
# Click setup below
#

@click.group()
@click.option('--debug/--no-debug', default=False, help='Set log level to DEBUG.')
def cli(debug):
    """ Crawler CLI for the Metasys API """
    # print(f"Metasys crawler {__version__}")
    if debug:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(level=log_level,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    try:
        load_dotenv()
        logging.info('.env loaded')
    except ModuleNotFoundError:
        logging.warning("Dotenv not found. Assuming the environment is set up.")


@cli.command()
@click.option('--object-type', type=click.INT, required=False,
              help='Only fetch object of type OBJECT-TYPE. If not set then we get all known types.')
def objects(object_type):
    """Get the list of objects and stores them in the database for crawling.
    Pass the object type. This is an INTEGER. If no object type is given
    then the script will grab all know object types.
    """

    # This is the current (Nov 2020) list of types in use I've seen.
    known_types = [129, 130, 135, 137, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151,
                   152, 153, 155, 156, 161, 165, 168, 172, 173, 176, 177, 178, 181, 185, 191,
                   192, 195, 197, 209, 227, 228, 229, 230, 249, 255, 257, 263, 274, 275, 276,
                   277, 278, 286, 290, 292, 326, 327, 328, 329, 336, 337, 338, 340, 342, 343,
                   344, 345, 348, 349, 350, 351, 352, 353, 354, 356, 357, 362, 425, 426, 427,
                   428, 429, 430, 431, 432, 433, 500, 501, 502, 503, 504, 505, 508, 513, 514,
                   515, 516, 517, 519, 544, 599, 600, 601, 602, 603, 604, 606, 608, 613, 651,
                   660, 661, 677, 694, 699, 719, 720, 748, 749, 758, 760, 761, 762, 763, 767,
                   820, 828, 844, 847, 872, 907]

    base_url = os.environ['METASYS_BASEURL']
    username = os.environ['METASYS_USERNAME']
    password = os.environ['METASYS_PASSWORD']
    logging.info(f"Crawling objects with type {object_type}")
    bearer = BearerToken(base_url, username, password)
    dbsess = db_session()
    if object_type:
        get_objects(dbsess, base_url, bearer, object_type, 0.5)
    else:
        for object_type_from_known in known_types:
            get_objects(dbsess, base_url, bearer, object_type_from_known, 0.5)


@cli.command()
@click.option('--item-prefix', type=click.STRING,
              help='itemReference prefix ie something like "GP-SXD9E-113:SOKP22"')
@click.option('--refresh', type=click.BOOL,
              help="The crawler won't refresh existing data unless told to", default=False)
def deep(item_prefix, refresh):
    """Do a deep crawl fetching every object taking the prefix into account. """
    base_url = os.environ['METASYS_BASEURL']
    username = os.environ['METASYS_USERNAME']
    password = os.environ['METASYS_PASSWORD']
    bearer = BearerToken(base_url, username, password)
    session = db_session()
    enrich_things(session, base_url, bearer, 2.0, refresh, item_prefix)


@cli.command()
def count_object_types():
    """Iterate over the various object types in Metasys and show the count.
    Used for exploration. This can be used to populate the known_types
    in the objects() function call above.
    """
    base_url = os.environ['METASYS_BASEURL']
    username = os.environ['METASYS_USERNAME']
    password = os.environ['METASYS_PASSWORD']
    bearer = BearerToken(base_url, username, password)
    count_object_by_type(base_url, bearer, 0.2, 0, 1000)


@cli.command()
@click.option('--enumset', type=click.INT,
              help='grab a specific enumset. Default is to grab 507 and 508.')
def get_enumset(enumset: int = None):
    """Grabs an enumset from metasys and populates the local database with it."""
    base_url = os.environ['METASYS_BASEURL']
    username = os.environ['METASYS_USERNAME']
    password = os.environ['METASYS_PASSWORD']
    bearer = BearerToken(base_url, username, password)
    dbsess = db_session()
    if enumset:
        grab_enumsets(base_url, bearer, dbsess, enumset, 1.0)
    else:
        grab_enumsets(base_url, bearer, dbsess, 507, 1.0)
        grab_enumsets(base_url, bearer, dbsess, 508, 1.0)


# We typically won't be invoked like this, but if we do we set debug=True
# We are typically invoked with "poetry run crawler" which will run the cli()
# function directly.
if __name__ == '__main__':
    cli()
