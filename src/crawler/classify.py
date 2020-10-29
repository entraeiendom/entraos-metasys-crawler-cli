import json
import os
import abc
import time
import logging
import re
from dataclasses import dataclass

from functools import lru_cache
from typing import Optional

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv

from db.models import MetasysObject, MetasysNetworkDevice, Base
from db.base import get_dsn


@dataclass
class Guess:
    real_estate: str
    building: str
    floor: int  # todo: should be string.
    type: str  # outlet, heating, ventilation, lighting
    room: str
    sd: str
    nae: str
    obj: str
    confidence: float


class Sensor:
    resp: dict
    type: int
    dbo: MetasysObject

    def __init__(self, dbo: MetasysObject):
        resp = dbo.response
        self.resp = json.loads(resp)
        self.type = dbo.type
        self.dbo = dbo


class ParserRule:
    @abc.abstractmethod
    def process(self, sensor: Sensor) -> Guess:
        pass


class Parser:
    rules: list

    def __init__(self):
        self.rules = []

    def add_rule(self, rule):
        self.rules.append(rule)

    def __collate(self, guesses):
        """ Take the guesses and collate them into a final guess. """

        # First create an dict and set all the vales to None.
        collated_guess = {}
        for key in Guess.__dataclass_fields__.keys():
            collated_guess[key] = None

        # then we iterate over the fields in the dataclass.
        for key in Guess.__dataclass_fields__.keys():
            if key == 'confidence':
                continue
            highest_confidence = 0.0
            # Then we iterate over all the guesses and keep the ones with the highest confidence.
            for guess in guesses:
                if guess.__getattribute__(key) and guess.__getattribute__('confidence') > highest_confidence:
                    collated_guess[key] = guess.__getattribute__(key)
                    highest_confidence = guess.__getattribute__('confidence')
        collated_guess = Guess(**collated_guess)
        return collated_guess

    def parse(self, s: Sensor) -> list[Guess]:
        guesses = []
        for rule in self.rules:
            guess = rule.process(s)
            if guess:
                guesses.append(guess)
        return self.__collate(guesses)
        # At this point we have 0 or more guesses.
        # Now we wanna collate them into a single response, weighing the various guess against each other.


class ItemRefParser(ParserRule):
    rx: re.Pattern

    def __init__(self):
        super().__init__()
        self.rx = re.compile('([^:]+):([^-]+)-(NAE\d+)/(.*)')

    def process(self, sensor: Sensor) -> Guess:
        try:
            sd, building, nae, obj = self.rx.findall(sensor.resp['item']['itemReference'])[0]
            guess = Guess(sd=sd, building=building, nae=nae, obj=obj,
                          real_estate=None, floor=None, type=None, room=None,
                          confidence=1.0)
            return guess
        except KeyError:  # The JSON object might be invalid or missing.
            return None


class FloorGuesser1(ParserRule):
    rx: re.Pattern

    def __init__(self):
        super().__init__()
        self.rx = re.compile('(\d|U|u).?\s+(etg|etage|etasje)', re.IGNORECASE)

    def __process_string(self, target: str) -> int:
        floor = None

        res = self.rx.findall(target)
        if res:
            floor_s = res[0][0]
            if floor_s[0] == 'u' or floor_s[0] == 'U':
                floor = -1
            else:
                try:
                    floor = int(floor_s)
                except Exception as e:
                    print(f'Cant make int out of "{floor_s}"')
        return floor

    def process(self, sensor: Sensor) -> Optional[Guess]:
        floor1 = self.__process_string(sensor.resp['item']['itemReference'])
        floor2 = self.__process_string(sensor.resp['item']['description'])
        if floor1 or floor2:
            guess = Guess(sd=None, building=None, nae=None, obj=None,
                          real_estate=None, floor=floor1 or floor2,
                          type=None, room=None,
                          confidence=0.65)
            return guess
        else:
            return None


class FloorGuesser2(ParserRule):
    rx: re.Pattern

    def __init__(self):
        super().__init__()
        self.rx = re.compile(re.compile('1([HU]\d+)'))

    def __process_string(self, target: str) -> int:
        floor = None
        res = self.rx.findall(target)
        if res:
            floor_s = res[0]
            if floor_s[0] == 'H':
                floor = int(floor_s[1:])
            elif floor_s[0] == 'U':
                floor = -int(floor_s[1:])
            else:
                assert "Brain damage!"
            return floor
        else:
            return None

    def process(self, sensor: Sensor) -> Optional[Guess]:
        floor1 = self.__process_string(sensor.resp['item']['itemReference'])
        floor2 = self.__process_string(sensor.resp['item']['description'])
        if floor1 or floor2:
            guess = Guess(sd=None, building=None, nae=None, obj=None,
                          real_estate=None, floor=floor1 or floor2,
                          type=None, room=None,
                          confidence=0.45)
            return guess
        else:
            return None


