"""Template for region comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import NaryOperator, Property, Region, Time


class RegionComparisonResult(FrankensteinQuestion):
    """Template for region comparison subgoal questions."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize the template.

        Parameters
        ----------
        slot_values: dict
            Slot values for the question.

        """
        self.templates = (
            'For the country in {region} that had the {operator} {property} in {time_2}, and what was its value in {time_1}?',
            'In {time_1}, what was the {property} for the country in {region} that had the {operator} value for that indicator in {time_2}?',
        )

        allowed_values = {
            'time_1': Time,
            'property': Property,
            'region': Region,
            'operator': NaryOperator,
            'time_2': Time,
        }

        super().__init__(slot_values, allowed_values)

    def validate_combination(self, combination: dict) -> bool:
        """Apply constraints to the combination of slot values.

        For this template, the constraints are that property_1 and property_2 must be different, and time_1 and time_2 must be different.

        Parameters
        ----------
        combination: dict
            A dictionary of slot values.

        Returns
        -------
        bool
            True if the combination is valid, False otherwise.

        """
        return combination['time_1'] != combination['time_2']

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the countries in the region
        action = FrankensteinAction('get_country_codes_in_region', region=self.region)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # Get the indicator code for property
        action = FrankensteinAction('get_indicator_code_from_name', indicator_name=self.i2n[self.property])
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Retrieve the property values for the countries in time_2
        property_values = []
        for country in countries:
            action = FrankensteinAction('get_country_code_from_name', country_name=self.c2n[country])
            action.execute()
            self.actions.append(action.to_dict())
            country_code = action.result

            action = FrankensteinAction(
                'retrieve_value', country_code=country_code, indicator_code=indicator_code, year=self.time_2
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            property_values.append((country_code, value))

        # Check if any values are missing
        if any(v[1] is None for v in property_values):
            self.metadata['data_availability'] = 'partial'

        # Check if all values are missing
        if all(v[1] is None for v in property_values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

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

        # Retrieve the property value for the target country in time_1
        action = FrankensteinAction(
            'retrieve_value', country_code=target_country, indicator_code=indicator_code, year=self.time_1
        )
        action.execute()
        self.actions.append(action.to_dict())
        property_value_time_1 = action.result

        # Check if the required value is missing
        if property_value_time_1 is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=property_value_time_1)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionComparison question.')
    parser.add_argument('--time_1', type=str, choices=Time.get_values())
    parser.add_argument('--region', type=str, choices=Region.get_values())
    parser.add_argument('--operator', type=str, choices=NaryOperator.get_values())
    parser.add_argument('--property_2', type=str, choices=Property.get_values())
    parser.add_argument('--time_2', type=str, choices=Time.get_values())

    args = parser.parse_args()

    q = RegionComparisonResult()

    if all(
        [
            args.time_1,
            # args.property_1,
            args.region,
            args.operator,
            args.property_2,
            args.time_2,
        ]
    ):
        comb = {
            'time_1': args.time_1,
            # 'property_1': args.property_1,
            'region': args.region,
            'operator': args.operator,
            'property_2': args.property_2,
            'time_2': args.time_2,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
