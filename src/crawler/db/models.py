"""Database objects for the crawler. """

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MetasysObject(Base):  # pylint: disable=too-few-public-methods
    """ This is where we store objects from the crawl. The fields that have
    nullable=False are the ones written to by the initial crawls. The rest are added
    in the deep crawl."""
    __tablename__ = "metasysCrawl"
    id = Column(String, primary_key=True)
    # Not everyone has parents.
    parentId = Column(String, index=True, nullable=True)
    type = Column(Integer, index=True, nullable=False)
    discovered = Column(DateTime, nullable=False)
    lastCrawl = Column(DateTime, nullable=True)
    lastError = Column(DateTime, nullable=True)
    successes = Column(Integer, nullable=False, default=0)
    errors = Column(Integer, nullable=False, default=0)
    response = Column(Text, nullable=True)

    # Included for convenience:
    name = Column(String, nullable=True)
    itemReference = Column(String, nullable=True)
    lastSync = Column(DateTime, nullable=True)

    def as_dict(self, excluded_keys: dict = {}) -> dict:
        """ Returns a dict with copies of the data in the object.
        Populate the _excluded_keys to omit
        """

        return dict(
            (key, value)
            for (key, value) in self.__dict__.items()
            if key not in excluded_keys
            )

class MetasysNetworkDevice(Base):  # pylint: disable=too-few-public-methods
    """ This is where we store the Network Devices we find in the crawl.

    The fields that have nullable=False are the ones written to by the initial crawls. The
    rest are added in the deep crawl."""
    __tablename__ = "metasysCrawlNetworkDevice"
    id = Column(String, primary_key=True)
    # Note that network device might not have parents so parentID is nullable.
    parentId = Column(String, index=True, nullable=True)
    discovered = Column(DateTime, nullable=False)
    lastCrawl = Column(DateTime, nullable=True)
    lastError = Column(DateTime, nullable=True)
    successes = Column(Integer, nullable=False, default=0)
    errors = Column(Integer, nullable=False, default=0)
    response = Column(Text, nullable=True)

    # Included for convenience:
    name = Column(String, nullable=True)
    itemReference = Column(String, nullable=True)
#
#

class EnumSet(Base):  # pylint: disable=too-few-public-methods
    """ This is where we store objects from the crawl. The fields that have
    nullable=False are the ones written to by the initial crawls. The rest are added
    in the deep crawl."""
    __tablename__ = "enumSets"
    id = Column(Integer, primary_key=True)
    description = Column(String, nullable=False)
    enumset = Column(Integer, nullable=False)