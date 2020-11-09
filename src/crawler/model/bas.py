import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Bas:
    id: uuid.UUID
    realEstate: str
    parentId: uuid.UUID
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
