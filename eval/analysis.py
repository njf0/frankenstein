"""Analysis helpers for evaluation outputs and tool-call traces."""

import json
from collections import Counter, defaultdict

import numpy as np
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


def get_pred_tool_calls(
    row: pd.Series,
    keep_id: bool = False,
    keep_result: bool = False,
) -> list[dict]:
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
                if keep_result:
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
        if not keep_id:
            call.pop('id', None)
        if not keep_result:
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


def get_incorrect_indicator_code_used(row: pd.Series) -> bool:
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


def get_error_generating_tool_calls(row: pd.Series) -> list[dict]:
    """Return a list of tool calls that resulted in an error when the model attempted to use them.

    First pass: examine the tool call results, checking if any of them indicate an error (e.g., by checking if the result starts with 'Error:'). Store ID of any tool calls that resulted in an error. Then, filter the initial list of predicted tool calls to return only those that resulted in an error.

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted tool calls and their results.

    Returns
    -------
    list[dict]
        List of tool calls (dicts) where the model attempted to use a tool and it resulted in an error.

    """
    error_calls = []
    error_call_ids = set()

    # First pass: identify tool calls that resulted in an error
    for call in row['pred_tool_calls']:
        call_id = call.get('id')
        if call_id is not None:
            # Find the corresponding tool result message
            for msg in row['messages']:
                if msg.get('tool_call_id') == call_id and msg['role'] == 'tool':
                    result = msg.get('content', '')
                    if isinstance(result, str) and (result.startswith('Error:') or result.startswith('could not convert')):
                        error_calls.append(call)
                        error_call_ids.add(call_id)
                    break

    return error_calls


def false_positive_overcall_factor(row: pd.Series) -> dict:
    """Compute a per-tool figure to show the factor by which each tool was called compared to the expected amount.

    False positives are 'things that were called but shouldn't have been', so we want to see how much more each tool was called compared to the expected amount (gold calls).

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted and gold tool calls.

    Returns
    -------
    dict
        A dictionary where the keys are tool names and the values are dictionaries containing:
        - 'factor': the factor by which the tool was called compared to the expected amount (pred / gold)
        - 'delta': the difference in the number of calls (pred - gold)

    """
    gold = Counter(c['name'] for c in row['gold_tool_calls'])
    pred = Counter(c['name'] for c in row['pred_tool_calls'])

    tools = set(gold.keys()) | set(pred.keys())

    out = {}
    for t in tools:
        p = pred.get(t, 0)  # Get the number of calls for this tool in the prediction, defaulting to 0 if not present
        g = gold.get(t, 0)  # Get the expected number of calls for this tool from the gold data, defaulting to 0 if not present

        if g == 0:
            # results in infinity values which are not useful for aggregation
            continue

        out[t] = {
            'factor': p / g,  # Compute the factor by which the tool was called compared to the expected amount
            'delta': int(
                p - g
            ),  # Compute the delta (pred - gold) to see how many more times the tool was called compared to the expected amount
        }

    # only keep elements where delta > 0 (overcalls)
    out = {t: metrics for t, metrics in out.items() if metrics['delta'] >= 0}
    return out


def false_negative_undercall_factor(row: pd.Series) -> dict:
    """Compute a per-tool figure to show the factor by which each tool was called compared to the expected amount.

    False negatives are 'things that weren't called but should have been', so we want to see how much less each tool was called compared to the expected amount (gold calls).

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted and gold tool calls.

    Returns
    -------
    dict
        A dictionary where the keys are tool names and the values are dictionaries containing:
        - 'factor': the factor by which the tool was called compared to the expected amount (pred / gold)
        - 'delta': the difference in the number of calls (pred - gold)

    """
    gold = Counter(c['name'] for c in row['gold_tool_calls'])
    pred = Counter(c['name'] for c in row['pred_tool_calls'])

    tools = set(gold.keys()) | set(pred.keys())

    out = {}
    for t in tools:
        p = pred.get(t, 0)  # Get the number of calls for this tool in the prediction, defaulting to 0 if not present
        g = gold.get(t, 0)  # Get the expected number of calls for this tool from the gold data, defaulting to 0 if not present

        if g == 0:
            # results in infinity values which are not useful for aggregation
            continue

        out[t] = {
            'factor': p / g,  # Compute the factor by which the tool was called compared to the expected amount
            'delta': int(
                p - g
            ),  # Compute the delta (pred - gold) to see how many more times the tool was called compared to the expected amount
        }

    # only keep elements where delta < 0 (undercalls)
    out = {t: metrics for t, metrics in out.items() if metrics['delta'] <= 0}
    return out


