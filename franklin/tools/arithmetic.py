"""Library of tools to be provided to the model and provide the basis for solutions."""

import logging

import pandas as pd
from rich.logging import RichHandler

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
    """Count the number of non-None elements in a list.

    Args:
        values: A list of numbers to count.

    Returns:
        The number of elements in the list.

    """
    if isinstance(values, str):
        values = values.strip('[]\'"')
        values = [float(value.strip()) for value in values.split(',')]
    else:
        values = [float(value) for value in values]
    # Remove NaN values
    values = [value for value in values if pd.notna(value)]
    return len(values)


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


def final_answer(answer: str) -> str:
    """Indicate that the final answer has been computed.

    Args:
        answer: The final answer to the question.

    Returns:
        The final answer as a string.

    """
    return str(answer)


if __name__ == '__main__':
    print('\n=== Think ===')
    print('think("First I will check the indicator code")')
    print('Result:', think('First I will check the indicator code'))

    print('\n=== Add ===')
    print('add([1, 2, 3])')
    print('Result:', add([1, 2, 3]))

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

    print('\n=== Final Answer ===')
    print('final_answer("42")')
    print('Result:', final_answer('42'))
