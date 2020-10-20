""" Crawler for the Metasys API."""
# pylint disable=wrong-import-position
from datetime import timezone, datetime
import sys
import os
import logging
import time

import click
import requests
import sqlalchemy

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from crawler.db.models import MetasysObject, Base
from crawler.metasysauth.bearer import BearerToken


def db_engine() -> sqlalchemy.engine.Engine:
    """ Acquire a database engine. Mostly used by session.
    Uses the DSN env variable. """
    dsn = os.environ['DSN']
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
    return url.split('objects/')[1]


def insert_item_from_list(session, item, object_type):
    """ Insert an item into the database if it doesn't exists. """
    obj_id = item["id"]

    existing_item = MetasysObject(id=obj_id)
    if existing_item:
        logging.info(f"Ignoring {obj_id}")
        return

    logging.info(f"Inserting {obj_id}")
    session.add(MetasysObject(id=obj_id,
                              parentId=get_uuid_from_url(item["parentUrl"]),
                              itemReference=item["itemReference"],
                              name=item["name"],
                              discovered=datetime.now(timezone.utc),
                              type=object_type
                              ))
    session.commit()


def get_objects(base_url: str, bearer: BearerToken, object_type: int):
    """ Get the list of objects from Metasys and store them in the database."""
    session = db_session()
    page = 1
    while True:
        resp = requests.get(base_url +
                            f"/objects?type={object_type}&page={page}&pageSize=100&sort=name",
                            auth=bearer)
        json = resp.json()
        items = json["items"]
        logging.info(f"Working on page ({page} - {len(items)} items")
        if json["next"] is None:  # the last page has a none link to next.
            break
        for item in json["items"]:
            insert_item_from_list(session, item, object_type)
        logging.info(f"Page({page}) complete.")
        page = page + 1
        time.sleep(1)


def enrich_single_object(base_url: str, bearer: BearerToken, item_object: MetasysObject):
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


def enrich_objects(base_url: str, bearer: BearerToken, item_prefix: str):
    """ Get the list of objects we should enrich. """
    session = db_session()
    if item_prefix:
        item_objects = session.query(MetasysObject) \
            .filter(MetasysObject.itemReference.like(item_prefix + '%')) \
            .all()
    else:
        # Refresh all objects:
        item_objects = session.query(MetasysObject).all()

    print(f"Will crawl {len(item_objects)} objects...")
    for item_object in item_objects:
        print(f"Enriching object {item_object.id}")
        enrich_single_object(base_url, bearer, item_object)
        session.commit()  # Commit after each object. Implicit bail out.
        time.sleep(2)


#
# Click setup below
#

@click.group()
def cli():
    """ Main entrypoint for the cli """
    print(f"Metasys crawler {__version__}")


@cli.command()  # @cli, not @click!
def createdb():
    """ Creates a database. We likely wanna use migrations at some point instead. """
    logging.info(f"Creating the database")
    try:
        engine = db_engine()
        Base.metadata.create_all(engine)
    except Exception as e:
        logging.error(f"While creating my tables: {e}")


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
    logging.info(f"Crawling objects with type {type}")
    bearer = BearerToken(base_url, username, password)
    get_objects(base_url, bearer, object_type)


@cli.command()
@click.option('--item-prefix', type=click.STRING)
def deep(item_prefix):
    """Do a deep crawl fetching every object taking the prefix into account. """
    base_url = os.environ['METASYS_BASEURL']
    username = os.environ['METASYS_USERNAME']
    password = os.environ['METASYS_PASSWORD']
    bearer = BearerToken(base_url, username, password)
    enrich_objects(base_url, bearer, item_prefix)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    # Try to load .env. Ignore failures - .env might not be present
    # in production if running in, say, Docker
    try:
        from dotenv import load_dotenv  # pylint: disable=wrong-import-position

        load_dotenv()
        logging.info('.env loaded')
    except ModuleNotFoundError:
        print("Dotenv not found. Ignoring.")

    cli()
