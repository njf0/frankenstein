"""Template for region comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import BinaryOperator, Property, Subject, Year


class CountryPropertyComparison(FrankensteinQuestion):
    """Class representing a CountryPropertyComparison question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a CountryPropertyComparison question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'Did {subject_a} have a {operator} {property} in {year_a} than {subject_b} had in {year_b}?',
            'Was the {property} of {subject_a} in {year_a} {operator} than that of {subject_b} in {year_b}?',
            'In {year_a}, was the {property} of {subject_a} {operator} than that of {subject_b} in {year_b}?',
            "In {year_a}, was {subject_a}'s {property} {operator} than {subject_b}'s in {year_b}?",
        )

        allowed_values = {
            'subject_a': Subject,
            'property': Property,
            'operator': BinaryOperator,
            'subject_b': Subject,
            'year_a': Year,
            'year_b': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'bool'

    def validate_combination(self, combination: dict) -> bool:
        """Validate the combination of slot values.

        Ensure subject_a != subject_b and year_a != year_b.

        Parameters
        ----------
        combination: dict
            A combination of slot values.

        Returns
        -------
        bool
            True if the combination is valid, False otherwise.

        """
        return combination['subject_a'] != combination['subject_b'] and combination['year_a'] != combination['year_b']

    def compute_actions(self):
        """Compute result for the question using FrankensteinActions."""
        # Get the country code for subject_a
        action = FrankensteinAction(
            'get_country_code_from_name',
            country_name=self.c2n[self.subject_a],
        )
        action.execute()
        self.actions.append(action.to_dict())
        country_a = action.result

        # Get the country code for subject_b
        action = FrankensteinAction(
            'get_country_code_from_name',
            country_name=self.c2n[self.subject_b],
        )
        action.execute()
        self.actions.append(action.to_dict())
        country_b = action.result

        # Search for the indicator code for the property (for traceability)
        action = FrankensteinAction(
            'search_for_indicator_codes',
            keywords=self.i2n[self.property],
        )
        action.execute()
        action.result = [d for d in action.result if d['indicator_name'] == self.i2n[self.property]]
        self.actions.append(action.to_dict())
        # Use the property slot value directly as the indicator code
        indicator_code = self.slot_values['property']

        # Retrieve the values for the subjects at the given years
        action = FrankensteinAction(
            'retrieve_value',
            country_code=country_a,
            indicator_code=indicator_code,
            year=self.year_a,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value_a = action.result

        action = FrankensteinAction(
            'retrieve_value',
            country_code=country_b,
            indicator_code=indicator_code,
            year=self.year_b,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value_b = action.result

        # Check if values are missing
        if value_a is None and value_b is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False

            return

        elif value_a is None or value_b is None:
            self.metadata['data_availability'] = 'partial'
            self.metadata['answerable'] = False

            return

        # Compare the values
        if self.operator == 'higher':
            action = FrankensteinAction(
                'greater_than',
                value_a=value_a,
                value_b=value_b,
            )
        elif self.operator == 'lower':
            action = FrankensteinAction(
                'greater_than',
                value_a=value_b,
                value_b=value_a,
            )
        action.execute()
        self.actions.append(action.to_dict())

        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a CountryPropertyComparison question.')
    parser.add_argument(
        '--subject_a',
        type=str,
        choices=Subject.get_values(),
        help='The first subject to retrieve the property for.',
    )
    parser.add_argument(
        '--operator',
        type=str,
        choices=BinaryOperator.get_values(),
        help='The operator to use for comparison.',
    )
    parser.add_argument(
        '--property',
        type=str,
        choices=Property.get_values(),
        help='The property to retrieve.',
    )
    parser.add_argument(
        '--subject_b',
        type=str,
        choices=Subject.get_values(),
        help='The second subject to retrieve the property for.',
    )
    parser.add_argument(
        '--year_a',
        type=str,
        choices=Year.get_values(),
        help='The year at which to retrieve the property.',
    )
    parser.add_argument(
        '--year_b',
        type=str,
        choices=Year.get_values(),
        help='The year at which to retrieve the property.',
    )

    args = parser.parse_args()

    q = CountryPropertyComparison()
    if all(
        [
            args.subject_a,
            args.operator,
            args.property,
            args.subject_b,
            args.year_a,
            args.year_b,
        ]
    ):
        comb = {
            'subject_a': args.subject_a,
            'operator': args.operator,
            'property': args.property,
            'subject_b': args.subject_b,
            'year_a': args.year_a,
            'year_b': args.year_b,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