class RoomGuesser1(ParserRule):
    rx: re.Pattern

    def __init__(self):
        super().__init__()
        self.rx = re.compile(re.compile('Rom\s+(\d+)\D?', re.IGNORECASE))

    def __process(self, target: str) -> str:
        room = None
        res = self.rx.findall(target)
        if res:
            room = res[0]
            return room
        else:
            return None

    def process(self, sensor: Sensor) -> Optional[Guess]:
        room = self.__process(sensor.resp['item']['description'])
        if room:
            guess = Guess(sd=None, building=None, nae=None, obj=None,
                          real_estate=None, floor=None,
                          type=None, room=room,
                          confidence=0.85)
            return guess
        else:
            return None


class TemperatureDetector1(ParserRule):

    def process(self, sensor: Sensor) -> Optional[Guess]:
        try:
            unit = sensor.resp['item']['units']
            if unit == 'unitEnumSet.degC':
                guess = Guess(sd=None, building=None, nae=None, obj=None,
                              real_estate=None, floor=None,
                              type='temp', room=None,
                              confidence=0.95)
                return guess
        except KeyError:
            return None

        return None


class Co2Detector1(ParserRule):
    """ Detect if this is a CO2 sensor"""
    rx: re.Pattern

    def __init__(self):
        super().__init__()
        self.rx = re.compile(re.compile('co2', re.IGNORECASE))

    def process(self, sensor: Sensor) -> Optional[Guess]:
        try:
            judgement = None
            confidence = 0.0
            desc = sensor.resp['item']['description']
            units = sensor.resp['item']['units']
            if self.rx.match(desc):
                judgement = 'co2'
                confidence = 0.7
            if units == 'unitEnumSet.partsPerMillion':
                judgement = 'co2'
                confidence += 0.2
            if judgement:
                guess = Guess(sd=None, building=None, nae=None, obj=None,
                              real_estate=None, floor=None,
                              type=judgement, room=None,
                              confidence=confidence)
                return guess
        except KeyError:
            return None

        return None  # likely not reached.


def db_engine() -> sqlalchemy.engine.Engine:
    """ Acquire a database engine. Mostly used by session.
    Uses the DSN env variable. """
    dsn = get_dsn()
    engine = create_engine(dsn)
    return engine


def db_session(engine: sqlalchemy.engine.Engine = None) -> sqlalchemy.orm.session.Session:
    """ Get a database session. """
    # Engine default to None. If it isn't set then we set it ourselves.
    if not engine:
        engine = db_engine()
    Session = sessionmaker(bind=engine)  # pylint: disable=invalid-name
    session = Session()
    return session


@lru_cache(maxsize=32)
def main_rx():
    """([^:]+):([^-]+)-(NAE\d+)/(.*)"""
    return re.compile('([^:]+):([^-]+)-(NAE\d+)/(.*)')


def process_items():
    session = db_session()

    # Pick out what items we wanna apply the guesswork on:
    build_query = session.query(MetasysObject).filter(
        MetasysObject.itemReference.like('GP-SXD9E-113:SOKP16-NAE4/FCB.434%'))
    # build_query = build_query.filter(MetasysObject.itemReference.notlike('%Programming%'))
    # build_query = build_query.filter(MetasysObject.name.notlike('Trend%'))

    build_query = build_query.all()
    print(f'{len(build_query)} items to be considered.')

    parser = Parser()
    parser.add_rule(ItemRefParser())
    parser.add_rule(FloorGuesser1())
    parser.add_rule(FloorGuesser2())
    parser.add_rule(RoomGuesser1())
    parser.add_rule(TemperatureDetector1())
    parser.add_rule(Co2Detector1())

    for item in build_query:
        sensor = Sensor(item)
        print(f'Processing sensor: {sensor.dbo.itemReference}')
        guess = parser.parse(sensor)

        print(guess)


def main():
    load_dotenv()
    process_items()


if __name__ == '__main__':
    main()
