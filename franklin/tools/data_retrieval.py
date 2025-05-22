"""Library of tools to be provided to the model and provide the basis for solutions."""

import logging
from pathlib import Path

import pandas as pd
from rich.logging import RichHandler

from franklin.exceptions import (
    InvalidCountryCodeError,
    InvalidCountryNameError,
    InvalidIndicatorCodeError,
    InvalidIndicatorNameError,
    InvalidRegionNameError,
    NoDataAvailableError,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    datefmt='[%X]',
    handlers=[RichHandler(rich_tracebacks=True)],
)


def search_for_indicator_codes(keywords: list[str]) -> list[str]:
    """Search the database of indicators for codes and names that match the keywords.

    Args:
        keywords: A list of keywords to search for.

    Returns:
        A list of indicator codes that match the keywords.

    """
    data = pd.read_csv(Path('resources', 'wdi.csv'))
    data['name_lower'] = data['name'].str.lower()
    keywords = [keyword.lower() for keyword in keywords]

    filtered = data[data['name_lower'].str.contains('|'.join(keywords))]
    return filtered[['id', 'name']].to_dict(orient='records')


def get_country_code_from_name(country_name: str) -> str:
    """Get the three-letter country code from a country name.

    Args:
        country_name: The name of the country to get the code for.

    Returns:
        The three-letter country code.

    """
    data = pd.read_csv(Path('resources', 'iso_3166.csv'))
    try:
        return data[data['country_name'] == country_name]['country_code'].to_list()[0]
    except IndexError as e:
        raise InvalidCountryNameError(country_name) from e


def get_indicator_code_from_name(indicator_name: str) -> str:
    """Get the indicator code from an indicator name.

    Args:
        indicator_name: The name of the indicator to get the code for.

    Returns:
        The indicator code.

    """
    data = pd.read_csv(Path('resources', 'wdi.csv'))
    try:
        return data[data['name'] == indicator_name.strip()]['id'].to_list()[0]
    except IndexError as e:
        raise InvalidIndicatorNameError(indicator_name) from e


def get_country_codes_in_region(region_name: str) -> list[str]:
    """Get the list of country codes in a given region.

    Args:
        region_name: The region to get the countries for.

    Returns:
        A list of countries in the region as three-letter country codes.

    """
    data = pd.read_csv(Path('resources', 'iso_3166.csv'))

    if region_name not in data['region'].tolist():
        raise InvalidRegionNameError(region_name)

    return data[data['region'] == region_name]['country_code'].tolist()


def retrieve_value(country_code: str, indicator_code: str, year: str) -> float | str | None:
    """Return the value of an indicator for a country at a given year.

    Args:
        country_code: The three-letter country code to look up the indicator for.
        indicator_code: The indicator code to look up.
        year: The year to look up the indicator for.

    Returns:
        The value of the property for the subject at the given year.

    Raises:
        InvalidCountryCodeError: If the country code is not valid.
        InvalidIndicatorCodeError: If the file for the indicator code does not exist.

    """
    # Check country code is valid
    data = pd.read_csv(Path('resources', 'iso_3166.csv'))
    if country_code not in data['country_code'].tolist():
        raise InvalidCountryCodeError(country_code)

    try:
        data = pd.read_csv(
            Path('resources', 'wdi', f'{indicator_code}.csv'),
            index_col='country_code',
        )
    except FileNotFoundError as e:
        raise InvalidIndicatorCodeError(indicator_code) from e

    try:
        value = data.loc[country_code, year]
    except KeyError as e:
        raise NoDataAvailableError(
            {
                'country_code': country_code,
                'indicator_code': indicator_code,
                'year': year,
            }
        ) from e

    if pd.isna(value):
        return None

    return float(value)
    # return {'subject': country_code, 'property': indicator_code, 'object': float(value), 'time': year}


if __name__ == '__main__':
    print('\n=== Search for Indicator Codes ===')
    print('search_for_indicator_codes(["GDP", "growth"])')
    print('Result:', search_for_indicator_codes(['GDP', 'growth']))

    print('\n=== Get Country Code from Name ===')
    print('get_country_code_from_name("Comoros")')
    print('Result:', get_country_code_from_name('Comoros'))

    print('\n=== Get Indicator Code from Name ===')
    print('get_indicator_code_from_name("Revenue, excluding grants (% of GDP)")')
    print('Result:', get_indicator_code_from_name('Revenue, excluding grants (% of GDP)'))

    print('\n=== Get Country Codes in Region ===')
    print('get_country_codes_in_region("Eastern Europe")')
    print('Result:', get_country_codes_in_region('Eastern Europe'))
