"""Library of tools to be provided to the model and provide the basis for solutions."""

import inspect
from pathlib import Path

import pandas as pd


class FranklinActionError(Exception):
    """Base class for all Franklin action-related errors."""

    pass


class InvalidIndicatorName(FranklinActionError):
    """Exception raised when an invalid indicator name is used."""

    def __init__(self, indicator_name: str):
        super().__init__(
            f"Indicator name '{indicator_name}' is not valid. Ensure you have used the correct indicator name from the question."
        )


class InvalidIndicatorCode(FranklinActionError):
    """Exception raised when an invalid indicator code is used."""

    def __init__(self, indicator_code: str):
        super().__init__(
            f"Indicator code '{indicator_code}' is not valid. Ensure you have used the 'get_indicator_code_from_name' function to get the code from the indicator name."
        )


class InvalidCountryName(FranklinActionError):
    """Exception raised when an invalid country name is used."""

    def __init__(self, country_name: str):
        super().__init__(
            f"Country name '{country_name}' is not valid. Double-check the country name in the question and ensure it is spelled correctly."
        )


class InvalidCountryCode(FranklinActionError):
    """Exception raised when an invalid country code is used."""

    def __init__(self, country_code: str):
        super().__init__(
            f"Country code '{country_code}' is not valid. Ensure you have used the 'get_country_code_from_name' function to get the code from the country name."
        )


class NoDataAvailable(FranklinActionError):
    """Exception raised when no data is available for a given indicator and country."""

    def __init__(self, name: str, arguments: dict):
        super().__init__(
            f"No data is available for country code '{arguments['country_code']}' for indicator code '{arguments['indicator_code']}' in year '{arguments['year']}'. Re-plan and consider if it is still possible to answer the question. If not, call the 'question_unanswerable' function to end the conversation."
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


def subtract(a: float, b: float) -> float:
    """Subtract two numbers.

    Args:
        a: The first number.
        b: The second number.

    Returns:
        The difference between the two numbers.

    """
    return float(a) - float(b)


def greater_than(a: float, b: float) -> bool:
    """Check if a is greater than b.

    Args:
        a: The first number.
        b: The second number.

    Returns:
        True if a is greater than b, False otherwise.

    """
    return float(a) > float(b)


def less_than(a: float, b: float) -> bool:
    """Check if a is less than b.

    Args:
        a: The first number.
        b: The second number.

    Returns:
        True if a is less than b, False otherwise.

    """
    return float(a) < float(b)


def multiply(values: list[float]) -> float:
    """Multiply a list of numbers.

    Args:
        list: A list of numbers to multiply.

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


def divide(a: float, b: float) -> float:
    """Divide two numbers.

    Args:
        a: The first number.
        b: The second number.

    Returns:
        The quotient of the two numbers.

    """
    if float(b) == 0:
        raise ZeroDivisionError('Division by zero is not allowed. Double-check your inputs.')
    return float(a) / float(b)


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
    except IndexError:
        raise InvalidCountryName(country_name)


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


def get_countries_in_region(region_name: str) -> list[str]:
    """Get the list of countries which are members of a region.

    Args:
        region_name: The region to get the countries for.

    Returns:
        A list of countries in the region as three-letter country codes.

    """
    data = pd.read_csv(Path('resources', 'iso_3166.csv'))
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
            name=indicator_code,
            arguments={
                'country_code': country_code,
                'indicator_code': indicator_code,
                'year': year,
            },
        ) from e

    if pd.isna(value):
        raise NoDataAvailable(
            name=indicator_code,
            arguments={
                'country_code': country_code,
                'indicator_code': indicator_code,
                'year': year,
            },
        )

    return value


def final_answer(answer) -> str:
    """Indicate that the final answer has been computed.

    Args:
        answer: The final answer to the question.

    Returns:
        The final answer as a string.

    """
    return str(answer)


# def question_unanswerable() -> str:
#     """Call this function if the question is unanswerable and the conversation should end.

#     Returns:
#         A string indicating that the question is unanswerable.

#     """
#     return 1


tools = [
    func
    for name, func in inspect.getmembers(
        __import__(__name__),
        inspect.isfunction,
    )
]
