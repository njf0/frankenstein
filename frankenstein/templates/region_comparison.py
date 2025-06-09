"""Template for region comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import NaryOperator, Property, Region, Year


class RegionComparison(FrankensteinQuestion):
    """Class representing a region comparison question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a region comparison question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'Which country in the region of {region} had the {operator} {property} in {year}?',
            'In {region}, which country had the {operator} {property} in {year}?',
            'For the countries in {region}, which had the {operator} {property} in {year}?',
        )

        allowed_values = {
            'region': Region,
            'operator': NaryOperator,
            'property': Property,
            'year': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'str'

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
            action = FrankensteinAction('get_country_code_from_name', country_name=self.c2n[country])
            action.execute()
            self.actions.append(action.to_dict())
            country_code = action.result

            action = FrankensteinAction(
                'retrieve_value', country_code=country_code, indicator_code=indicator_code, year=self.year
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result

            property_values.append((country_code, value))

        # Check if all values are missing
        if all(v[1] is None for v in property_values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Check if any values are missing
        if any(v[1] is None for v in property_values):
            self.metadata['data_availability'] = 'partial'

        # Use maximum or minimum tool to find the target value
        values = [v[1] for v in property_values if v[1] is not None]
        if self.operator == 'highest':
            action = FrankensteinAction('maximum', values=values)
        elif self.operator == 'lowest':
            action = FrankensteinAction('minimum', values=values)
        action.execute()
        self.actions.append(action.to_dict())
        target_value = action.result

        target_country = next((c for c, v in property_values if v == target_value), None)

        # Check if the required value is missing
        if target_country is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=self.c2n[target_country])
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        self.metadata['data_availability'] = 'full'

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionComparison question.')
    parser.add_argument('--region', type=str, choices=Region.get_values(), help='The region to compare.')
    parser.add_argument('--operator', type=str, choices=NaryOperator.get_values(), help='The operator to use for comparison.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--year', type=str, choices=Year.get_values(), help='The year to compare.')

    args = parser.parse_args()

    q = RegionComparison()
    if all(
        [
            args.region,
            args.operator,
            args.property,
            args.year,
        ]
    ):
        comb = {
            'region': args.region,
            'operator': args.operator,
            'property': args.property,
            'year': args.year,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
