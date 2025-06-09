"""Template for total property value questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Region, Time


class AverageProperty(FrankensteinQuestion):
    """Class representing a mean property value question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a property increase comparison question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'What was the mean {property} of the countries in {region} in {time}?',
            'For the countries in {region}, what was the mean {property} in {time}?',
            'In {time}, what was the mean {property} of the countries in {region}?',
        )

        allowed_values = {
            'region': Region,
            'property': Property,
            'time': Time,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'float'

    def compute_actions(
        self,
    ):
        """Compute result for the question using FrankensteinActions."""
        # Get countries in the region
        action = FrankensteinAction('get_country_codes_in_region', region=self.region)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # Get the indicator code from the property name
        action = FrankensteinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Get the country codes from the country names and then get the value
        indicator_values = []
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
            indicator_values.append(value)

        # Check if any values are missing
        if any(value is None for value in indicator_values):
            self.metadata['data_availability'] = 'partial'

        # Check if all values are missing
        if all(value is None for value in indicator_values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Retrieve the mean value for the region
        action = FrankensteinAction('mean', values=indicator_values)
        action.execute()
        self.actions.append(action.to_dict())
        value = action.result

        # Set the answer
        action = FrankensteinAction('final_answer', answer=value)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate an AverageProperty question.')
    parser.add_argument(
        '--region',
        type=str,
        choices=Region.get_values(),
        help='The region.',
    )
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property.')
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time.')

    args = parser.parse_args()

    q = AverageProperty()

    if all(
        [
            args.region,
            args.property,
            args.time,
        ]
    ):
        comb = {
            'region': args.region,
            'property': args.property,
            'time': args.time,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
