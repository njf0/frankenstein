"""Template for region comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import NaryOperator, Property, Region, Year


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
            'For the country in {region} that had the {operator} {property} in {year_2}, what was its value in {year_1}?',
            'In {year_1}, what was the {property} for the country in {region} that had the {operator} value for that indicator in {year_2}?',
            'What was the {property} in {year_1} for the country in {region} that had the {operator} value for that indicator in {year_2}?',
        )

        allowed_values = {
            'year_1': Year,
            'property': Property,
            'region': Region,
            'operator': NaryOperator,
            'year_2': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'float'

    def validate_combination(self, combination: dict) -> bool:
        """Apply constraints to the combination of slot values.

        For this template, the constraints are that property_1 and property_2 must be different, and year_1 and year_2 must be different.

        Parameters
        ----------
        combination: dict
            A dictionary of slot values.

        Returns
        -------
        bool
            True if the combination is valid, False otherwise.

        """
        return combination['year_1'] != combination['year_2']

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the countries in the region
        action = FrankensteinAction('get_country_codes_in_region', region=self.region)
        action.execute()
        self.actions.append(action.to_dict())
        country_codes = action.result

        # Search for the indicator code for property (for traceability)
        action = FrankensteinAction(
            'search_for_indicator_codes',
            keywords=self.i2n[self.property],
        )
        action.execute()
        action.result = [d for d in action.result if d['indicator_name'] == self.i2n[self.property]]
        self.actions.append(action.to_dict())
        indicator_code = self.slot_values['property']

        # Retrieve the property values for the country_codes in year_2
        property_values = []
        for code in country_codes:
            action = FrankensteinAction('retrieve_value', country_code=code, indicator_code=indicator_code, year=self.year_2)
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            property_values.append((code, value))

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

        # Retrieve the property value for the target country in year_1
        action = FrankensteinAction(
            'retrieve_value', country_code=target_country, indicator_code=indicator_code, year=self.year_1
        )
        action.execute()
        self.actions.append(action.to_dict())
        property_value_year_1 = action.result

        # Check if the required value is missing
        if property_value_year_1 is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Set the final answer
        self.answer = property_value_year_1

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionComparison question.')
    parser.add_argument('--year_1', type=str, choices=Year.get_values())
    parser.add_argument('--region', type=str, choices=Region.get_values())
    parser.add_argument('--operator', type=str, choices=NaryOperator.get_values())
    parser.add_argument('--property_2', type=str, choices=Property.get_values())
    parser.add_argument('--year_2', type=str, choices=Year.get_values())

    args = parser.parse_args()

    q = RegionComparisonResult()

    if all(
        [
            args.year_1,
            # args.property_1,
            args.region,
            args.operator,
            args.property_2,
            args.year_2,
        ]
    ):
        comb = {
            'year_1': args.year_1,
            # 'property_1': args.property_1,
            'region': args.region,
            'operator': args.operator,
            'property_2': args.property_2,
            'year_2': args.year_2,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
