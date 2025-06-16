"""Template for property ratio questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Region, Year


class RegionPropertyRatio(FrankensteinQuestion):
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
            'What was the ratio of the highest value to the lowest for the {property} of {region} in {year}?',
            'In {region}, what was the ratio of the highest value of {property} to the lowest in {year}?',
            'In {year}, what was the ratio of the highest value of {property} to the lowest for {region}?',
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
                year=self.year,  # Use the year slot
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
        action = FrankensteinAction('maximum', values=property_values)
        action.execute()
        self.actions.append(action.to_dict())
        max_value = action.result

        action = FrankensteinAction('minimum', values=property_values)
        action.execute()
        self.actions.append(action.to_dict())
        min_value = action.result

        # Compute the ratio
        if min_value == 0:
            self.metadata['data_availability'] = 'partial'

            return

        action = FrankensteinAction('divide', value_a=max_value, value_b=min_value)
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
    parser = argparse.ArgumentParser(description='Generate a RegionPropertyRatio question.')
    parser.add_argument('--region', type=str, choices=Region.get_values(), help='The region to use.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to use.')
    parser.add_argument('--year', type=str, choices=Year.get_values(), help='The year to use.')

    args = parser.parse_args()

    q = RegionPropertyRatio()
    if all([args.region, args.property, args.year]):
        comb = {
            'region': args.region,
            'property': args.property,
            'year': args.year,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
