"""Flexible answer matcher that can handle various answer formats."""

import ast
import logging


class Matcher:
    """Flexible answer matcher using answer_format from metadata.

    Provides methods for matching predicted and gold answers of various types,
    returning a percent error (0.0 for exact match, 100.0 for mismatch).
    """

    def __init__(self):
        """Initialize the Matcher."""
        pass

    def match(
        self,
        pred: str,
        gold: str,
        answer_format: str | None = None,
    ) -> tuple[bool, float]:
        """Match predicted and gold answers using the specified answer format.

        Returns
        -------
        (bool, float)
            Tuple of (correct, percent_error).

        """
        self.percent_tolerance = 0.01  # 0.01% tolerance for float matching

        if answer_format == 'float':
            return self.match_float(pred, gold)
        elif answer_format == 'bool':
            return self.match_bool(pred, gold)
        elif answer_format == 'list':
            return self.match_list(pred, gold)
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
        logging.info(f'🔬 Matcher().match_float(pred = {pred!r}, gold = {gold!r})')

        try:
            pred_f = float(ast.literal_eval(pred))
            gold_f = float(gold)
            logging.info(f'🔬 Parsed pred: {pred_f}')
            logging.info(f'🔬 Parsed gold: {gold_f}')
            percent_error = abs(pred_f - gold_f) * 100 if gold_f == 0 else abs(pred_f - gold_f) / abs(gold_f) * 100

        except Exception as e:
            logging.warning(f'🔬 Exception parsing float values: {e}')
            percent_error = 100.0

        correct = percent_error <= 0.01
        if correct:
            logging.info(f'✅ Correct within {self.percent_tolerance}% tolerance.')
        else:
            logging.warning(f'❌ Incorrect. Answer {pred_f!r} differs from gold {gold_f!r} by {percent_error:.2f}%')

        return correct, percent_error

    def match_bool(self, pred: str, gold: str) -> tuple[bool, float]:
        """Match boolean values.

        Returns
        -------
        (bool, float)
            Tuple of (correct, percent_error).

        """
        logging.info(f'🔬 Matcher().match_bool(pred = {pred!r}, gold = {gold!r})')
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
            logging.warning(f'🔬 Exception parsing pred: {e}. Using fallback parsing.')
            pred_val = pred

        gold_val = gold

        pred_bool = bool_map.get(str(pred_val).strip().lower(), pred_val)
        logging.info(f'🔬 Parsed pred: {pred_bool}')
        gold_bool = bool_map.get(str(gold_val).strip().lower(), gold_val)
        logging.info(f'🔬 Parsed gold: {gold_bool}')

        correct = bool(pred_bool) == bool(gold_bool)
        if correct:
            logging.info('✅ Correct boolean match.')
        else:
            logging.warning(f'❌ Incorrect boolean match. Received: {pred_bool!r}, expected: {gold_bool!r}')

        percent_error = 0.0 if correct else 100.0
        return correct, percent_error

    def match_list(self, pred: str, gold: str) -> tuple[bool, float]:
        """Match list-formatted strings, e.g., "['a', 'b']" or "['a', 'b', 'c']".

        Returns
        -------
        (bool, float)
            Tuple of (correct, percent_error). If not correct, percent_error is delta in length.

        """
        logging.info(f'🔬 Matcher().match_list(pred = {pred!r}, gold = {gold!r})')

        # Attempt to parse the predicted and gold values as lists. If parsing fails, fallback to simple string splitting.
        try:
            pred_list = ast.literal_eval(pred.strip())
            gold_list = gold
            logging.info(f'🔬 Parsed pred: {pred_list}.')
            logging.info(f'🔬 Parsed gold: {gold_list}.')
        except Exception as e:
            logging.warning(f'🔬 Failed to parse pred: {e}. Using fallback parsing.')
            pred_list = [item.strip() for item in pred.strip('[](){}').split(',') if item.strip()]
            gold_list = (
                gold
                if isinstance(gold, list)
                else [item.strip() for item in str(gold).strip('[](){}').split(',') if item.strip()]
            )
            logging.info(f'🔬 Fallback pred_list: {pred_list} | fallback gold_list: {gold_list}')

        # If both are lists, compare them as sets for order-insensitive matching.
        if isinstance(pred_list, list) and isinstance(gold_list, list):
            pred_set = set(pred_list)
            logging.info(f'🔬 Pred set: {pred_set}')
            gold_set = set(gold_list)
            logging.info(f'🔬 Gold set: {gold_set}')
            correct = pred_set == gold_set
            percent_error = 0.0 if correct else float(abs(len(pred_list) - len(gold_list)))
            if correct:
                logging.info('✅ Correct match (order-insensitive).')
            else:
                logging.warning(f'❌ Incorrect match (order-insensitive). Set difference: {pred_set ^ gold_set}')
            return correct, percent_error
        else:
            logging.warning('🔬 One or both values are not lists.')
            return False, 100.0

    def match_int(self, pred: str, gold: str) -> tuple[bool, float]:
        """Match integer values.

        Returns
        -------
        (bool, float)
            Tuple of (correct, percent_error). If not correct, percent_error is delta.

        """
        logging.info(f'🔬 Matcher().match_int(pred = {pred!r}, gold = {gold!r})')

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
        logging.info(f'🔬 Matcher().match_str(pred = {pred!r}, gold = {gold!r})')
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
