import pandas as pd


def get_gold_tool_calls(row: pd.Series, tools: list) -> list[dict]:
    """Get the gold tool calls from a row (Series).

    Parameters
    ----------
    row : pd.Series
        A row from the DataFrame containing the actions.

    Returns
    -------
    list[dict]
        A list of dictionaries representing the tool calls, where each dictionary contains the 'name' and
        'arguments' of the tool call.

    """
    tool_calls = []
    for action in row['actions']:
        tool_calls.append({'name': action['name'], 'arguments': action['arguments']})

    # For functions with a 'values' argument (which takes a list of values), we should sort the values to perform a fair comparison.
    for call in tool_calls:
        if 'values' in call['arguments']:
            # Sort the values for comparison
            call['arguments']['values'] = sorted(call['arguments']['values'])

    # Filter out tool calls that are not in the tools list
    if tools:
        tool_calls = [call for call in tool_calls if call['name'] in tools]

    return tool_calls


def get_pred_tool_calls(row: pd.Series) -> list[dict]:
    """Post-process predicted tool calls from messages.

    Post-processing involves applying a number of transformations to the tool calls extracted from the messages. These include:

    1. Normalising the arguments of the `less_than` tool call to `greater_than`.
    2. Checking if the `search_for_indicator_codes` tool call resulted in the correct indicator codes, and rewriting it to match the gold call if successful.


    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the messages and tool calls.

    Returns
    -------
    list[dict]
        A list of dictionaries representing the post-processed tool calls.

    """
    tool_calls = []

    # Extract tool calls from messages
    for msg in row.get('messages', []):
        if 'tool_calls' in msg and isinstance(msg['tool_calls'], list):
            for call in msg['tool_calls']:
                function = call['function']
                pred_call = {'name': function['name'], 'arguments': function['arguments'], 'id': call.get('id')}
                pred_call['result'] = next(
                    m['content'] for m in row['messages'] if m.get('tool_call_id') == call.get('id') and m['role'] == 'tool'
                )
                tool_calls.append(pred_call)

    # Normalise the arguments of the `less_than` tool call to `greater_than`
    for call in tool_calls:
        if call['name'] == 'less_than':
            call['name'] = 'greater_than'
            value_a = call['arguments'].get('value_a', None)
            value_b = call['arguments'].get('value_b', None)
            call['arguments'] = {'value_a': value_b, 'value_b': value_a}

    # Remove any final_answer tool calls
    tool_calls = [call for call in tool_calls if call['name'] != 'final_answer']

    # search_for_indicator_names: check if any of these calls resulted in the correct indicator names.
    for call in tool_calls:
        if call['name'] == 'search_for_indicator_names':
            # Check if any of the returned indicator names match the 'property' slot value
            for d in call.get('result', []):
                if isinstance(d, dict):
                    if d.get('indicator_name') == row.get('slot_values', {}).get('property_original', ''):
                        # This counts as a successful search.
                        # Now, because it's successful, we rewrite this to match the gold call to aid analysis.
                        # Use direct assignment to update the keywords argument
                        call['arguments']['keywords'] = row.get('slot_values', {}).get('property_original', '')

    # For functions with a 'values' argument (which takes a list of values), we should sort the values to perform a fair comparison.
    for call in tool_calls:
        if 'values' in call['arguments']:
            # Sort the values for comparison
            try:
                call['arguments']['values'] = sorted([v for v in call['arguments']['values'] if v is not None])
            except TypeError:
                # If the values are not sortable (e.g., if they are not all strings or numbers), we skip sorting
                pass

    # Finally, drop 'id' and 'result' fields from each call
    for call in tool_calls:
        call.pop('id', None)
        call.pop('result', None)

    # Drop 'think' and 'final_answer' calls
    tool_calls = [call for call in tool_calls if call['name'] not in ['think', 'final_answer']]

    return tool_calls


def get_true_positives(row: pd.Series) -> list[dict]:
    """Return the list of true positive tool calls (predicted tool calls that are in the gold set).

    Parameters
    ----------
    row : pd.Series

    Returns
    -------
    list[dict]
        List of tool calls present in both pred_tool_calls and gold_tool_calls.

    """
    pred = list(row['pred_tool_calls']) if 'pred_tool_calls' in row else []
    gold = list(row['gold_tool_calls']) if 'gold_tool_calls' in row else []
    gold_remaining = gold.copy()
    tp = []
    for p in pred:
        if p in gold_remaining:
            tp.append(p)
            gold_remaining.remove(p)
    return tp


