"""Library of tools to be provided to the model and provide the basis for solutions."""

import ast
import logging

import pandas as pd
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    datefmt='[%X]',
    handlers=[RichHandler(rich_tracebacks=True)],
)


def add(
    values: list[float],
) -> float:
    """Add a list of numbers.

    Args:
        values: A list of numbers to add.

    Returns:
        The sum of the numbers in the list.

    """
    if isinstance(values, str):
        values = ast.literal_eval(values)
    values = [float(value) for value in values if pd.notna(value)]
    return sum(float(value) for value in values if pd.notna(value))


def subtract(
    value_a: float,
    value_b: float,
) -> float:
    """Subtract two numbers.

    Args:
        value_a: The first number.
        value_b: The second number.

    Returns:
        The difference between the two numbers.

    """
    return float(value_a) - float(value_b)


def greater_than(
    value_a: float,
    value_b: float,
) -> bool:
    """Check if value_a is greater than value_b.

    Args:
        value_a: The first number.
        value_b: The second number.

    Returns:
        True if value_a is greater than value_b, False otherwise.

    """
    return float(value_a) > float(value_b)


def less_than(
    value_a: float,
    value_b: float,
) -> bool:
    """Check if value_a is less than value_b.

    Args:
        value_a: The first number.
        value_b: The second number.

    Returns:
        True if value_a is less than value_b, False otherwise.

    """
    return float(value_a) < float(value_b)


def multiply(
    values: list[float],
) -> float:
    """Multiply a list of numbers.

    Args:
        values: A list of numbers to multiply.

    Returns:
        The product of the numbers in the list.

    """
    if isinstance(values, str):
        values = ast.literal_eval(values)
    values = [float(value) for value in values]
    product = 1
    for number in values:
        product *= number
    return product


def divide(
    value_a: float,
    value_b: float,
) -> float:
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


def mean(
    values: list[float],
) -> float:
    """Calculate the mean of a list of numbers.

    Args:
        values: A list of numbers to calculate the mean for.

    Returns:
        The mean of the numbers in the list.

    """
    if isinstance(values, str):
        values = ast.literal_eval(values)
    values = [float(value) for value in values if pd.notna(value)]
    if not values:
        raise ValueError('No valid (non-NaN) values provided to mean()')
    return sum(values) / len(values)


def mode(
    values: list[float],
) -> float:
    """Calculate the mode of a list of numbers.

    Args:
        values: A list of numbers to calculate the mode for.

    Returns:
        The mode of the numbers in the list.

    """
    if isinstance(values, str):
        values = ast.literal_eval(values)
    values = [float(value) for value in values if pd.notna(value)]
    if not values:
        raise ValueError('No valid (non-NaN) values provided to mode()')
    return max(set(values), key=values.count)


