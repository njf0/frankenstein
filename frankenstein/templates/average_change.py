"""Template for average yearly change questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Subject, Year


class AverageChange(FrankensteinQuestion):
    """Class representing an average yearly change question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize an average yearly change question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'What was the average yearly change in the {property} in {subject} for each year between {year_a} and {year_b}?',
            'For each year between {year_a} and {year_b}, what was the average yearly change in the {property} in {subject}?',
            "What was the average yearly change in {subject}'s {property} for each year between {year_a} and {year_b}?",
            "For each year between {year_a} and {year_b}, what was the average yearly change in {subject}'s {property}?",
        )

        allowed_values = {
            'property': Property,
            'subject': Subject,
            'year_a': Year,
            'year_b': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'float'

    def validate_combination(
        self,
        combination: dict,
    ) -> bool:
        """Ensure year_a != year_b and year_a < year_b and at least 2 years apart.

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
            combination['year_a'] != combination['year_b']
            and combination['year_a'] < combination['year_b']
            and (int(combination['year_b']) - int(combination['year_a'])) >= 3
        )

    def compute_actions(
        self,
    ):
        """Compute actions for the question."""
        # Get the country code for the subject
        action = FrankensteinAction(
            'get_country_code_from_name',
            country_name=self.c2n[self.subject],
        )
        action.execute()
        self.actions.append(action.to_dict())
        subject_code = action.result

        # Get the indicator code for the property
        action = FrankensteinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Collect all yearly values for the subject between year_a and year_b (inclusive)
        years = list(range(int(self.year_a), int(self.year_b) + 1))

        yearly_values = []
        for year in years:
            action = FrankensteinAction(
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
            self.metadata['answerable'] = False
            return

        # Compute yearly changes
        yearly_changes = []
        for i in range(1, len(yearly_values)):
            action = FrankensteinAction('subtract', value_a=yearly_values[i], value_b=yearly_values[i - 1])
            action.execute()
            self.actions.append(action.to_dict())
            change = action.result
            yearly_changes.append(change)

        # Compute the average yearly change
        action = FrankensteinAction('mean', values=yearly_changes)
        action.execute()
        self.actions.append(action.to_dict())
        avg_change = action.result

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=avg_change)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate an AverageChange question.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to compare.')
    parser.add_argument('--year_a', type=str, choices=Year.get_values(), help='The first year.')
    parser.add_argument('--year_b', type=str, choices=Year.get_values(), help='The second year.')

    args = parser.parse_args()

    q = AverageChange()
    if all([args.property, args.subject, args.year_a, args.year_b]):
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
