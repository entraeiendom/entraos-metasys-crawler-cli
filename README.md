# EntraOS Metasys Crawler 
## entraos-metasys-crawler-cli


This is a crawler that fetches data from Metasys and sticks it into a 
relational database.

The goal is to figure out a semantic structure from the graph and the data provided 
by the API so we build a tfm2rec API.


## Installation

This is Python 3 cli application. It uses [Poetry](https://python-poetry.org/) to managed dependencies and runtime.

```shell script
git clone ..
poetry install
```

## Setting up the environment

Create a .env file containing the following:
 * BASEURL - Base URL to the Metasys API, ie http://192.168.63.21/api/v2 or similar
 * USERNAME
 * PASSWORD
 * DSN - Database connection string
 
Now you can have the crawler create the tables it needs:
```shell script
poetry run crawler createdb
```
 
## Running the crawler

The crawler runs in two phases. First it collects the list of objects.
```
poetry run crawler objects
```

Once it completes you can run the more intrusive crawl:
```
poetry run crawler deep
```

If you wanna reset the database:
```
poetry run crawler flush
```

### Help?
```shell script
poetry run crawler --help
```