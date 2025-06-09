"""Template for region comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Subject, Year


class FactorIncreaseComparison(FrankensteinQuestion):
    """Class representing a property increase comparison question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a factor increase comparison question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'What was the change in the {property} of {subject} between {year_a} and {year_b}?',
            'By how much did the {property} of {subject} change between {year_a} and {year_b}?',
            'What was the difference in the {property} of {subject} between {year_a} and {year_b}?',
            'Between {year_a} and {year_b}, what was the change in the {property} of {subject}?',
        )

        allowed_values = {
            'subject': Subject,
            'property': Property,
            'year_a': Year,
            'year_b': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'float'

    def validate_combination(self, combination: dict) -> bool:
        """Validate the combination of slot values.

        Parameters
        ----------
        combination: dict
            The combination of slot values to validate.

        Returns
        -------
        bool
            True if the combination is valid, False otherwise.

        """
        # Ensure year_a != year_b and year_a < year_b
        return combination['year_a'] != combination['year_b'] and combination['year_a'] < combination['year_b']

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the country code for the subject
        action = FrankensteinAction(
            'get_country_code_from_name',
            country_name=self.c2n[self.subject],
        )
        action.execute()
        self.actions.append(action.to_dict())
        country_code = action.result

        # Get the indicator code for the property
        action = FrankensteinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Get the values for the property for the subject for both years
        action = FrankensteinAction(
            'retrieve_value',
            country_code=country_code,
            indicator_code=indicator_code,
            year=self.year_a,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value_a = action.result

        # Get the value for the property for the subject for the second year
        action = FrankensteinAction(
            'retrieve_value',
            country_code=country_code,
            indicator_code=indicator_code,
            year=self.year_b,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value_b = action.result

        # Set data availability to 'missing' if all values are missing
        if value_a is None and value_b is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False

            return

        # Set data availability to 'partial' if there is at least one missing value
        if value_a is None or value_b is None:
            self.metadata['data_availability'] = 'partial'
            self.metadata['answerable'] = False

            return

        # Compute the increase
        action = FrankensteinAction(
            'subtract',
            value_a=value_b,
            value_b=value_a,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value = action.result

        # Format the answer
        action = FrankensteinAction(
            'final_answer',
            answer=value,
        )
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a FactorIncreaseComparison question.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to get the property value for.')
    parser.add_argument('--year_a', type=str, choices=Year.get_values(), help='The first year to compare.')
    parser.add_argument('--year_b', type=str, choices=Year.get_values(), help='The second year to compare.')

    args = parser.parse_args()

    q = FactorIncreaseComparison()
    if all(
        [
            args.property,
            args.subject,
            args.year_a,
            args.year_b,
        ]
    ):
        comb = {
            'property': args.property,
            'subject': args.subject,
            'year_a': args.year_a,
            'year_b': args.year_b,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
