import sqlalchemy
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class MetasysObject(Base):
    __tablename__ = "metasysCrawl"
    id = Column(UUID(as_uuid=True), primary_key=True)
    parentId = Column(UUID(as_uuid=True), index=True, nullable=False)
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
