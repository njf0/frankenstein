"""Template for region comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import NaryOperator, Property, Region, Time


class IncreasePropertyComparison(FrankensteinQuestion):
    """Class representing an IncreasePropertyComparison question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize an IncreasePropertyComparison question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'Which country in {region} had the {operator} increase in {property} between {time_a} and {time_b}?',
            'Between {time_a} and {time_b}, which country in {region} had the {operator} increase in {property}?',
            'For the countries in {region}, which had the {operator} increase in {property} between {time_a} and {time_b}?',
            'In {region}, which country had the {operator} increase in {property} between {time_a} and {time_b}?',
        )

        allowed_values = {
            'region': Region,
            'operator': NaryOperator,
            'property': Property,
            'time_a': Time,
            'time_b': Time,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'list[str]'

    def validate_combination(self, combination: dict) -> bool:
        """Apply constraints to the combination of slot values.

        For this question type, we need to ensure that the two times are not the same, and that time_a is 'before' time_b.

        Parameters
        ----------
        combination: dict
            A combination of slot values.

        Returns
        -------
        bool
            True if the combination is valid, False otherwise.

        """
        return not (combination['time_a'] == combination['time_b'] or combination['time_a'] > combination['time_b'])

    def compute_actions(self):
        """Compute answer in terms of FrankensteinAction."""
        # Get countries in the region
        action = FrankensteinAction(
            'get_country_codes_in_region',
            region=self.region,
        )
        action.execute()
        self.actions.append(action.to_dict())
        countries_in_region = action.result

        # Get the indicator code for the property
        action = FrankensteinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Get the values for each country in the region for both time_a and time_b
        values = []
        for country in countries_in_region:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.time_a,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value_a = action.result

            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.time_b,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value_b = action.result
            values.append((country, value_a, value_b))

        # Check if any values are None
        if any(value_a is None or value_b is None for _, value_a, value_b in values):
            self.metadata['data_availability'] = 'partial'

        # Check if all values are None
        if all(value_a is None and value_b is None for _, value_a, value_b in values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Get the country with the largest increase
        deltas = []
        for country, value_a, value_b in values:
            action = FrankensteinAction(
                'subtract',
                value_a=value_b,
                value_b=value_a,
            )
            action.execute()
            self.actions.append(action.to_dict())
            delta = action.result
            deltas.append((country, delta))

        # Check if deltas is empty
        if all(delta is None for _, delta in deltas):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Sort the countries by the largest increase

        # action = FrankensteinAction('sort', values=[d[1] for d in deltas])
        # action.execute()
        # self.actions.append(action.to_dict())
        # sorted_countries = action.result

        # Get the country with the 'operator' increase
        if self.operator == 'highest':
            action = FrankensteinAction(
                'maximum',
                values=[d[1] for d in deltas],
            )
        elif self.operator == 'lowest':
            action = FrankensteinAction(
                'minimum',
                values=[d[1] for d in deltas],
            )
        action.execute()
        self.actions.append(action.to_dict())

        # Set the answer to the country with the 'operator' increase
        self.answer = [country for country, delta in deltas if delta == action.result]

        # Call the final_answer tool to format the answer
        action = FrankensteinAction(
            'final_answer',
            answer=self.answer,
        )
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionComparison question.')
    parser.add_argument('--region', type=str, choices=Region.get_values(), help='The region to compare.')
    parser.add_argument('--operator', type=str, choices=NaryOperator.get_values(), help='The operator to use for comparison.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--time_a', type=str, choices=Time.get_values(), help='The first time to compare.')
    parser.add_argument('--time_b', type=str, choices=Time.get_values(), help='The second time to compare.')

    args = parser.parse_args()

    q = IncreasePropertyComparison()
    if all(
        [
            args.region,
            args.operator,
            args.property,
            args.time_a,
            args.time_b,
        ]
    ):
        comb = {
            'region': args.region,
            'operator': args.operator,
            'property': args.property,
            'time_a': args.time_a,
            'time_b': args.time_b,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
