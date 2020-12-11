""" Dataclass object for the BAS API"""     # pylint: disable=invalid-name

from datetime import datetime


class Bas:
    id: str      # id - get from item or metadata
    realEstate: str  # generate from building
    parentId: str   # from metadata or parse parentUrl
    type: str       # generate from metadata type.
    discovered: datetime    # metadata
    lastCrawl: datetime     # metadata
    lastError: datetime     # metadata
    successes: int          # metadata
    errors: int             # metadata
    response: str           # generate from response. just b64-encode the string.
    name: str               # from item or metadata
    itemReference: str      # from item or metadata
    tfm: str                # item->objectname
    description: str        # item->descrition

    def __init__(self, **kwargs):
        # Generic dataclass-like constructor
        self.__dict__.update(kwargs)

    def asDict(self) -> dict:
        return self.__dict__
