""" Dataclass object for the BAS API"""     # pylint: disable=invalid-name

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass
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
