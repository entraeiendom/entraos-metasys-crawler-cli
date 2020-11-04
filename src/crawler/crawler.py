""" Crawler for the Metasys API."""
import base64
import json
import os
import re
import time
import uuid
from datetime import timezone, datetime
import logging

import click
import requests
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Editable
# sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), 'src/crawler')))

from db.models import MetasysObject, MetasysNetworkDevice, Base
from db.base import get_dsn
from metasysauth.bearer import BearerToken
from model.bas import Bas


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
                            auth=bearer)
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


def enrich_single_thing(base_url: str, bearer: BearerToken, item_object: MetasysObject):
    """ Fetch a single object from Metasys and store the response. """
    try:
        resp = requests.get(base_url + f"/objects/{item_object.id}", auth=bearer)
        item_object.lastCrawl = datetime.now(timezone.utc)
        item_object.response = resp.text
        item_object.successes += 1
    except requests.exceptions.RequestException as requests_exception:
        item_object.lastError = datetime.now(timezone.utc)
        item_object.errors += 1
        logging.error(requests_exception)


def enrich_things(session: sqlalchemy.orm.session.Session,
                  source_class: Base,
                  base_url: str,
                  bearer: BearerToken,
                  delay: float,
                  item_prefix: str = None) -> None:
    """ Get a list of "things" we should enrich. Things can be anything with a UUID
    available through the /objects endpoint. Supply the class from the model of the thing you
    want to enrich.
    ATM we can query both the Objects and the Network Device tables. It needs a itemReference if
    we are to do filtering."""

    only_new_items = True

    # We could perhaps  check source_class here, but that isn't pythonic. 🦆 ftw!

    build_query = session.query(source_class)

    if item_prefix:
        build_query = build_query.filter(source_class.itemReference.like(item_prefix + '%'))

    # Filter out stuff and don't like:
    build_query = build_query.filter(source_class.itemReference.notlike('%Programming%'))
    build_query = build_query.filter(source_class.name.notlike('Trend%'))
    build_query = build_query.filter(source_class.name.notlike('%Alarm%'))

    if only_new_items:
        build_query = build_query.filter(source_class.successes == 0)

    item_objects = build_query.all()

    logging.debug(f"Will crawl {len(item_objects)} objects...")
    for item_object in item_objects:
        logging.info(f"Enriching object {item_object.id} - {item_object.name}")
        enrich_single_thing(base_url, bearer, item_object)
        session.commit()  # Commit after each object. Implicit bail out.
        time.sleep(delay)


def insert_network_device_from_list(session, item):
    """ Insert an network device into the database if it doesn't exists. """
    obj_id = item["id"]

    existing_item = session.query(MetasysNetworkDevice).filter_by(id=obj_id).first()
    if existing_item and existing_item.discovered:
        logging.info(f"Ignoring {obj_id}")
        return

    parent_url = item["parentUrl"]
    if parent_url:
        parent_id = get_uuid_from_url(item["parentUrl"])
    else:
        parent_id = None

    logging.info(f"Inserting {obj_id}")
    session.add(MetasysNetworkDevice(id=obj_id,
                                     parentId=parent_id,
                                     itemReference=item["itemReference"],
                                     name=item["name"],
                                     discovered=datetime.now(timezone.utc)
                                     ))
    session.commit()


def get_network_devices(session: sqlalchemy.orm.session.Session,
                        base_url: str,
                        bearer: BearerToken,
                        delay: float):
    """ Get the list of objects from Metasys and store them in the database."""
    page = 1
    while True:
        resp = requests.get(base_url +
                            f"/networkDevices?page={page}&pageSize=100&sort=name",
                            auth=bearer)
        json_response = resp.json()
        items = json_response["items"]
        logging.info(f"Working on page ({page} - {len(items)} items")
        for item in json_response["items"]:
            insert_network_device_from_list(session, item)
        logging.info(f"Page({page}) complete.")
        page = page + 1
        if json_response["next"] is None:  # the last page has a none link to next.
            break
        time.sleep(delay)


def count_object_by_type(base_url: str, bearer: BearerToken, delay: float, start: int, finish: int):
    """ Used to list counts of different object types in the API"""
    logging.info(f"Starting count {start} --> {finish} with {delay}s delay on {base_url}")
    logging.info("We ignore types with 0 entries so it'll take some time before you see output.")
    print('type,count', flush=True)
    for type_idx in range(start, finish):
        resp = requests.get(base_url +
                            f"/objects?type={type_idx}",
                            auth=bearer)
        json_resp = resp.json()
        total = json_resp["total"]
        if total > 0:
            print(f'{type_idx},{total}', flush=True)
        time.sleep(delay)


def __metasysid_to_real_estate(metasysid: str) -> str:
    """Takes something like 'GP-SXD9E-113:SOKP16-NAE4/FCB.434_121-1OU001.VAVmaks4' and spits out 'kjorbo'"""

    buildingmap = {
        'SOKP16': 'kjorbo'
    }
    try:
        rx = re.compile('^([^:]+):([^-]+)')
        sd, building = rx.findall(metasysid)[0]
    except Exception as e:
        logging.error(f"Could not make sense of {metasysid}")
        raise ValueError("Regular expression error")
    return buildingmap[building]


