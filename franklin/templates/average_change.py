"""Template for average yearly change questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import Property, Subject, Time


class AverageChange(FranklinQuestion):
    """Class representing an average yearly change question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize an average yearly change question."""
        self.templates = (
            'What was the average yearly change in the {property} in {subject} for each year between {time_a} and {time_b}?',
            'For each year between {time_a} and {time_b}, what was the average yearly change in the {property} in {subject}?',
            "What was the average yearly change in {subject}'s {property} for each year between {time_a} and {time_b}?",
            "For each year between {time_a} and {time_b}, what was the average yearly change in {subject}'s {property}?",
        )
        allowed_values = {
            'property': Property,
            'subject': Subject,
            'time_a': Time,
            'time_b': Time,
        }
        super().__init__(slot_values, allowed_values)

    def validate_combination(
        self,
        combination: dict,
    ) -> bool:
        """Ensure time_a != time_b and time_a < time_b and at least 2 years apart.

        Parameters
        ----------
        combination : dict
            The combination of slot values to validate.

        Returns
        -------
        bool
            True if the combination is valid, False otherwise.

        """
        return (
            combination['time_a'] != combination['time_b']
            and combination['time_a'] < combination['time_b']
            and (int(combination['time_b']) - int(combination['time_a'])) >= 3
        )

    def compute_actions(
        self,
    ):
        """Compute actions for the question."""
        # Get the country code for the subject
        action = FranklinAction(
            'get_country_code_from_name',
            country_name=self.c2n[self.subject],
        )
        action.execute()
        self.actions.append(action.to_dict())
        subject_code = action.result

        # Get the indicator code for the property
        action = FranklinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Collect all yearly values for the subject between time_a and time_b (inclusive)
        years = list(range(int(self.time_a), int(self.time_b) + 1))

        yearly_values = []
        for year in years:
            action = FranklinAction(
                'retrieve_value',
                country_code=subject_code,
                indicator_code=indicator_code,
                year=str(year),
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            yearly_values.append(value)

        # Check for missing data
        if any(v is None for v in yearly_values):
            self.metadata['data_availability'] = 'partial'

        if all(v is None for v in yearly_values):
            self.metadata['data_availability'] = 'missing'
            return

        # Compute yearly changes
        yearly_changes = []
        for i in range(1, len(yearly_values)):
            action = FranklinAction('subtract', value_a=yearly_values[i], value_b=yearly_values[i - 1])
            action.execute()
            self.actions.append(action.to_dict())
            change = action.result
            yearly_changes.append(change)

        # Compute the average yearly change
        action = FranklinAction('mean', values=yearly_changes)
        action.execute()
        self.actions.append(action.to_dict())
        avg_change = action.result

        # Set the final answer
        action = FranklinAction('final_answer', answer=avg_change)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        self.metadata['data_availability'] = 'full'

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate an AverageChange question.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to compare.')
    parser.add_argument('--time_a', type=str, choices=Time.get_values(), help='The first time.')
    parser.add_argument('--time_b', type=str, choices=Time.get_values(), help='The second time.')

    args = parser.parse_args()

    q = AverageChange()
    if all([args.property, args.subject, args.time_a, args.time_b]):
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
