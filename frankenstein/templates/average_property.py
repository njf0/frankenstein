"""Template for total property value questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Region, Year


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
            'What was the average {property} of the countries in {region} in {year}?',
            'For the countries in {region}, what was the average {property} in {year}?',
            'In {year}, what was the average {property} of the countries in {region}?',
        )

        allowed_values = {
            'region': Region,
            'property': Property,
            'year': Year,
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

        # Search for the indicator code for the property (for traceability)
        action = FrankensteinAction(
            'search_for_indicator_names',
            keywords=self.i2n[self.property],
        )
        action.execute()
        action.result = [d for d in action.result if d['indicator_name'] == self.i2n[self.property]]
        self.actions.append(action.to_dict())

        # Now get the indicator code from the name
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
                year=self.year,
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
        action = FrankensteinAction('mean', values=[i for i in indicator_values if i is not None])
        action.execute()
        self.actions.append(action.to_dict())
        value = action.result

        # Set the answer (no final_answer action)
        self.answer = value

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
    parser.add_argument('--year', type=str, choices=Year.get_values(), help='The year.')

    args = parser.parse_args()

    q = AverageProperty()

    if all(
        [
            args.region,
            args.property,
            args.year,
        ]
    ):
        comb = {
            'region': args.region,
            'property': args.property,
            'year': args.year,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
