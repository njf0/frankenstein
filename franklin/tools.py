"""Library of tools to be provided to the model and provide the basis for solutions."""

import inspect
import logging
from pathlib import Path

import pandas as pd
from rich.logging import RichHandler

from franklin.exceptions import (
    InvalidCountryCode,
    InvalidCountryName,
    InvalidIndicatorCode,
    InvalidIndicatorName,
    InvalidRegionName,
    NoDataAvailable,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    datefmt='[%X]',
    handlers=[RichHandler(rich_tracebacks=True)],
)


def think(thought: str) -> str:
    """Think aloud about the actions required to solve the problem.

    Args:
        thought: Your thought about the actions required to solve the problem.

    Returns:
        The thought as a string.

    """
    return str(thought)


def add(values: list[float]) -> float:
    """Add a list of numbers.

    Args:
        values: A list of numbers to add.

    Returns:
        The sum of the numbers in the list.

    """
    if isinstance(values, str):
        values = values.strip('[]\'"')
        values = [float(value.strip()) for value in values.split(',')]
    else:
        values = [float(value) for value in values]

    return sum(float(value) for value in values)


def subtract(value_a: float, value_b: float) -> float:
    """Subtract two numbers.

    Args:
        value_a: The first number.
        value_b: The second number.

    Returns:
        The difference between the two numbers.

    """
    return float(value_a) - float(value_b)


def greater_than(value_a: float, value_b: float) -> bool:
    """Check if value_a is greater than value_b.

    Args:
        value_a: The first number.
        value_b: The second number.

    Returns:
        True if value_a is greater than value_b, False otherwise.

    """
    return float(value_a) > float(value_b)


def less_than(value_a: float, value_b: float) -> bool:
    """Check if value_a is less than value_b.

    Args:
        value_a: The first number.
        value_b: The second number.

    Returns:
        True if value_a is less than value_b, False otherwise.

    """
    return float(value_a) < float(value_b)


def multiply(values: list[float]) -> float:
    """Multiply a list of numbers.

    Args:
        values: A list of numbers to multiply.

    Returns:
        The product of the numbers in the list.

    """
    if isinstance(values, str):
        values = values.strip('[]\'"')
        values = [float(value.strip()) for value in values.split(',')]
    else:
        values = [float(value) for value in values]

    product = 1
    for number in [float(i) for i in values]:
        product *= number
    return product


def divide(value_a: float, value_b: float) -> float:
    """Divide two numbers.

    Args:
        value_a: The first number.
        value_b: The second number.

    Returns:
        The quotient of the two numbers.

    """
    if float(value_b) == 0:
        raise ZeroDivisionError('Division by zero is not allowed. Double-check your inputs.')
    return float(value_a) / float(value_b)


def mean(values: list[float]) -> float:
    """Calculate the mean of a list of numbers.

    Args:
        values: A list of numbers to calculate the mean for.

    Returns:
        The mean of the numbers in the list.

    """
    if isinstance(values, str):
        values = values.strip('[]\'"')
        values = [float(value.strip()) for value in values.split(',')]
    else:
        values = [float(value) for value in values]

    return sum(values) / len(values)


def mode(values: list[float]) -> float:
    """Calculate the mode of a list of numbers.

    Args:
        values: A list of numbers to calculate the mode for.

    Returns:
        The mode of the numbers in the list.

    """
    if isinstance(values, str):
        values = values.strip('[]\'"')
        values = [float(value.strip()) for value in values.split(',')]
    else:
        values = [float(value) for value in values]

    return max(set(values), key=values.count)


def median(values: list[float]) -> float:
    """Calculate the median of a list of numbers.

    Args:
        values: A list of numbers to calculate the median for.

    Returns:
        The median of the numbers in the list.

    """
    if isinstance(values, str):
        values = values.strip('[]\'"')
        values = [float(value.strip()) for value in values.split(',')]
    else:
        values = [float(value) for value in values]

    sorted_values = sorted(values)
    n = len(sorted_values)
    median_value = (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2 if n % 2 == 0 else sorted_values[n // 2]

    return median_value


def maximum(values: list[float]) -> float:
    """Return the maximum of a list of numbers.

    Args:
        values: A list of numbers to Return the maximum for.

    Returns:
        The maximum of the numbers in the list.

    """
    if isinstance(values, str):
        values = values.strip('[]\'"')
        values = [float(value.strip()) for value in values.split(',')]
    else:
        values = [float(value) for value in values]

    return max(values)


def minimum(values: list[float]) -> float:
    """Return the minimum of a list of numbers.

    Args:
        values: A list of numbers to Return the minimum for.

    Returns:
        The minimum of the numbers in the list.

    """
    if isinstance(values, str):
        values = values.strip('[]\'"')
        values = [float(value.strip()) for value in values.split(',')]
    else:
        values = [float(value) for value in values]

    return min(values)


def count(values: list[float | str]) -> int:
    """Count the number of elements in a list.

    Args:
        values: A list of numbers to count.

    Returns:
        The number of elements in the list.

    """
    pass


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
        raise InvalidCountryName(country_name) from e


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
        raise InvalidIndicatorName(indicator_name) from e


def sort(values: list[float]) -> list[float]:
    """Sort a list of numbers.

    Args:
        values: The list of numbers to sort.

    Returns:
        The sorted list of numbers.

    """
    if isinstance(values[0], str):
        values = [value.strip("[]'") for value in values]
        values = [float(value) for value in values[0].split(',')]

    return sorted(values)


def get_country_codes_in_region(region_name: str) -> list[str]:
    """Get the list of country codes in a given region.

    Args:
        region_name: The region to get the countries for.

    Returns:
        A list of countries in the region as three-letter country codes.

    """
    data = pd.read_csv(Path('resources', 'iso_3166.csv'))

    if region_name not in data['region'].tolist():
        raise InvalidRegionName(region_name)

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
        InvalidCountryCode: If the country code is not valid.
        InvalidIndicatorCode: If the file for the indicator code does not exist.

    """
    # Check country code is valid
    data = pd.read_csv(Path('resources', 'iso_3166.csv'))
    if country_code not in data['country_code'].tolist():
        raise InvalidCountryCode(country_code)

    try:
        data = pd.read_csv(
            Path('resources', 'wdi', f'{indicator_code}.csv'),
            index_col='country_code',
        )
    except FileNotFoundError as e:
        raise InvalidIndicatorCode(indicator_code) from e

    try:
        value = data.loc[country_code, year]
    except KeyError as e:
        raise NoDataAvailable(
            {
                'country_code': country_code,
                'indicator_code': indicator_code,
                'year': year,
            }
        ) from e

    if pd.isna(value):
        return None

    return value
    # return {'subject': country_code, 'property': indicator_code, 'object': float(value), 'time': year}


def final_answer(answer: str) -> str:
    """Indicate that the final answer has been computed.

    Args:
        answer: The final answer to the question.

    Returns:
        The final answer as a string.

    """
    return str(answer)


tools = [
    func
    for name, func in inspect.getmembers(
        __import__(__name__),
        inspect.isfunction,
    )
]
