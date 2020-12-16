# EntraOS Metasys Crawler 
## entraos-metasys-crawler-cli


This is a crawler that fetches data from Metasys and sticks it into a 
relational database - Sqlite. It can then be pushed into Bas, a proprietary API.

This is written for Entra but might provide a basis for a similar dataflow for others as well.


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


We use alembic for schema creation and migrations.

Now you can have the crawler create the database tables it needs:
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

The crawler accepts a global flag `--debug` which will print a bunch
of stuff to the console.

The crawler runs in two phases. First it collects the list of objects.
```
poetry run crawler objects
```

Once it completes you can run the more intrusive crawl. This will push data to Bas as you go along.
```
poetry run crawler deep
```
If you wanna do a somewhat more specific crawl you can give a prefix that will limit the crawl to a part of the system, 
based on the itemReference identifier. Do this:
```
poetry run crawler deep --item-prefix GP-SXD9E-113:SOKP22-NAE4/
```
And the crawler will limit the enrichment to items with that prefix (building KP22, substation NAE4).

### Help?
```shell script
poetry run crawler --help
```

## How to setup your dev environment

I use Pycharm for this. 

Remember to set the "src" folder as "source root" so Pycharm groks the imports.

### Prerequisites
 * Pycharm (or IntelliJ with the Python plugin)
 * Poetry plugin
 * Python 3.8 or later
 * Python Poetry installed globally
 
Clone the project. "poetry install" to install dependencies.
Open the project. Set interpreter. Add interpreter. 
Choose poetry. Existing environment. 
Pick the venv that poetry just created.

"Edit configurations". Script path is the path to src/crawler/crawler.py.
Add parameters depending on what you want the crawler to do.

Create an ".env" file.
Now you should be able to run the crawler through pycharm and debug it.

Let's get the tests running in pycharm.
Preferences. Set pytest as the testing tool. Create a configuration
where you set the target to "tests", this should be enough to make
pycharm grok the tests.

## Bugs and weird stuff

I'm not entirely happy with the way the source layout works. I'm adding to the PYTHONPATH
to fix this but this upsets Pycharm a bit (things turn red). 
