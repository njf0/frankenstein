"""Template for property ratio questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Subject, Year


class PropertyRatioComparison(FrankensteinQuestion):
    """Class representing a property ratio question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a property ratio question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'What was the ratio of the {property} of {subject_a} to {subject_b} in {year}?',
            "In {year}, what was the ratio of {subject_a}'s {property} to {subject_b}'s?",
            "What was the value of {subject_a}'s {property} divided by {subject_b}'s in {year}?",
        )

        allowed_values = {
            'property': Property,
            'subject_a': Subject,
            'subject_b': Subject,
            'year': Year,
        }

        super().__init__(slot_values, allowed_values)
        self.metadata['answer_format'] = 'float'

    def validate_combination(self, combination: dict) -> bool:
        """Ensure subject_a != subject_b."""
        return combination['subject_a'] != combination['subject_b']

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the indicator code for the property
        action = FrankensteinAction('get_indicator_code_from_name', indicator_name=self.i2n[self.property])
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Get the country codes for subject_a and subject_b
        action = FrankensteinAction('get_country_code_from_name', country_name=self.c2n[self.subject_a])
        action.execute()
        self.actions.append(action.to_dict())
        code_a = action.result

        action = FrankensteinAction('get_country_code_from_name', country_name=self.c2n[self.subject_b])
        action.execute()
        self.actions.append(action.to_dict())
        code_b = action.result

        # Retrieve the property values for both subjects
        action = FrankensteinAction(
            'retrieve_value',
            country_code=code_a,
            indicator_code=indicator_code,
            year=self.year,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value_a = action.result

        action = FrankensteinAction(
            'retrieve_value',
            country_code=code_b,
            indicator_code=indicator_code,
            year=self.year,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value_b = action.result

        # Check for missing data
        if value_a is None or value_b is None or value_b == 0:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Compute the ratio
        action = FrankensteinAction('divide', value_a=value_a, value_b=value_b)
        action.execute()
        self.actions.append(action.to_dict())
        ratio = action.result

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=ratio)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a PropertyRatioComparison question.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--subject_a', type=str, choices=Subject.get_values(), help='The first subject.')
    parser.add_argument('--subject_b', type=str, choices=Subject.get_values(), help='The second subject.')
    parser.add_argument('--year', type=str, choices=Year.get_values(), help='The year to compare.')

    args = parser.parse_args()

    q = PropertyRatioComparison()
    if all([args.property, args.subject_a, args.subject_b, args.year]):
        comb = {
            'property': args.property,
            'subject_a': args.subject_a,
            'subject_b': args.subject_b,
            'year': args.year,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