def median(
    values: list[float],
) -> float:
    """Calculate the median of a list of numbers.

    Args:
        values: A list of numbers to calculate the median for.

    Returns:
        The median of the numbers in the list.

    """
    if isinstance(values, str):
        values = ast.literal_eval(values)
    values = [float(value) for value in values if pd.notna(value)]
    if not values:
        raise ValueError('No valid (non-NaN) values provided to median()')
    sorted_values = sorted(values)
    n = len(sorted_values)
    median_value = (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2 if n % 2 == 0 else sorted_values[n // 2]
    return median_value


def maximum(
    values: list[float],
) -> float:
    """Return the maximum of a list of numbers.

    Args:
        values: A list of numbers to Return the maximum for.

    Returns:
        The maximum of the numbers in the list.

    """
    if isinstance(values, str):
        values = ast.literal_eval(values)
    # Filter out None/NaN values
    values = [float(value) for value in values if pd.notna(value)]
    if not values:
        raise ValueError('No valid (non-NaN) values provided to maximum()')
    return max(values)


def minimum(
    values: list[float],
) -> float:
    """Return the minimum of a list of numbers.

    Args:
        values: A list of numbers to Return the minimum for.

    Returns:
        The minimum of the numbers in the list.

    """
    if isinstance(values, str):
        values = ast.literal_eval(values)
    # Filter out None/NaN values
    values = [float(value) for value in values if pd.notna(value)]
    if not values:
        raise ValueError('No valid (non-NaN) values provided to minimum()')
    return min(values)


def count(
    values: list[float | str],
) -> int:
    """Count the number of non-None elements in a list.

    Args:
        values: A list of values to count.

    Returns:
        The number of elements in the list.

    """
    if isinstance(values, str):
        values = ast.literal_eval(values)
    # Only filter out NaN (for numbers), keep bools/strings
    values = [v for v in values if pd.notna(v)]
    return len(values)


def rank(
    values: list[float],
    query_value: float,
) -> int:
    """Return the 1-based rank of query_value in values sorted descending.

    Args:
        values: A list of numbers to rank against.
        query_value: The value whose rank is to be determined.

    Returns:
        The 1-based rank of query_value in the list of values sorted in descending order.
        If there are duplicate values, the rank of the first occurrence is returned.

    """
    if isinstance(values, str):
        values = ast.literal_eval(values)
    values = [float(value) for value in values if pd.notna(value)]
    sorted_values = sorted(values, reverse=True)
    try:
        return sorted_values.index(query_value) + 1
    except ValueError as e:
        raise ValueError(
            f"Value {query_value} not found in the list. Ensure it is present in the values."
        ) from e


def sort(
    values: list[float],
) -> list[float]:
    """Sort a list of numbers.

    Args:
        values: The list of numbers to sort.

    Returns:
        The sorted list of numbers.

    """
    if isinstance(values, str):
        values = ast.literal_eval(values)
    values = [float(value) for value in values if pd.notna(value)]
    return sorted(values)


def index(
    values: list[float],
    query_value: float,
) -> int:
    """Return the 0-based index of query_value in values.

    Args:
        values: List of values to search.
        query_value: The value to find the index for.

    Returns:
        The 0-based index of the first occurrence of query_value in values after filtering out NaN.

    """
    if isinstance(values, str):
        values = ast.literal_eval(values)
    values = [float(value) for value in values if pd.notna(value)]
    try:
        return values.index(query_value)
    except ValueError as e:
        raise ValueError(
            f"Value {query_value} not found in the list. Ensure it is present in the values."
        ) from e


if __name__ == '__main__':
    """Run some example calculations to demonstrate the tools."""
    print('\n=== Add ===')
    print('add([1, 2, 3])')
    print('Result:', add('["1", 2, 3]'))

    print('\n=== Subtract ===')
    print('subtract(10, 4)')
    print('Result:', subtract(10, 4))

    print('\n=== Multiply ===')
    print('multiply([2, 3, 4])')
    print('Result:', multiply([2, 3, 4]))

    print('\n=== Divide ===')
    print('divide(20, 5)')
    print('Result:', divide(20, 5))

    print('\n=== Mean ===')
    print('mean([1, 2, 3, 4, 5])')
    print('Result:', mean([1, 2, 3, 4, 5]))

    print('\n=== Median ===')
    print('median([1, 3, 2, 5, 4])')
    print('Result:', median([1, 3, 2, 5, 4]))

    print('\n=== Mode ===')
    print('mode([1, 2, 2, 3, 4])')
    print('Result:', mode([1, 2, 2, 3, 4]))

    print('\n=== Maximum ===')
    print('maximum([1, 5, 3, 2])')
    print('Result:', maximum([1, 5, 3, 2]))

    print('\n=== Minimum ===')
    print('minimum([1, 5, 3, 2])')
    print('Result:', minimum([1, 5, 3, 2]))

    print('\n=== Greater Than ===')
    print('greater_than(5, 3)')
    print('Result:', greater_than(5, 3))

    print('\n=== Less Than ===')
    print('less_than(2, 7)')
    print('Result:', less_than(2, 7))

    print('\n=== Count ===')
    print('count([1, 2, 3, 4, 5])')
    print('Result:', count([1, 2, 3, 4, 5]))

    print('\n=== Rank ===')
    print('rank([10, 20, 30, 40], 20)')
    print('Result:', rank([10, 20, 30, 40], 20))

    print('\n=== Index ===')
    print('index([10, 20, 30, 40], 30)')
    print('Result:', index([10, 20, 30, 40], 30))
