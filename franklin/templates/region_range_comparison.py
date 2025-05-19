"""Template for region range comparison questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import BinaryOperator, Property, SubjectSet, Time


class RegionRangeComparison(FranklinQuestion):
    """Class representing a region range comparison question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a region range comparison question."""
        self.template = 'Did {region_a} have a {operator} range of values for {property} than {region_b} in {time}?'
        allowed_values = {
            'region_a': SubjectSet,
            'region_b': SubjectSet,
            'operator': BinaryOperator,
            'property': Property,
            'time': Time,
        }
        super().__init__(slot_values, allowed_values)

    def validate_combination(self, combination: dict) -> bool:
        """Ensure region_a and region_b are different."""
        return combination['region_a'] != combination['region_b']

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the indicator code for the property
        action = FranklinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        region_ranges = {}
        for region in [self.region_a, self.region_b]:
            # Get the countries in the region
            action = FranklinAction(
                'get_country_codes_in_region',
                region_name=region,
            )
            action.execute()
            self.actions.append(action.to_dict())
            countries = action.result

            # Retrieve the property values for the countries
            values = []
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
                    values.append(value)

            # Check for missing data
            if any(v is None for v in values):
                self.metadata['data_availability'] = 'partial'

            if all(v is None for v in values):
                self.metadata['data_availability'] = 'missing'
                return

            # Compute the range (max - min)
            action = FranklinAction('maximum', values=values)
            action.execute()
            self.actions.append(action.to_dict())
            max_value = action.result

            action = FranklinAction('minimum', values=values)
            action.execute()
            self.actions.append(action.to_dict())
            min_value = action.result

            action = FranklinAction('subtract', value_a=max_value, value_b=min_value)
            action.execute()
            self.actions.append(action.to_dict())
            region_ranges[region] = action.result

        # Compare the ranges using the operator
        if self.operator == 'higher':
            action = FranklinAction('greater_than', value_a=region_ranges[self.region_a], value_b=region_ranges[self.region_b])
        elif self.operator == 'lower':
            action = FranklinAction('less_than', value_a=region_ranges[self.region_a], value_b=region_ranges[self.region_b])

        action.execute()
        self.actions.append(action.to_dict())
        comparison_result = action.result

        # Set the final answer
        action = FranklinAction('final_answer', answer=comparison_result)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionRangeComparison question.')
    parser.add_argument('--region_a', type=str, choices=SubjectSet.get_values(), help='The first region to compare.')
    parser.add_argument('--region_b', type=str, choices=SubjectSet.get_values(), help='The second region to compare.')
    parser.add_argument('--operator', type=str, choices=['higher', 'lower'], help='The operator to use for comparison.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time to compare.')

    args = parser.parse_args()

    q = RegionRangeComparison()
    if all([args.region_a, args.region_b, args.operator, args.property, args.time]):
        comb = {
            'region_a': args.region_a,
            'region_b': args.region_b,
            'operator': args.operator,
            'property': args.property,
            'time': args.time,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
