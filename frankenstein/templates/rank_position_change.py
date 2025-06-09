"""Template for rank position change questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import NaryOperator, Number, Property, Region, Year


class RankPositionChange(FrankensteinQuestion):
    """Class representing a rank position change question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a rank position change question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'For the countries in {region}, did the country with the {n} {operator} {property} in {year_a} retain that position in {year_b}?',
            'Did the country ranked {n} {operator} for {property} in {year_a} in {region} keep the same rank in {year_b}?',
            'In {region}, did the country with the {n} {operator} {property} in {year_a} keep that position in {year_b}?',
        )

        allowed_values = {
            'region': Region,
            'n': Number,
            'operator': NaryOperator,
            'property': Property,
            'year_a': Year,
            'year_b': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'bool'

    def validate_combination(self, combination: dict) -> bool:
        """Ensure year_a != year_b and n is valid."""
        return combination['year_a'] != combination['year_b']

    def compute_actions(self):
        """Compute actions for the question."""
        # Get countries in the region
        action = FrankensteinAction('get_country_codes_in_region', region=self.region)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # Get the indicator code for the property
        action = FrankensteinAction('get_indicator_code_from_name', indicator_name=self.i2n[self.property])
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Retrieve property values for all countries in year_a
        values_a = []
        for country in countries:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.year_a,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            if value is not None:
                values_a.append((country, value))

        if not values_a:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Sort values for year_a
        reverse = self.operator == 'highest'
        sorted_a = sorted(values_a, key=lambda x: x[1], reverse=reverse)
        n_idx = int(self.n) - 1
        if n_idx >= len(sorted_a):
            self.metadata['data_availability'] = 'partial'
            self.metadata['answerable'] = False
            return

        target_country = sorted_a[n_idx][0]
        target_value_a = sorted_a[n_idx][1]

        # Retrieve property values for all countries in year_b
        values_b = []
        for country in countries:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.year_b,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            if value is not None:
                values_b.append((country, value))

        if not values_b:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Sort values for year_b
        sorted_b = sorted(values_b, key=lambda x: x[1], reverse=reverse)
        values_b_list = [v for _, v in sorted_b]

        # Get the value for the target country in year_b
        target_value_b = next((v for c, v in values_b if c == target_country), None)
        if target_value_b is None:
            self.metadata['data_availability'] = 'partial'
            self.metadata['answerable'] = False
            return

        # Find index of target country in sorted_b (i.e., its position in year_b)
        action = FrankensteinAction('index', values=values_b_list, query_value=target_value_b)
        action.execute()
        self.actions.append(action.to_dict())
        index_b = action.result

        if index_b is None or index_b == -1:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Compare the index in year_b to n_idx
        retained = index_b == n_idx

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=retained)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RankPositionChange question.')
    parser.add_argument('--region', type=str, choices=Region.get_values(), help='The region to check.')
    parser.add_argument('--n', type=str, choices=Number.get_values(), help='The rank position to check.')
    parser.add_argument('--operator', type=str, choices=NaryOperator.get_values(), help='The operator (highest/lowest).')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to check.')
    parser.add_argument('--year_a', type=str, choices=Year.get_values(), help='The first year.')
    parser.add_argument('--year_b', type=str, choices=Year.get_values(), help='The second year.')

    args = parser.parse_args()

    q = RankPositionChange()
    if all([args.region, args.n, args.operator, args.property, args.year_a, args.year_b]):
        comb = {
            'region': args.region,
            'n': args.n,
            'operator': args.operator,
            'property': args.property,
            'year_a': args.year_a,
            'year_b': args.year_b,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
