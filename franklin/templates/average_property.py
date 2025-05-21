"""Template for total property value questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import Property, SubjectSet, Time


class AverageProperty(FranklinQuestion):
    """Class representing a mean property value question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a property increase comparison question."""
        self.templates = (
            'What was the mean {property} of the countries in {subject_set} in {time}?',
            'For the countries in {subject_set}, what was the mean {property} in {time}?',
            'In {time}, what was the mean {property} of the countries in {subject_set}?',
        )

        allowed_values = {'subject_set': SubjectSet, 'property': Property, 'time': Time}

        super().__init__(slot_values, allowed_values)

    def compute_actions(
        self,
    ):
        """Compute result for the question using FranklinActions."""
        # Get countries in the subject_set
        action = FranklinAction('get_country_codes_in_region', region_name=self.subject_set)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # Get the indicator code from the property name
        action = FranklinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Get the country codes from the country names and then get the value
        indicator_values = []
        for country in countries:
            action = FranklinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.time,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result

            if value is not None:
                indicator_values.append(value)
            else:
                self.metadata['data_availability'] = 'partial'

        # Check if lists are empty
        if not indicator_values:
            self.metadata['data_availability'] = 'missing'

            return

        # Check if any values are missing
        if any(value is None for value in indicator_values):
            self.metadata['data_availability'] = 'partial'

            return

        # Retrieve the mean value for the subject_set
        action = FranklinAction('mean', values=indicator_values)
        action.execute()
        self.actions.append(action.to_dict())
        value = action.result

        # Set the answer
        action = FranklinAction('final_answer', answer=value)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate an AverageProperty question.')
    parser.add_argument(
        '--subject_set',
        type=str,
        choices=SubjectSet.get_values(),
        help='The subject set.',
    )
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property.')
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time.')

    args = parser.parse_args()

    q = AverageProperty()

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
