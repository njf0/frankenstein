"""Flexible answer matcher that can handle various answer formats."""

import ast
import json
import logging
import re

import pandas as pd


class Matcher:
    """Flexible answer matcher using answer_format from metadata."""

    def __init__(self, percent_tolerance: float = 0.01):
        """Initialize the Matcher."""
        self.percent_tolerance = percent_tolerance

    def extract_final_answer(self, messages):
        """Extract the final answer from a list of messages (dicts)."""
        final_answer = None
        for message in messages:
            if message.get('role') == 'assistant' and message.get('tool_calls'):
                for tool_call in message['tool_calls']:
                    if tool_call.get('function', {}).get('name') == 'final_answer':
                        arguments = tool_call['function']['arguments']
                        # Fix: Only parse if arguments is a string
                        if isinstance(arguments, str):
                            parsed_args = json.loads(arguments)
                        elif isinstance(arguments, dict):
                            parsed_args = arguments
                        else:
                            parsed_args = {}
                        final_answer = parsed_args.get('answer')
                        break
            if final_answer is not None:
                break
        return final_answer

    def match(
        self,
        pred,
        gold: str,
        answer_format: str | None = None,
    ) -> tuple[bool, float]:
        """Match predicted and gold answers using the specified answer format.

        If pred is a list of messages, extract the final answer.
        """
        # If pred is a list of dicts (messages), extract the final answer
        if isinstance(pred, list) and pred and isinstance(pred[0], dict):
            pred = self.extract_final_answer(pred)
        # Accept both 'list' and 'list[str]' as list formats
        if answer_format in ('list', 'list[str]', 'list[int]', 'list[float]'):
            return self.match_list(pred, gold)
        elif answer_format == 'float':
            return self.match_float(pred, gold)
        elif answer_format == 'bool':
            return self.match_bool(pred, gold)
        elif answer_format == 'int':
            return self.match_int(pred, gold)
        elif answer_format == 'str':
            return self.match_str(pred, gold)
        else:
            return self.match_fallback(pred, gold)

    def match_float(
        self,
        pred: str,
        gold: str,
    ) -> tuple[bool, float]:
        """Match float values with percent error.

        Returns
        -------
        (bool, float)
            Tuple of (correct, percent_error).

        """
        logging.info(f'🔬 Matcher().match_float(pred={pred!r}, gold={gold!r})')

        # Attempt to parse both pred and gold as floats
        try:
            pred_f = float(ast.literal_eval(pred))
            gold_f = float(gold)
            logging.info(f'🔬 Parsed pred: {pred_f}')
            logging.info(f'🔬 Parsed gold: {gold_f}')
            percent_error = abs(pred_f - gold_f) * 100 if gold_f == 0 else abs(pred_f - gold_f) / abs(gold_f) * 100
            correct = percent_error <= 0.01

        # If parsing fails, try to handle common cases
        except Exception as e:
            logging.warning(f'🔬 Exception parsing float values: {e}')

            # Fallback: check if gold value as string is present in pred string
            gold_str = str(gold).strip()
            if gold_str in str(pred):
                logging.info(f'✅ Gold value {gold_str!r} found in prediction string (fallback).')
                return True, 0.0

            # Further fallback: extract any float from pred and compare
            try:
                gold_f = float(gold)
                float_pattern = r'[-+]?\d*\.\d+|\d+'
                found_floats = [float(x) for x in re.findall(float_pattern, str(pred))]
                for f in found_floats:
                    percent_error = abs(f - gold_f) * 100 if gold_f == 0 else abs(f - gold_f) / abs(gold_f) * 100
                    if percent_error <= 0.01:
                        logging.info(f'✅ Found matching float {f} in prediction string (regex fallback).')
                        return True, 0.0
                logging.warning('❌ No matching float found in prediction string (regex fallback).')
            except Exception as e2:
                logging.warning(f'🔬 Exception in regex float extraction: {e2}')

            percent_error = 100.0
            correct = False
            pred_f = None
            gold_f = None

        if correct:
            logging.info(f'✅ Correct within {self.percent_tolerance}% tolerance.')
        else:
            logging.warning(f'❌ Incorrect. Answer {pred_f!r} differs from gold {gold_f!r} by {percent_error:.2f}%')

        logging.info(f'🔬 Percent error value: {percent_error}')

        return correct, percent_error

    def match_bool(self, pred: str, gold: str) -> tuple[bool, float]:
        """Match boolean values.

        Returns
        -------
        (bool, float)
            Tuple of (correct, percent_error).

        """
        logging.info(f'🔬 Matcher().match_bool(pred={pred!r}, gold={gold!r})')
        bool_map = {
            'true': True,
            'false': False,
            'Yes': True,
            'No': False,
            'yes': True,
            'no': False,
        }

        try:
            pred_val = ast.literal_eval(pred)
        except Exception as e:
            logging.warning(f'🔬 Exception parsing pred: {e}. Falling back to mapping.')
            pred_val = pred

        gold_val = gold

        pred_bool = bool_map.get(str(pred_val).strip().lower(), pred_val)
        logging.info(f"🔬 Parsed pred '{pred}' -> {pred_bool}")

        correct = bool(pred_bool) == bool(gold_val)
        if correct:
            logging.info('✅ Correct boolean match.')
        else:
            logging.warning(f'❌ Incorrect boolean match. Received: {pred_bool!r}, expected: {gold_val!r}')

        percent_error = 0.0 if correct else 100.0
        return correct, percent_error

    def match_list(
        self,
        pred: str,
        gold: str,
    ) -> tuple[bool, float]:
        """Match list-formatted answers, e.g., "['a', 'b']", or comma-separated strings e.g., "a, b".

        Returns
        -------
        (bool, float)
            Tuple of (correct, percent_error). If not correct, percent_error is delta.

        """
        logging.info(f'🔬 Matcher().match_list(pred={pred!r}, gold={gold!r})')

        # Parse pred to list
        try:
            pred_list = ast.literal_eval(pred.strip()) if isinstance(pred, str) else pred
        except Exception as e:
            logging.warning(f'🔬 Failed to parse pred: {e}. Using fallback parsing.')
            pred_list = [item.strip() for item in str(pred).strip('[](){}').split(',') if item.strip()]

        # Gold may already be a list, or a string representation of a list
        if isinstance(gold, list):
            gold_list = gold
        else:
            try:
                gold_list = ast.literal_eval(str(gold).strip())
            except Exception as e:
                logging.warning(f'🔬 Failed to parse gold: {e}. Using fallback parsing.')
                gold_list = [item.strip() for item in str(gold).strip('[](){}').split(',') if item.strip()]

        # Log parsed values
        logging.info(f'🔬 Parsed pred_list: {pred_list}')
        logging.info(f'🔬 Parsed gold_list: {gold_list}')

        # Compare as sets (order-insensitive)
        if isinstance(pred_list, list) and isinstance(gold_list, list):
            pred_set = {str(x) for x in pred_list}
            gold_set = {str(x) for x in gold_list}
            correct = pred_set == gold_set
            percent_error = 0.0 if correct else float(abs(len(pred_list) - len(gold_list)))

            if correct:
                logging.info('✅ Correct set match.')
            else:
                missing = gold_set - pred_set
                extra = pred_set - gold_set
                logging.warning('❌ Set mismatch')
                logging.warning(f'🔬 Correct: {gold_set & pred_set}')
                logging.warning(f'🔬 Missing: {missing}')
                logging.warning(f'🔬 Extra: {extra}')

            return correct, percent_error

        else:
            logging.warning('🔬 One or both values are not lists after parsing.')
            return False, 100.0

    def match_int(self, pred: str, gold: str) -> tuple[bool, float]:
        """Match integer values.

        Returns
        -------
        (bool, float)
            Tuple of (correct, percent_error). If not correct, percent_error is delta.

        """
        logging.info(f'🔬 Matcher().match_int(pred={pred!r}, gold={gold!r})')

        try:
            pred_i = int(ast.literal_eval(pred))
            gold_i = int(gold)
            logging.info(f'🔬 Parsed pred: {pred_i}')
            logging.info(f'🔬 Parsed gold: {gold_i}')
            correct = pred_i == gold_i
            percent_error = 0.0 if correct else float(pred_i - gold_i)
            if correct:
                logging.info('✅ Correct match.')
            else:
                logging.warning(f'❌ Incorrect match. Predicted: {pred_i}, Gold: {gold_i}, Delta: {percent_error}')

            return correct, percent_error

        except Exception as e:
            logging.warning(f'🔬 Exception parsing int values: {e}')
            return False, 100.0

    def match_str(self, pred: str, gold: str) -> tuple[bool, float]:
        """Match string values (case-insensitive, whitespace-stripped).

        Returns
        -------
        (bool, float)
            Tuple of (correct, percent_error).

        """
        logging.info(f'🔬 Matcher().match_str(pred={pred!r}, gold={gold!r})')
        pred_str = str(pred).strip().lower()
        gold_str = str(gold).strip().lower()
        logging.info(f'🔬 Parsed pred: {pred_str}')
        logging.info(f'🔬 Parsed gold: {gold_str}')
        correct = pred_str == gold_str
        percent_error = 0.0 if correct else 100.0
        if correct:
            logging.info('✅ Correct string match.')
        else:
            logging.warning(f'❌ Incorrect string match. Predicted: {pred_str!r}, Gold: {gold_str!r}')

        return correct, percent_error

    def match_fallback(self, pred: str, gold: str) -> tuple[bool, float]:
        """Try all matchers in order until one matches exactly.

        Returns
        -------
        (bool, float)
            Tuple of (correct, percent_error).

        """
        logging.info(f'🔬 Matcher() match_fallback | Trying all matchers for pred: {pred!r} | gold: {gold!r}')
        for fmt in ('float', 'bool', 'list', 'int', 'str'):
            correct, percent_error = self.match(pred, gold, fmt)
            if correct:
                logging.info(f'🔬 Matcher() match_fallback | Matched using format: {fmt}')
                return True, percent_error
        logging.warning('🔬 Matcher() match_fallback | No matcher succeeded.')
        return False, 100.0

    def match_row(self, row: pd.Series):
        """Match a DataFrame row by extracting messages, gold answer, and answer format.

        Parameters
        ----------
        row : pd.Series
            A row from a DataFrame containing at least 'messages', 'answer', and optionally 'metadata'.

        Returns
        -------
        (bool, float)
            Tuple of (correct, percent_error).

        """
        messages = row.get('messages')
        gold = row.get('answer')
        answer_format = None
        metadata = row.get('metadata')
        if isinstance(metadata, dict):
            answer_format = metadata.get('answer_format')
        return self.match(messages, gold, answer_format)
