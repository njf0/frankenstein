def think(thought: str) -> str:
    """Record a thought or plan for the next step.

    Parameters
    ----------
    thought : str
        A string describing your plan or reasoning.

    Returns
    -------
    str
        The same thought string.

    """
    return thought


def final_answer(answer: str) -> str:
    """Submit your final answer.

    Parameters
    ----------
    answer : str
        The answer to the question.

    Returns
    -------
    str
        The same answer string.

    """
    return answer


if __name__ == '__main__':
    print('\n=== Think ===')
    print('think("First I will check the indicator code")')
    print('Result:', think('First I will check the indicator code'))

    print('\n=== Final Answer ===')
    print('final_answer("42")')
    print('Result:', final_answer('42'))
