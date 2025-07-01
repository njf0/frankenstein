"""Template for total property value questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Region, Year


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
            'What was the total {property} of the countries in the region of {region} in {year}?',
            'In {year}, what was the total {property} of the countries in the region of {region}?',
            'For the countries in the region of {region}, what was the total {property} in {year}?',
        )

        allowed_values = {
            'region': Region,
            'property': Property,
            'year': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'float'

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the countries in the region
        action = FrankensteinAction('get_country_codes_in_region', region=self.region)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # Search for the indicator code for the property (for traceability)
        action = FrankensteinAction(
            'search_for_indicator_codes',
            keywords=self.i2n[self.property],
        )
        action.execute()
        action.result = [d for d in action.result if d['indicator_name'] == self.i2n[self.property]]
        self.actions.append(action.to_dict())
        indicator_code = self.slot_values['property']

        # Retrieve the property values for the countries
        property_values = []
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
        action = FrankensteinAction('add', values=[i for i in property_values if i is not None])
        action.execute()
        self.actions.append(action.to_dict())
        total_value = action.result

        # Set the final answer (no final_answer action)
        self.answer = total_value

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a TotalProperty question.')
    parser.add_argument('--region', type=str, choices=Region.get_values(), help='The region.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property.')
    parser.add_argument('--year', type=str, choices=Year.get_values(), help='The year.')

    args = parser.parse_args()

    q = TotalProperty()
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