def get_false_positives(row: pd.Series) -> list[dict]:
    """Return the list of false positive tool calls (predicted tool calls that are not in the gold set).

    Parameters
    ----------
    row : pd.Series

    Returns
    -------
    list[dict]
        List of tool calls present in pred_tool_calls but not in gold_tool_calls.

    """
    pred = list(row['pred_tool_calls']) if 'pred_tool_calls' in row else []
    gold = list(row['gold_tool_calls']) if 'gold_tool_calls' in row else []
    gold_remaining = gold.copy()
    fp = []
    for p in pred:
        if p in gold_remaining:
            gold_remaining.remove(p)
        else:
            fp.append(p)
    return fp


def get_false_negatives(row: pd.Series) -> list[dict]:
    """Return the list of false negative tool calls (gold tool calls that are not in the predictions).

    Parameters
    ----------
    row : pd.Series

    Returns
    -------
    list[dict]
        List of tool calls present in gold_tool_calls but not in pred_tool_calls.

    """
    gold = list(row['gold_tool_calls']) if 'gold_tool_calls' in row else []
    pred = list(row['pred_tool_calls']) if 'pred_tool_calls' in row else []
    pred_remaining = pred.copy()
    fn = []
    for g in gold:
        if g in pred_remaining:
            pred_remaining.remove(g)
        else:
            fn.append(g)
    return fn


def get_true_false_positives(row: pd.Series) -> float:
    """Extract the number of true and false positives from a row.

    Not quite as simple as standard true/false positives because we do not include repeated calls as true positives.

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted and gold tool calls.

    Returns
    -------
    tuple[list[dict], list[dict]]
        A tuple containing two lists: the first is the list of true positives, and the second is the list of false positives.

    """
    pred = row['pred_tool_calls']
    gold = row['gold_tool_calls']
    tp = []
    fp = []
    for p in pred:
        if p in gold:
            tp.append(p)
            gold.remove(p)
        else:
            fp.append(p)
    return tp, fp


def get_precision(row: pd.Series) -> float:
    """Calculate the precision of the predicted tool calls.

    Precision is defined as the number of true positives divided by the total number of predicted tool calls.

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted and gold tool calls.

    Returns
    -------
    float
        The precision of the predicted tool calls.

    """
    # Create true/false positives if they don't already exist
    if 'true_positives' not in row or 'false_positives' not in row:
        tp, fp = get_true_false_positives(row)
        row['true_positives'] = tp
        row['false_positives'] = fp

    tp = row['true_positives']
    fp = row['false_positives']

    return len(tp) / (len(tp) + len(fp)) if (len(tp) + len(fp)) > 0 else 0.0


def get_coverage(row: pd.Series) -> float:
    """Calculate coverage: proportion of gold tool calls found in predictions.

    This function measures recall for tool calls: the fraction of gold tool calls that are present in the model's predictions.
    It matches each gold tool call to a unique prediction (no double-counting).

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted and gold tool calls.

    Returns
    -------
    float
        The proportion of gold tool calls that are present in the predictions (recall).
        Returns 1.0 if there are no gold tool calls (trivially complete).

    """
    matched = 0
    pred_used = [False] * len(row['pred_tool_calls'])

    for g in row['gold_tool_calls']:
        for i, p in enumerate(row['pred_tool_calls']):
            if not pred_used[i] and p == g:
                matched += 1
                pred_used[i] = True  # Prevent reusing a prediction
                break
    return matched / len(row['gold_tool_calls']) if row['gold_tool_calls'] else 1.0  # Empty gold = trivially complete


def get_error_made(row: pd.Series) -> list[dict]:
    """Return true if the model made a tool call which returned an error.

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted tool calls.

    Returns
    -------
    bool
        True if the model made a tool call which returned an error, False otherwise.

    """
    tool_call_error = False

    # Extract tool calls from messages
    for msg in row['messages']:
        if 'tool_calls' in msg:
            for call in msg['tool_calls']:
                function = call['function']
                pred_call = {'name': function['name'], 'arguments': function['arguments'], 'id': call.get('id')}

                # Resolve the result of the tool call from the messages
                pred_call['result'] = next(
                    m['content'] for m in row['messages'] if m.get('tool_call_id') == call.get('id') and m['role'] == 'tool'
                )

                # Check if the result is an error
                if isinstance(pred_call['result'], str) and pred_call['result'].startswith('Error:'):
                    # If the result starts with 'Error:', we consider it an error call
                    pred_call['result'] = {'error': pred_call['result']}
                    tool_call_error = True
                    break

    return tool_call_error