def aggregate_tool_factors(
    factors_list_column: pd.Series,
    return_deltas: bool = False,
) -> dict:
    """Sum up per-tool factors to get an overall factor for each row.

    Each item in the column represents a row/run, containing a dict[tool_name, dict[factor, delta,]] of tools.
    This shows the factor and delta to the expected calls.

    Parameters
    ----------
    factors_list_column : pd.Series
        A pandas Series where each item is a dict mapping tool names to their respective factors and deltas for that row/run.
    return_deltas : bool, optional
        If True, return the total deltas for each tool instead of the average factors. Default is False.

    Returns
    -------
    dict
        A dictionary where the keys are tool names and the values are either:
        - If return_deltas is False: the average factor by which each tool was called compared to the expected amount across all rows.
        - If return_deltas is True: the total delta (sum of pred - gold) for each tool across all rows.

    """
    total_factors = {}
    call_factors = defaultdict(list)  # tool_name -> list of factors for that tool across rows, to compute average factor later
    for factors in factors_list_column:
        # factors looks like {'tool_name': {'factor': float, 'delta': int}, ...}
        for tool_name, metrics in factors.items():
            # If the tool is not already in total_factors, initialize it with 0 total_factor and 0 total_delta
            if tool_name not in total_factors:
                total_factors[tool_name] = {'total_factor': 0.0, 'total_delta': 0}

            # Update total delta, which is easy to sum across tools and rows
            total_factors[tool_name]['total_delta'] += metrics['delta']
            call_factors[tool_name].append(
                metrics['factor']
            )  # Keep track of individual factors for this tool to compute average later

    # Finally, update total factor with a simple unweighted average across all rows
    for tool_name, metrics in total_factors.items():
        factors = call_factors[tool_name]
        average_call_factor = sum(factors) / len(factors) if factors else 0.0
        total_factors[tool_name]['total_factor'] = average_call_factor
        total_factors[tool_name]['std_dev_factor'] = np.std(factors)

    # we don't actually want deltas so just return the average factors for each tool
    if return_deltas:
        return {tool_name: metrics['total_delta'] for tool_name, metrics in total_factors.items()}

    return {tool_name: metrics['total_factor'] for tool_name, metrics in total_factors.items()}


def false_positive_overcall_factor_signature(
    row: pd.Series, remove_duplicates: bool = False, include_equal: bool = True
) -> dict:
    """Signature-aware per-tool overcall factor.

    Parameters
    ----------
    row: pd.Series
         A single row from the dataframe row with 'gold_tool_calls' and 'pred_tool_calls'
        remove_duplicates: if True, count only predicted name+args signatures that have zero gold counterparts
        include_equal: if True keep delta == 0 rows (delta >= 0), else keep only delta > 0

    Returns
    -------
        dict[tool_name] -> {'factor': float, 'delta': int}

    """
    gold_by_name = Counter(c['name'] for c in row.get('gold_tool_calls', []) or [])
    pred_by_name = Counter(c['name'] for c in row.get('pred_tool_calls', []) or [])

    def sig(call: dict):
        name = call.get('name')
        args = call.get('arguments', {}) or {}
        try:
            args_ser = json.dumps(args, sort_keys=True, default=lambda o: repr(o))
        except Exception:
            args_ser = repr(args)
        return (name, args_ser)

    gold_sigs = [sig(c) for c in row.get('gold_tool_calls', []) or []]
    pred_sigs = [sig(c) for c in row.get('pred_tool_calls', []) or []]

    gold_sig_counter = Counter(gold_sigs)
    pred_sig_counter = Counter(pred_sigs)

    tools = set(gold_by_name.keys()) | set(pred_by_name.keys())
    out = {}

    for t in tools:
        g = gold_by_name.get(t, 0)
        if g == 0:
            # keep behaviour consistent with existing name-only function: skip tools with no gold occurrences
            continue

        if not remove_duplicates:
            p = pred_by_name.get(t, 0)
        else:
            # count only predicted signatures for this tool that have zero gold counterparts
            p = 0
            for s, p_count in pred_sig_counter.items():
                if s[0] != t:
                    continue
                g_count = gold_sig_counter.get(s, 0)
                if g_count == 0:
                    p += p_count

        out[t] = {'factor': p / g if g else float('inf'), 'delta': int(p - g)}

    if include_equal:
        out = {t: m for t, m in out.items() if m['delta'] >= 0}
    else:
        out = {t: m for t, m in out.items() if m['delta'] > 0}

    return out


def get_answer_produced(row: pd.Series) -> bool:
    """Check if the model produced an answer (i.e., made a final_answer tool call).

    Parameters
    ----------
    row : pd.Series
        A single row from the DataFrame containing the predicted tool calls.

    Returns
    -------
    bool
        True if the model produced an answer (made a final_answer tool call), False otherwise.

    """
    # pred_tool_calls has final_answer calls removed, so we need to look in the messages to see if a final_answer tool call was made
    for msg in row.get('messages', []):
        if 'tool_calls' in msg and isinstance(msg['tool_calls'], list):
            for call in msg['tool_calls']:
                function = call['function']
                if function['name'] == 'final_answer':
                    return True
    return False
