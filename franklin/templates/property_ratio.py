"""Template for property ratio questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import Property, SubjectSet, Time


class PropertyRatio(FranklinQuestion):
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
            'What was the ratio of the highest value to the lowest for the {property} of {subject_set} in {time}?',
            'In {subject_set}, what was the ratio of the highest value of {property} to the lowest in {time}?',
            'In {time}, what was the ratio of the highest value of {property} to the lowest for {subject_set}?',
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
        action = FranklinAction('get_country_codes_in_region', region_name=self.subject_set)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # Get the indicator code for the property
        action = FranklinAction('get_indicator_code_from_name', indicator_name=self.i2n[self.property])
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Retrieve the property values for the countries
        property_values = []
        for country in countries:
            action = FranklinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.time,  # Use the time slot
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            property_values.append(value)

        # Check if any values are missing
        if any(value is None for value in property_values):
            self.metadata['data_availability'] = 'partial'

        if all(value is None for value in property_values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Find the highest and lowest values
        action = FranklinAction('maximum', values=property_values)
        action.execute()
        self.actions.append(action.to_dict())
        max_value = action.result

        action = FranklinAction('minimum', values=property_values)
        action.execute()
        self.actions.append(action.to_dict())
        min_value = action.result

        # Compute the ratio
        if min_value == 0:
            self.metadata['data_availability'] = 'partial'

            return

        action = FranklinAction('divide', value_a=max_value, value_b=min_value)
        action.execute()
        self.actions.append(action.to_dict())
        ratio = action.result

        # Set the final answer
        action = FranklinAction('final_answer', answer=ratio)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a PropertyRatio question.')
    parser.add_argument('--subject_set', type=str, choices=SubjectSet.get_values(), help='The region to use.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to use.')
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time to use.')  # Add time

    args = parser.parse_args()

    q = PropertyRatio()
    if all([args.subject_set, args.property, args.time]):
        comb = {
            'subject_set': args.subject_set,
            'property': args.property,
            'time': args.time,  # Add time
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
