"""Template for total property value questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, SubjectSet, Time


class TotalProperty(FrankensteinQuestion):
    """Class representing a total property value question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a total property value question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'What was the total {property} of the countries in the region of {subject_set} in {time}?',
            'In {time}, what was the total {property} of the countries in the region of {subject_set}?',
            'For the countries in the region of {subject_set}, what was the total {property} in {time}?',
        )

        allowed_values = {
            'subject_set': SubjectSet,
            'property': Property,
            'time': Time,
        }

        super().__init__(slot_values, allowed_values)

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the countries in the subject_set
        action = FrankensteinAction('get_country_codes_in_region', region_name=self.subject_set)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # Get the indicator code for the property
        action = FrankensteinAction('get_indicator_code_from_name', indicator_name=self.i2n[self.property])
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Retrieve the property values for the countries
        property_values = []
        for country in countries:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.time,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            property_values.append(value)

        # Check if all values are missing
        if all(v is None for v in property_values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Check if any values are missing
        if any(v is None for v in property_values):
            self.metadata['data_availability'] = 'partial'

        # Compute the total property value
        action = FrankensteinAction('add', values=property_values)
        action.execute()
        self.actions.append(action.to_dict())
        total_value = action.result

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=total_value)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        self.metadata['data_availability'] = 'full'

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a TotalProperty question.')
    parser.add_argument('--subject_set', type=str, choices=SubjectSet.get_values(), help='The subject set.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property.')
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time.')

    args = parser.parse_args()

    q = TotalProperty()
    if all(
        [
            args.subject_set,
            args.property,
            args.time,
        ]
    ):
        comb = {
            'subject_set': args.subject_set,
            'property': args.property,
            'time': args.time,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
