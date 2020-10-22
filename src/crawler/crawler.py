""" Crawler for the Metasys API."""
import logging
import os
import time
from datetime import timezone, datetime

import click
import requests
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import MetasysObject, MetasysNetworkDevice, Base
from db.base import get_dsn
from metasysauth.bearer import BearerToken


def db_engine() -> sqlalchemy.engine.Engine:
    """ Acquire a database engine. Mostly used by session.
    Uses the DSN env variable. """
    dsn = get_dsn()
    engine = create_engine(dsn)
    return engine


# Engine default to None. If it isn't set then we set it ourselves.
def db_session(engine: sqlalchemy.engine.Engine = None) -> sqlalchemy.orm.session.Session:
    """ Get a database session. """
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


def enrich_thing(session: sqlalchemy.orm.session.Session,
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

    # if not issubclass(source_class, Base):
    #    raise ValueError('Supplied source_class is not sqlalchemy model class derived from Base')
    if item_prefix:
        item_objects = session.query(source_class) \
            .filter(source_class.itemReference.like(item_prefix + '%')) \
            .all()
    else:
        # Refresh all objects:
        item_objects = session.query(source_class).all()

    print(f"Will crawl {len(item_objects)} objects...")
    for item_object in item_objects:
        print(f"Enriching object {item_object.id}")
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

#
# Click setup below
#

@click.group()
def cli():
    """ Crawler CLI for the Metasys API """
    # print(f"Metasys crawler {__version__}")
    logging.basicConfig(level=logging.INFO)

    try:
        from dotenv import load_dotenv  # pylint: disable=wrong-import-position

        load_dotenv()
        logging.info('.env loaded')
    except ModuleNotFoundError:
        print("Dotenv not found. Ignoring.")


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
    enrich_thing(session, source_class, base_url, bearer, 2.0, item_prefix)


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
    count_object_by_type(base_url, bearer, 0.2 , 0, 2000)

if __name__ == '__main__':
    cli()
