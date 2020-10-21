# EntraOS Metasys Crawler 
## entraos-metasys-crawler-cli


This is a crawler that fetches data from Metasys and sticks it into a 
relational database.

The goal is to figure out a semantic structure from the graph and the data provided 
by the API so we build a tfm2rec API.


## Installation

This is Python 3 cli application. It uses [Poetry](https://python-poetry.org/) to managed dependencies and runtime.
Please make sure you have poetry installed at this point.

```shell script
git clone ..
cd entraos-metasys-crawler-cli
poetry install
```

## Setting up the environment

Create a .env file containing the following:
 * METASYS_BASEURL - Base URL to the Metasys API, ie http://192.168.63.21/api/v2 or similar
 * METASYS_USERNAME
 * METASYS_PASSWORD
 * DSN - Database connection string, "postgresql://crawler:test4crawl@localhost:5432/metasys_crawler", this is a [libpq](https://www.postgresql.org/docs/11/libpq-connect.html) connection string, not a psycopg2 key/value DSN.

### Setup Postgresql
 * [Postgresql initial setup[(https://docs.boundlessgeo.com/suite/1.1.1/dataadmin/pgGettingStarted/firstconnect.html)

### Create user and database
 
```
sudo -u postgres psql postgres
CREATE USER crawler with password 'test4crawl';
CREATE DATABASE metasys_crawler;
GRANT ALL PRIVILEGES ON DATABASE metasys_crawler TO crawler;
\q
```

Now you can have the crawler create the tables it needs:
```shell script
poetry run alembic upgrade head
```
If the database changes you might need to run this in order to get the
latest database structure.

## Running the tests w/coverage
```
poetry run pytest --cov=crawler
```

## Linting
```
poetry run pylint src
```

## Running the crawler

The crawler has built in help. Just run 
```poetry run crawler```
and it'll show the built in help.

The crawler runs in two phases. First it collects the list of objects.
```
poetry run crawler objects
```

Once it completes you can run the more intrusive crawl:
```
poetry run crawler deep
```
If you wanna do a somewhat more specific crawl you can give a prefix that will limit the crawl to a part of the system, 
based on the itemReference identifier. Do this:
```
poetry run crawler deep --item-prefix GP-SXD9E-113:SOKP22-NAE4/
```
And the crawler will limit the enrichment to items with that prefix (building KP22, substation NAE4).

If you wanna reset the database:
```
poetry run crawler flush
```

### Help?
```shell script
poetry run crawler --help
```
