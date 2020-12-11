""" Dataclass object for the BAS API"""     # pylint: disable=invalid-name

from datetime import datetime


class Bas:
    id: str
    realEstate: str
    parentId: str
    type: str
    discovered: datetime
    lastCrawl: datetime
    lastError: datetime
    successes: int
    errors: int
    response: str
    name: str
    itemReference: str
    tfm: str
    description: str

    def __init__(self, **kwargs):
        # Generic dataclass-like constructor
        self.__dict__.update(kwargs)
