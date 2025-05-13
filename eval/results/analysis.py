from pathlib import Path

import pandas as pd

LOG_PATH = Path('..', 'log').with_suffix('.jsonl')


def get_all_files_matching(**kwargs):
    """Extract all rows where the kwargs are matched.

    Parameters
    ----------
    **kwargs : dict
        Key-value pairs to filter the rows in the log file.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing rows that match the given criteria.

    """
    log_files = pd.read_json(LOG_PATH, lines=True)

    for key, value in kwargs.items():
        log_files = log_files[log_files[key] == value]

    return log_files


def remove_no_answer_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove rows where there is to tool call using 'final_answer'.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to filter.

    Returns
    -------
    pd.DataFrame
        The filtered DataFrame.

    """
    # Remove rows where there is no tool call using 'final_answer'
    df = df[
        df['messages'].apply(
            lambda messages: any(message['role'] == 'tool' and message['name'] == 'final_answer' for message in messages)
        )
    ]
    return df


def get_model_final_answer(
    messages,
) -> str:
    """Get the final answer from the model's messages.

    Parameters
    ----------
    row : pd.Series
        A row from the log file.

    Returns
    -------
    str
        The final answer from the model's messages.

    """
    # Get the messages where 'role' = 'tool' and 'name' = 'final_answer'
    final_answer = [msg for msg in messages if msg['role'] == 'tool' and msg['name'] == 'final_answer']
    if final_answer:
        # Get the content of the final answer
        final_answer_content = final_answer[0]['content']
        # Convert the content to a string
        final_answer_str = str(final_answer_content)
        return final_answer_str
    else:
        # If no final answer is found, return None
        return None


def get_gold_final_answer(actions) -> str:
    """Get the final answer from the actions sequence.

    Parameters
    ----------
    row : pd.Series
        A row from the log file.

    Returns
    -------
    str
        The final answer from the actions sequence.

    """
    # Get the actions where 'name' = 'final_answer'
    final_answer = [action for action in actions if action['name'] == 'final_answer']
    return str(final_answer)


def check_final_answer(row: pd.Series) -> bool:
    """Check if the final answer is correct.

    Parameters
    ----------
    row : pd.Series
        A row from the log file.

    Returns
    -------
    bool
        True if the final answer is correct, False otherwise.

    """
    # Get the final answer from the model's messages
    model_final_answer = get_model_final_answer(row['messages'])
    # Get the final answer from the actions sequence
    gold_final_answer = row['answer']

    # We now need to apply a number of heuristic checks to see if the final answers are equal
    # e.g., match 3.222426e+01 to 32.2242574604399
    if isinstance(gold_final_answer, float):
        return str(gold_final_answer) in model_final_answer

    # Check if the final answers are equal
    return model_final_answer == gold_final_answer


def get_model_tool_calls(
    messages,
    clean=False,
):
    """Get the tool calls from the model's messages.

    Parameters
    ----------
    row : pd.Series
        A row from the log file.
    clean : bool, optional
        If True, remove 'think' tool calls. Default is False.

    Returns
    -------
    list
        A list of tool calls extracted from the model's messages.

    """
    # Get the messages where 'role' = 'tool'
    tool_calls = [msg['tool_calls'][0]['function'] for msg in messages if msg['role'] == 'assistant' and 'tool_calls' in msg]

    # Arguments is a string representation of a dictionary, convert it to a dictionary
    for i in range(len(tool_calls)):
        tool_calls[i]['arguments'] = eval(tool_calls[i]['arguments'])

    # If clean, remove 'think' tool calls
    if clean:
        tool_calls = [call for call in tool_calls if call['name'] != 'think']

    return tool_calls


def get_gold_tool_calls(
    actions,
    clean=False,
):
    """Get the tool calls from the actions sequence.

    Parameters
    ----------
    actions : pd.Series
        A row from the log file.
    clean : bool, optional
        If True, remove 'think' tool calls. Default is False.

    Returns
    -------
    list
        A list of tool calls extracted from the actions sequence.

    """
    # Each tool call contains a 'result' key, drop it from the actions
    for action in actions:
        if 'result' in action:
            del action['result']

    return actions


def make_hashable(value):
    """Recursively convert a value into a hashable type.

    Parameters
    ----------
    value : any
        The value to be converted into a hashable type.

    Returns
    -------
        hashable
            A hashable representation of the input value.

    """
    if isinstance(value, dict):
        return tuple(sorted((k, make_hashable(v)) for k, v in value.items()))
    elif isinstance(value, list):
        return tuple(make_hashable(v) for v in value)
    else:
        return value


def precision(gold, model):
    """Calculate precision for tool calls.

    Parameters
    ----------
    gold : list
        The ground truth tool calls.
    model : list
        The tool calls predicted by the model.

    Returns
    -------
    float
        The precision value.

    """
    # Convert lists of dicts to sets of hashable tuples for comparison
    gold_set = {make_hashable(d) for d in gold}
    model_set = {make_hashable(d) for d in model}

    # True positives, false positives, and false negatives
    true_positives = gold_set & model_set
    false_positives = model_set - gold_set
    false_negatives = gold_set - model_set

    # Calculate precision
    precision = len(true_positives) / (len(true_positives) + len(false_positives)) if model_set else 0

    return precision


def recall(gold, model):
    """Calculate recall for tool calls.

    Parameters
    ----------
    gold : list
        The ground truth tool calls.
    model : list
        The tool calls predicted by the model.

    Returns
    -------
    float
        The recall value.

    """
    # Convert lists of dicts to sets of hashable tuples for comparison
    gold_set = {make_hashable(d) for d in gold}
    model_set = {make_hashable(d) for d in model}

    # True positives, false positives, and false negatives
    true_positives = gold_set & model_set
    false_positives = model_set - gold_set
    false_negatives = gold_set - model_set

    # Calculate recall
    recall = len(true_positives) / (len(true_positives) + len(false_negatives)) if gold_set else 0

    return recall


def accuracy(gold, model):
    """Calculate accuracy for tool calls.

    Parameters
    ----------
    gold : list
        The ground truth tool calls.
    model : list
        The tool calls predicted by the model.

    Returns
    -------
    float
        The accuracy value.

    """
    # Convert lists of dicts to sets of hashable tuples for comparison
    gold_set = {make_hashable(d) for d in gold}
    model_set = {make_hashable(d) for d in model}

    # True positives, false positives, and false negatives
    true_positives = gold_set & model_set
    false_positives = model_set - gold_set
    false_negatives = gold_set - model_set

    # Calculate accuracy
    accuracy = len(true_positives) / (len(gold_set | model_set)) if (gold_set | model_set) else 0

    return accuracy
