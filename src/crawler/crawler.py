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
    logging.info(f"Considering item with UUID {obj_id}")

    existing_item = MetasysObject(id=obj_id)
    if existing_item:
        return
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
        logging.info(f"Got a page ({page}) of objects....")
        json = resp.json()
        items = json["items"]
        if len(items) == 0:
            break
        for item in json["items"]:
            insert_item_from_list(session, item, object_type)
        page = page + 1
        time.sleep(1)


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
@click.option('--object-type', default=165, type=click.STRING)
def objects(object_type):
    base_url = os.getenv('METASYS_BASEURL')
    username = os.getenv('METASYS_USERNAME')
    password = os.getenv('METASYS_PASSWORD')
    logging.info(f"Crawling objects with type {type}")
    logging.info("Getting a token")
    bearer = BearerToken(base_url, username, password)
    get_objects(base_url, bearer, object_type)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    cli()
