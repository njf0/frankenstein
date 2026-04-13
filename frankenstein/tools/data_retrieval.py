"""Data-retrieval tools used by Frankenstein question answering workflows."""

import ast
from pathlib import Path

import pandas as pd

from frankenstein.exceptions import (
    InvalidCountryCodeError,
    InvalidCountryNameError,
    InvalidIndicatorCodeError,
    InvalidIndicatorNameError,
    InvalidRegionNameError,
    NoDataAvailableError,
)

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent.parent
RESOURCES_DIR = PROJECT_ROOT / 'resources'


def search_for_indicator_names(
    keywords: list[str] | str,
) -> list[dict]:
    """Retrieve indicator names and descriptions that match the given keywords.

    Parameters
    ----------
    keywords : list[str] | str
        A list of keywords or a string to search for.

    Returns
    -------
    list[dict]
        A list of dictionaries containing the indicator names and descriptions that match the keywords.

    """
    indicator_key = pd.read_json(RESOURCES_DIR / 'indicator_paraphrases.json')
    indicator_key['original_name'] = indicator_key['name']
    indicator_key['name'] = indicator_key['name'].str.lower()
    indicator_key = indicator_key.drop('paraphrase', axis=1)
    indicator_key = indicator_key.rename(
        columns={
            'original_name': 'indicator_name',
            'description': 'indicator_description',
        }
    )
    indicator_key = indicator_key.to_dict(orient='records')

    def clean_dict(indicators: list[dict]) -> list[dict]:
        """Remove internal fields from matched indicator records.

        Parameters
        ----------
        indicators : list[dict]
            Raw indicator records.

        Returns
        -------
        list[dict]
            Indicator records containing only public-facing fields.

        """
        cleaned_dict = []
        for indicator in indicators:
            cleaned_indicator = {k: v for k, v in indicator.items() if k in ['indicator_name', 'indicator_description']}
            # cleaned_indicator['indicator_name'] = cleaned_indicator.pop('original_name')
            # cleaned_indicator['indicator_description'] = cleaned_indicator.pop('description', '')
            cleaned_dict.append(cleaned_indicator)
        return cleaned_dict

    if isinstance(keywords, str):
        # First check for exact match on original name
        result = [item for item in indicator_key if item['name'] == keywords]
        if result:
            return clean_dict(result)

        # Otherwise, treat as a string to search for
        try:
            # Try to parse string representation of a list, e.g., "['freshwater', 'resources']"
            keywords = ast.literal_eval(keywords)
        except Exception:
            # If not formatted as a list, treat as a single keyword
            keywords = [keywords]

    expanded_keywords = []
    for keyword in keywords:
        for k in keyword.split():
            expanded_keywords.append(k.strip(','))

    matched_indicators = []
    # Now, treat each element in the list as a phrase to be searched for in name or description
    for indicator in indicator_key:
        for keyword in expanded_keywords:
            if keyword.lower() in [
                k.strip('(),') for k in indicator['name'].split()
            ]:  # or keyword in indicator['indicator_description']:
                matched_term = keyword.strip().lower()
                matched_indicators.append(indicator)

    return clean_dict(matched_indicators)


def get_country_code_from_name(
    country_name: str,
) -> str:
    """Get the three-letter country code from a country name.

    Parameters
    ----------
    country_name : str
        The name of the country to get the code for.

    Returns
    -------
    str
        The three-letter country code.

    """
    data = pd.read_csv(RESOURCES_DIR / 'un_m49_cleaned.csv')
    try:
        return data[data['country_name'] == country_name]['country_code'].to_list()[0]
    except IndexError as e:
        raise InvalidCountryNameError(country_name) from e


def get_country_name_from_code(
    country_code: str,
) -> str:
    """Get the country name from a three-letter country code.

    Parameters
    ----------
    country_code : str
        The three-letter country code to get the name for.

    Returns
    -------
    str
        The name of the country.

    """
    data = pd.read_csv(RESOURCES_DIR / 'un_m49_cleaned.csv')
    try:
        return data[data['country_code'] == country_code]['country_name'].to_list()[0]
    except IndexError as e:
        raise InvalidCountryCodeError(country_code) from e


def get_indicator_code_from_name(
    indicator_name: str,
) -> str:
    """Get the indicator code from an indicator name.

    Parameters
    ----------
    indicator_name : str
        The name of the indicator to get the code for.

    Returns
    -------
    str
        The indicator code.

    """
    data = pd.read_csv(RESOURCES_DIR / 'wdi.csv')
    try:
        return data[data['name'] == indicator_name.strip()]['id'].to_list()[0]
    except IndexError as e:
        raise InvalidIndicatorNameError(indicator_name) from e


