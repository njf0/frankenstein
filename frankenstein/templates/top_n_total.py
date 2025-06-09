"""Template for region comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import NaryOperator, Number, Property, Region, Time


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
            'Which {n} countries in {region} had the {operator} {property} in {time}?',
            'In {region}, which {n} countries had the {operator} {property} in {time}?',
            'In {time}, which {n} countries in {region} had the {operator} {property}?',
        )

        allowed_values = {
            'property': Property,
            'n': Number,
            'region': Region,
            'operator': NaryOperator,
            'time': Time,
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

        # Get the indicator code for the property
        action = FrankensteinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
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
                year=self.time,
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

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=[self.c2n[c] for c in top_countries])
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

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
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time to compare.')

    args = parser.parse_args()

    q = TopNTotal()
    if all(
        [
            args.property,
            args.n,
            args.operator,
            args.region,
            args.time,
        ]
    ):
        comb = {
            'property': args.property,
            'n': args.n,
            'operator': args.operator,
            'region': args.region,
            'time': args.time,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
