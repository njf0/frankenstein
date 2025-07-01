"""Template for region comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import NaryOperator, Number, Property, Region, Year


class TopNTotal(FrankensteinQuestion):
    """Class representing a TopNTotal question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a TopNTotal question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'Which {n} countries in {region} had the {operator} {property} in {year}?',
            'In {region}, which {n} countries had the {operator} {property} in {year}?',
            'In {year}, which {n} countries in {region} had the {operator} {property}?',
        )

        allowed_values = {
            'property': Property,
            'n': Number,
            'region': Region,
            'operator': NaryOperator,
            'year': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'list[str]'

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
            property_values.append((country, value))

        # Check if all values are missing
        if all(v[1] is None for v in property_values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Check if any values are missing
        if any(v[1] is None for v in property_values):
            self.metadata['data_availability'] = 'partial'

        # Use maximum or minimum tool to find the top `n` values
        values = [float(v[1]) for v in property_values if v[1] is not None]
        action = FrankensteinAction('sort', values=values)
        if self.operator == 'highest':
            action.execute()
            self.actions.append(action.to_dict())
            top_values = action.result[-int(self.n) :]
        elif self.operator == 'lowest':
            action.execute()
            self.actions.append(action.to_dict())
            top_values = action.result[: int(self.n)]

        # Get the corresponding countries for the top values
        top_countries = [c for c, v in property_values if v in top_values]

        # Check if the number of top countries is less than `n`
        if len(top_countries) < int(self.n):
            self.metadata['data_availability'] = 'partial'
            return

        # Set the final answer (no final_answer action)
        country_names = []
        for country in top_countries:
            action = FrankensteinAction('get_country_name_from_code', country_code=country)
            action.execute()
            self.actions.append(action.to_dict())
            action.execute()
            country_names.append(action.result)

        self.answer = country_names

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a TopNTotal question.')
    parser.add_argument(
        '--property',
        type=str,
        choices=Property.get_values(),
        help='The property to compare.',
    )
    parser.add_argument(
        '--n',
        type=str,
        choices=Number.get_values(),
        help='The number of countries to compare.',
    )
    parser.add_argument(
        '--operator',
        type=str,
        choices=NaryOperator.get_values(),
        help='The operator to use for comparison.',
    )
    parser.add_argument(
        '--region',
        type=str,
        choices=Region.get_values(),
        help='The region to compare.',
    )
    parser.add_argument('--year', type=str, choices=Year.get_values(), help='The year to compare.')

    args = parser.parse_args()

    q = TopNTotal()
    if all(
        [
            args.property,
            args.n,
            args.operator,
            args.region,
            args.year,
        ]
    ):
        comb = {
            'property': args.property,
            'n': args.n,
            'operator': args.operator,
            'region': args.region,
            'year': args.year,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
