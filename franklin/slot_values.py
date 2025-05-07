"""Module containing types of slots and their values."""

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO)


class Slot:
    """Base class for slot values."""

    DATA_PATH = Path('resources')
    WDI_IND_DIR = Path('resources', 'wdi')

    @staticmethod
    def read_csv_file(file_path: Path, column_name: str) -> list[str]:
        """Read a CSV file and return the unique values in a column."""
        try:
            df = pd.read_csv(file_path)
            return df[column_name].dropna().unique().tolist()
        except FileNotFoundError:
            logging.exception(f'File not found: {file_path}')
            raise

    @classmethod
    def get_values(cls) -> list[str]:
        """Return the allowed values for the slot."""
        raise NotImplementedError('Subclasses should implement this method.')


class Subject(Slot):
    """Class to manage subject slot values."""

    @classmethod
    def get_values(cls) -> list[str]:
        """Return all subjects."""
        return cls.read_csv_file(cls.DATA_PATH / 'iso_3166.csv', 'country_code')


class SubjectSet(Slot):
    """Class to manage subject set slot values."""

    @classmethod
    def get_values(cls) -> list[str]:
        """Return all unique subject sets."""
        return cls.read_csv_file(cls.DATA_PATH / 'iso_3166.csv', 'region')


class Property(Slot):
    """Class to manage property slot values."""

    @classmethod
    def get_values(
        cls,
    ) -> list[str]:
        """Return all unique properties."""
        return cls.read_csv_file(cls.DATA_PATH / 'wdi.csv', 'id')


class Number(Slot):
    """Class to manage number slot values.

    Used in questions which require getting the 'top or bottom n' countries, or for getting the
    country in the n-th position.
    """

    # We choose 2-5 as 5 is the smallest number of countries in a sub-region, and 1 is trivial.
    @staticmethod
    def get_values() -> list[str]:
        """Return numbers 2-5."""
        return [str(i) for i in range(2, 6)]


class NaryOperator(Slot):
    """Class to manage n-ary operator slot values."""

    @staticmethod
    def get_values() -> list[str]:
        """Return comparison operations."""
        return ['highest', 'lowest']


class BinaryOperator(Slot):
    """Class to manage binary operator slot values."""

    @staticmethod
    def get_values() -> list[str]:
        """Return binary comparison operations."""
        return ['higher', 'lower']


class AggregationOperator(Slot):
    """Class to manage aggregation operator slot values."""

    @staticmethod
    def get_values() -> list[str]:
        """Return aggregation operations."""
        return ['total', 'mean', 'median']


class Time(Slot):
    """Class to manage time slot values."""

    @staticmethod
    def get_current_year() -> int:
        """Return current year."""
        return datetime.now().year

    @staticmethod
    def get_values() -> list[str]:
        """Return past years."""
        max_year = 2023
        return [f'{year}' for year in range(max_year - 20, max_year)]


if __name__ == '__main__':
    print(Subject.get_values())
    print(SubjectSet.get_values())
    print(Property.get_values())
    print(NaryOperator.get_values())
    print(BinaryOperator.get_values())
    print(AggregationOperator.get_values())
    print(Time.get_current_year())
    print(Time.get_values())
