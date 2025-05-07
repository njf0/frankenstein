"""Template for subject_set comparison questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import Property, Subject, Time


class FactorIncreaseComparison(FranklinQuestion):
    """Class representing a property increase comparison question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a factor increase comparison question."""
        self.template = 'What was the change in the {property} of {subject} between {time_a} and {time_b}?'
        allowed_values = {'subject': Subject, 'property': Property, 'time_a': Time, 'time_b': Time}

        super().__init__(slot_values, allowed_values)

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
        # Ensure time_a != time_b and time_a < time_b
        return combination['time_a'] != combination['time_b'] and combination['time_a'] < combination['time_b']

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the country code for the subject
        action = FranklinAction(
            'get_country_code_from_name',
            country_name=self.c2n[self.subject],
        )
        action.execute()
        self.actions.append(action.to_dict())
        country_code = action.result

        # Get the indicator code for the property
        action = FranklinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Get the values for the property for the subject for both times
        action = FranklinAction(
            'retrieve_value',
            country_code=country_code,
            indicator_code=indicator_code,
            year=self.time_a,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value_a = action.result

        # Get the value for the property for the subject for the second time
        action = FranklinAction(
            'retrieve_value',
            country_code=country_code,
            indicator_code=indicator_code,
            year=self.time_b,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value_b = action.result

        # Set data availability to 'missing' if all values are missing
        if value_a is None and value_b is None:
            self.metadata['answerable'] = False
            self.metadata['data_availability'] = 'missing'
            self.answer = None
            return None

        # Set data availability to 'partial' if there is at least one missing value
        if value_a is None or value_b is None:
            self.metadata['answerable'] = False
            self.metadata['data_availability'] = 'partial'
            self.metadata['answerable'] = False
            self.answer = None
            return

        # Compute the increase
        action = FranklinAction(
            'subtract',
            a=value_b,
            b=value_a,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value = action.result

        # Format the answer
        action = FranklinAction(
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
    parser.add_argument('--time_a', type=str, choices=Time.get_values(), help='The first time to compare.')
    parser.add_argument('--time_b', type=str, choices=Time.get_values(), help='The second time to compare.')

    args = parser.parse_args()

    q = FactorIncreaseComparison()
    if all(
        [
            args.property,
            args.subject,
            args.time_a,
            args.time_b,
        ]
    ):
        comb = {
            'property': args.property,
            'subject': args.subject,
            'time_a': args.time_a,
            'time_b': args.time_b,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