def get_indicator_name_from_code(
    indicator_code: str,
) -> str:
    """Get the indicator name from an indicator code.

    Parameters
    ----------
    indicator_code : str
        The code of the indicator to get the name for.

    Returns
    -------
    str
        The name of the indicator.

    """
    data = pd.read_csv(RESOURCES_DIR / 'wdi.csv')
    try:
        return data[data['id'] == indicator_code]['name'].to_list()[0]
    except IndexError as e:
        raise InvalidIndicatorCodeError(indicator_code) from e


def get_country_codes_in_region(
    region: str,
) -> list[str]:
    """Get the list of country codes in a given region.

    Parameters
    ----------
    region : str
        The region to get the countries for.

    Returns
    -------
    list[str]
        A list of countries in the region as three-letter country codes.

    """
    data = pd.read_csv(RESOURCES_DIR / 'un_m49_cleaned.csv')

    if region not in data['region'].tolist():
        raise InvalidRegionNameError(region)

    return data[data['region'] == region]['country_code'].tolist()


def retrieve_value(
    country_code: str,
    indicator_code: str,
    year: str,
) -> float | str | None:
    """Return the value of an indicator for a country at a given year.

    Parameters
    ----------
    country_code : str
        The three-letter country code to look up the indicator for.
    indicator_code : str
        The indicator code to look up.
    year : str
        The year to look up the indicator for.

    Returns
    -------
    float | str | None
        The value of the property for the subject at the given year, rounded to 5 decimal places.

    Raises
    ------
    InvalidCountryCodeError
        If the country code is not valid.
    InvalidIndicatorCodeError
        If the indicator file does not exist.
    NoDataAvailableError
        If the indicator has no value for the requested country and year.

    """
    # Check country code is valid
    data = pd.read_csv(RESOURCES_DIR / 'un_m49_cleaned.csv')
    if country_code not in data['country_code'].tolist():
        raise InvalidCountryCodeError(country_code)

    try:
        data = pd.read_csv(
            RESOURCES_DIR / 'wdi' / f'{indicator_code}.csv',
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
        raise NoDataAvailableError(
            {
                'country_code': country_code,
                'indicator_code': indicator_code,
                'year': year,
            }
        )

    return round(float(value), 5)
    # return {'subject': country_code, 'property': indicator_code, 'object': float(value), 'time': year}


if __name__ == '__main__':
    print('\n=== Search for Indicator Codes ===')
    print('search_for_indicator_names("Children enrolled in preprimary education")')
    print('Result:', search_for_indicator_names('Children enrolled in preprimary education'))

    # print('\n=== Search for Indicator Codes ===')
    # print('search_for_indicator_names("Land under cereal production (hectares)")')
    # print('Result:', search_for_indicator_names('Land under cereal production (hectares)'))

    print('\n=== Search for Indicator Codes ===')
    print('search_for_indicator_names(["freshwater", "resources"])')
    print('Result:', search_for_indicator_names(['freshwater', 'resources']))

    print('\n=== Search for Indicator Codes ===')
    print('search_for_indicator_names("freshwater resources")')
    print('Result:', search_for_indicator_names('freshwater resources'))

    print('\n=== Search for Indicator Codes ===')
    print("search_for_indicator_names(\"['freshwater', 'resources']\")")
    print('Result:', search_for_indicator_names("['freshwater', 'resources']"))

    print('\n=== Get Country Name from Code ===')
    print('get_country_name_from_code("COM")')
    print('Result:', get_country_name_from_code('COM'))

    print('\n=== Get Country Code from Name ===')
    print('get_country_code_from_name("Comoros")')
    print('Result:', get_country_code_from_name('Comoros'))

    print('\n=== Get Indicator Name from Code ===')
    print('get_indicator_name_from_code("NY.GDP.MKTP.CD")')
    print('Result:', get_indicator_name_from_code('NY.GDP.MKTP.CD'))

    print('\n=== Get Indicator Code from Name ===')
    print('get_indicator_code_from_name("Revenue, excluding grants (% of GDP)")')
    print('Result:', get_indicator_code_from_name('Revenue, excluding grants (% of GDP)'))

    print('\n=== Get Country Codes in Region ===')
    print('get_country_codes_in_region("Eastern Europe")')
    print('Result:', get_country_codes_in_region('Eastern Europe'))