def __json_converter(whatever):
    """Helper to match various types into something that the JSON lib can grok."""
    if isinstance(whatever, datetime):
        return whatever.utcnow().isoformat() + 'Z'  # somewhat of a hack.
    if isinstance(whatever, uuid.UUID):
        return str(whatever)


def push_object(session: sqlalchemy.orm.session.Session,
                delay: float,
                item_prefix: str = None) -> None:
    """ Push things into the cloud."""

    build_query = session.query(MetasysObject)

    # If we wanna qualify the query further do it like this:
    if item_prefix:
        build_query = build_query.filter(MetasysObject.itemReference.like(item_prefix + '%'))

    for item in build_query.all():
        logging.debug(f'Processing {item.id}')
        if item.successes == 0:
            logging.debug(f'Ignoring item {item.id} which has not been crawled')
            continue
        if item.response is None:
            logging.debug(f'Ignoring item {item.id} which has no response recorded')
            continue

        # Copy the DBO into a dict, removing stuff we don't want.
        item_as_dict = item.as_dict({'_sa_instance_state': True, 'lastSync': True})

        # Parse the response. We need to make sure it looks ok and we wanna get some data from it.
        json_resp_dict = json.loads(item_as_dict['response'])
        if 'message' in json_resp_dict:
            logging.warning(f'JSON response {item.id} has a message. Ignoring. Message: "{json_resp_dict["message"]}"')
            continue
        #

        # base64-encode the response so it can be represented as a string in the JSON we POST.

        response_encoded = item_as_dict['response'].encode('utf8')
        json_str = base64.b64encode(response_encoded).decode('utf8')
        item_as_dict['response'] = json_str

        item_as_dict['realEstate'] = __metasysid_to_real_estate(item.itemReference)
        item_as_dict['tfm'] = None  # Todo: Don't know what to do with this one. We don't have TFM.
        item_as_dict['description'] = json_resp_dict['item']['description']
        realestate_id = item_as_dict['realEstate']

        # Dict --> JSON with customer encoder:
        # requests doesn't support supplying an encoder so we have to do this in two steps.
        json_data = json.dumps(item_as_dict, default=__json_converter)

        resp = requests.post(f'http://localhost:8889/metadata/bas/realestate/{realestate_id}',
                             headers={'Content-Type': 'application/json'},
                             data=json_data)

        resp.raise_for_status()  # Bail on error.
        logging.debug(f'{item.id} uploaded')

        # Not catching errors here. Abort on failure.
        item.lastSync = datetime.now(tz=timezone.utc)
        session.commit()
        # print(item)
        # print(bas)


#
# Click setup below
#

@click.group()
@click.option('--debug/--no-debug', default=False)
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
        from dotenv import load_dotenv  # pylint: disable=wrong-import-position
        load_dotenv()
        logging.info('.env loaded')
    except ModuleNotFoundError:
        logging.warning("Dotenv not found. Assuming the environment is set up.")


@cli.command()
def flush():
    """ Deletes everything from the database. """
    logging.info("Flushing the database")
    session = db_session()
    no_of_rows = session.query(MetasysObject).delete()
    logging.info(f"Deleted {no_of_rows} objects from {MetasysObject.__tablename__}")


@cli.command()
@click.option('--object-type', default=165, type=click.INT)
def objects(object_type):
    """Get the list of objects and stores them in the database for crawling."""
    base_url = os.environ['METASYS_BASEURL']
    username = os.environ['METASYS_USERNAME']
    password = os.environ['METASYS_PASSWORD']
    logging.info(f"Crawling objects with type {object_type}")
    bearer = BearerToken(base_url, username, password)
    dbsess = db_session()
    get_objects(dbsess, base_url, bearer, object_type, 0.5)


@cli.command()
@click.option('--item-prefix', type=click.STRING)
@click.option('--source', required=True,
              type=click.Choice(['objects', 'network-devices'],
                                case_sensitive=False))
def deep(item_prefix, source):
    """Do a deep crawl fetching every object taking the prefix into account. """
    base_url = os.environ['METASYS_BASEURL']
    username = os.environ['METASYS_USERNAME']
    password = os.environ['METASYS_PASSWORD']
    bearer = BearerToken(base_url, username, password)
    session = db_session()
    if source == 'objects':
        source_class = MetasysObject
    else:
        source_class = MetasysNetworkDevice
    enrich_things(session, source_class, base_url, bearer, 2.0, item_prefix)


@cli.command()
def network_devices():
    """Get the list of networking devices and store them in the database."""
    base_url = os.environ['METASYS_BASEURL']
    username = os.environ['METASYS_USERNAME']
    password = os.environ['METASYS_PASSWORD']
    logging.info(f"Crawling objects with type {type}")
    bearer = BearerToken(base_url, username, password)
    dbsess = db_session()
    get_network_devices(dbsess, base_url, bearer, 1.0)


@cli.command()
def count_object_types():
    """Iterate over the various object types and show the count.
    Used for exploration.
    """
    base_url = os.environ['METASYS_BASEURL']
    username = os.environ['METASYS_USERNAME']
    password = os.environ['METASYS_PASSWORD']
    bearer = BearerToken(base_url, username, password)
    count_object_by_type(base_url, bearer, 0.2, 0, 2000)


@cli.command()
@click.option('--item-prefix', type=click.STRING)
def push(item_prefix):
    """Push cralwer data to the cloud."""
    dbsess = db_session()

    push_object(dbsess, 0.0, item_prefix)


if __name__ == '__main__':
    cli()