def get_correct_indicator_data_process(row: pd.Series) -> bool:
    """Check if the model performs the correct series of steps for data retrieval.

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted tool calls.

    Returns
    -------
    bool
        True if no correct indicator data process is performed, False otherwise.

    """
    indicator_code = row['slot_values']['property']
    gold_subset = [
        c
        for c in row['gold_tool_calls']
        if c['name']
        in [
            'search_for_indicator_names',
            'get_indicator_code_from_name',
            'get_country_code_from_name',
            'get_country_name_from_code',
            'get_indicator_name_from_code',
            'get_country_codes_in_region',
        ]
    ]
    pred_subset = [
        c
        for c in row['pred_tool_calls']
        if c['name']
        in [
            'search_for_indicator_names',
            'get_indicator_code_from_name',
            'get_country_code_from_name',
            'get_country_name_from_code',
            'get_indicator_name_from_code',
            'get_country_codes_in_region',
        ]
    ]
    for call in pred_subset:
        if call['name'] == 'search_for_indicator_names':
            # Check if any of the returned indicator names match the 'property' slot value
            for d in call.get('result', []):
                # If the indicator name matches the property, we rewrite this to match the gold call to aid analysis.
                # This is because the model has successfully found the indicator name.
                if isinstance(d, dict):
                    if d.get('indicator_name') == row.get('slot_values', {}).get('property', ''):
                        # This counts as a successful search.
                        # Now, because it's successful, we rewrite this to match the gold call to aid analysis.
                        call['arguments']['keywords'] = row.get('slot_values', {}).get('property_original', '')
                        # Use the full name of the indicator.

    return all(g in pred_subset for g in gold_subset)


def get_missing_tool_calls(row: pd.Series) -> list[dict]:
    """Return a list of gold tool calls that are missing from the model's predicted tool calls.

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted and gold tool calls.

    Returns
    -------
    list[dict]
        List of tool calls (dicts) present in gold_tool_calls but not in pred_tool_calls.

    """
    gold = list(row['gold_tool_calls']) if 'gold_tool_calls' in row else []
    pred = list(row['pred_tool_calls']) if 'pred_tool_calls' in row else []
    # Make a copy of pred so we can remove matches as we go (to handle duplicates correctly)
    pred_remaining = pred.copy()
    missing = []
    for g in gold:
        if g in pred_remaining:
            pred_remaining.remove(g)
        else:
            missing.append(g)
    return missing


def get_additional_tool_calls(row: pd.Series) -> list[dict]:
    """Return a list of additional tool calls that are present in the model's predicted tool calls but not in the gold tool calls.

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted and gold tool calls.

    Returns
    -------
    list[dict]
        List of tool calls (dicts) present in pred_tool_calls but not in gold_tool_calls.

    """
    pred = list(row['pred_tool_calls']) if 'pred_tool_calls' in row else []
    gold = list(row['gold_tool_calls']) if 'gold_tool_calls' in row else []
    # Make a copy of gold so we can remove matches as we go (to handle duplicates correctly)
    gold_remaining = gold.copy()
    additional = []
    for p in pred:
        if p in gold_remaining:
            gold_remaining.remove(p)
        else:
            additional.append(p)

    return additional


def get_incorrect_indicator_code_used(row: pd.Series) -> list[dict]:
    """Return whether incorrect indicator codes were used in the model's retrieve_value tool calls.

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted tool calls.

    Returns
    -------
    list[dict]
        List of tool calls where the retrieve_value tool was used with incorrect indicator codes.

    """
    incorrect_code_used = False
    for call in row['pred_tool_calls']:
        if call['name'] == 'retrieve_value':
            indicator_code = call['arguments']['indicator_code']
            # Check if this code is == df['slot_values']['property']
            if indicator_code != row['slot_values']['property']:
                incorrect_code_used = True
                break

    return incorrect_code_used


# For coverage/recall, the current implementation is correct and standard:
# it matches each gold tool call to a unique prediction (no double-counting),
# and returns the fraction of gold tool calls that are present in the predictions.
# This is equivalent to recall in information retrieval.

# The true positives/false positives logic in get_precision is for precision (fraction of predicted calls that are correct).
# For recall/coverage, you want the fraction of gold calls that are found in predictions,
# which is what your get_coverage function already does.


# If you want to compute recall using the true positives from get_true_false_positives, you could do:
def get_recall(row: pd.Series) -> float:
    """Calculate recall: proportion of gold tool calls found in predictions."""
    gold = row['gold_tool_calls']
    return len(row['true_positives']) / len(gold) if gold else 1.0


# But your current get_coverage function is equivalent and more robust to double-counting.
# So you do NOT need to use the true positives/false positives logic for recall/coverage.
# Use get_true_false_positives only for precision (and F1 if you want).
