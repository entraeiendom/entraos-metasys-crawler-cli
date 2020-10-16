from datetime import timezone, datetime
import sys
import os
import logging
import time

import click
import requests

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Local modules:
# I wish poetry would manage the path automagically
sys.path.append("src/crawler")

from db.models import MetasysObject, Base
from metasysauth.bearer import BearerToken

__version__ = '0.1.0'

# Try to load .env. Ignore failures - .env might not be present in production if running in, say, Docker
try:
    from dotenv import load_dotenv

    load_dotenv()
    print('.env loaded')
except ModuleNotFoundError:
    print("Dotenv not found. Ignoring.")


def db_engine():
    dsn = os.getenv('DSN')
    engine = create_engine(dsn)
    return engine


def db_session(engine=db_engine()):
    Session = sessionmaker(bind=engine)
    session = Session()
    return session


def get_uuid_from_url(url: str) -> str:
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
    session = db_session()
    page = 1
    while True:
        resp = requests.get(base_url + f"/objects?type={object_type}&page={page}&pageSize=100&sort=name", auth=bearer)
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


def enrich_single_object(base_url: str, bearer: BearerToken, object: MetasysObject):
    try:
        resp = requests.get(base_url + f"/objects/{object.id}", auth=bearer)
        object.lastCrawl = datetime.now(timezone.utc)
        object.response = resp.text
        object.successes += 1
    except Exception as e:
        object.lastError = datetime.now(timezone.utc)
        object.errors += 1


def enrich_objects(base_url: str, bearer: BearerToken, item_prefix: str):
    session = db_session()
    objects = session.query(MetasysObject).filter(MetasysObject.itemReference.like(item_prefix + '%')).all()
    print(f"Will crawl {len(objects)} objects...")
    for object in objects:
        print(f"Enriching object {object.id}")
        enrich_single_object(base_url, bearer, object)
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
    logging.info(f"Creating the database")
    try:
        engine = db_engine()
        Base.metadata.create_all(engine)
    except Exception as e:
        logging.error(f"While creating my tables: {e}")


@cli.command()
def flush():
    logging.info("Flushing the database")
    session = db_session()
    no_of_rows = session.query(MetasysObject).delete()
    logging.info(f"Deleted {no_of_rows} objects from {MetasysObject.__tablename__}")


@cli.command()
@click.option('--object-type', default=165, type=click.INT)
def objects(object_type):
    base_url = os.getenv('METASYS_BASEURL')
    username = os.getenv('METASYS_USERNAME')
    password = os.getenv('METASYS_PASSWORD')
    logging.info(f"Crawling objects with type {type}")
    bearer = BearerToken(base_url, username, password)
    get_objects(base_url, bearer, object_type)


@cli.command()
@click.option('--item-prefix', type=click.STRING)
def deep(item_prefix):
    base_url = os.getenv('METASYS_BASEURL')
    username = os.getenv('METASYS_USERNAME')
    password = os.getenv('METASYS_PASSWORD')
    bearer = BearerToken(base_url, username, password)
    enrich_objects(base_url, bearer, item_prefix)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    cli()
