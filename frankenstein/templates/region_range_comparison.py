"""Template for region range comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import BinaryOperator, Property, Region, Year


class RegionRangeComparison(FrankensteinQuestion):
    """Class representing a region range comparison question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a region range comparison question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'Did {region_a} have a {operator} range of values for {property} than {region_b} in {year}?',
            'In {year}, did {region_a} have a {operator} range of values for {property} than {region_b}?',
            'In {region_a}, was the range of values for {property} {operator} than that of {region_b} in {year}?',
        )

        allowed_values = {
            'region_a': Region,
            'region_b': Region,
            'operator': BinaryOperator,
            'property': Property,
            'year': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'bool'

    def validate_combination(self, combination: dict) -> bool:
        """Ensure region_a and region_b are different."""
        return combination['region_a'] != combination['region_b']

    def compute_actions(self):
        """Compute actions for the question."""
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

        region_ranges = {}
        for region in [self.region_a, self.region_b]:
            # Get the countries in the region
            action = FrankensteinAction(
                'get_country_codes_in_region',
                region=region,
            )
            action.execute()
            self.actions.append(action.to_dict())
            countries = action.result

            # Retrieve the property values for the countries
            values = []
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
                values.append(value)

            # Check for missing data
            if any(v is None for v in values):
                self.metadata['data_availability'] = 'partial'

            if all(v is None for v in values):
                self.metadata['data_availability'] = 'missing'
                self.metadata['answerable'] = False
                return

            # Remove None values
            values = [v for v in values if v is not None]

            # Compute the range (max - min)
            action = FrankensteinAction('maximum', values=values)
            action.execute()
            self.actions.append(action.to_dict())
            max_value = action.result

            action = FrankensteinAction('minimum', values=values)
            action.execute()
            self.actions.append(action.to_dict())
            min_value = action.result

            action = FrankensteinAction('subtract', value_a=max_value, value_b=min_value)
            action.execute()
            self.actions.append(action.to_dict())
            region_ranges[region] = action.result

        # Compare the ranges using the operator
        if self.operator == 'higher':
            action = FrankensteinAction(
                'greater_than', value_a=region_ranges[self.region_a], value_b=region_ranges[self.region_b]
            )
        elif self.operator == 'lower':
            action = FrankensteinAction(
                'greater_than', value_a=region_ranges[self.region_b], value_b=region_ranges[self.region_a]
            )

        action.execute()
        self.actions.append(action.to_dict())
        comparison_result = action.result

        # Set the final answer
        self.answer = comparison_result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionRangeComparison question.')
    parser.add_argument('--region_a', type=str, choices=Region.get_values(), help='The first region to compare.')
    parser.add_argument('--region_b', type=str, choices=Region.get_values(), help='The second region to compare.')
    parser.add_argument('--operator', type=str, choices=['higher', 'lower'], help='The operator to use for comparison.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--year', type=str, choices=Year.get_values(), help='The year to compare.')

    args = parser.parse_args()

    q = RegionRangeComparison()
    if all([args.region_a, args.region_b, args.operator, args.property, args.year]):
        comb = {
            'region_a': args.region_a,
            'region_b': args.region_b,
            'operator': args.operator,
            'property': args.property,
            'year': args.year,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
