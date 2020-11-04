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
    id = Column(UUID(as_uuid=True), primary_key=True)
    # Not everyone has parents.
    parentId = Column(UUID(as_uuid=True), index=True, nullable=True)
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


class MetasysNetworkDevice(Base):  # pylint: disable=too-few-public-methods
    """ This is where we store the Network Devices we find in the crawl.

    The fields that have nullable=False are the ones written to by the initial crawls. The
    rest are added in the deep crawl."""
    __tablename__ = "metasysCrawlNetworkDevice"
    id = Column(UUID(as_uuid=True), primary_key=True)
    # Note that network device might not have parents so parentID is nullable.
    parentId = Column(UUID(as_uuid=True), index=True, nullable=True)
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
