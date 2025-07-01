"""Template for region proportion comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import BinaryOperator, Property, Region, Subject, Year


class RegionProportionChange(FrankensteinQuestion):
    """Class representing a region proportion comparison question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a region proportion comparison question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            "Was {subject}'s share of the total {property} in {region} {operator} in {year_a} than it was in {year_b}?",
            "In {year_a}, was {subject}'s share of the total {property} in {region} {operator} than it was in {year_b}?",
            "Compared to {region} as a whole, was {subject}'s share of the total {property} {operator} in {year_a} than it was in {year_b}?",
        )

        allowed_values = {
            'property': Property,
            'subject': Subject,
            'region': Region,
            'operator': BinaryOperator,
            'year_a': Year,
            'year_b': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'bool'

    def validate_combination(self, combination: dict) -> bool:
        """Ensure subject is in the region and years are different."""
        countries_in_region = FrankensteinAction('get_country_codes_in_region', region=combination['region'])
        countries_in_region.execute()
        return combination['subject'] in countries_in_region.result and combination['year_a'] != combination['year_b']

    def compute_actions(self):
        """Compute actions for the question."""
        # Search for the indicator code for the property (for traceability)
        action = FrankensteinAction(
            'search_for_indicator_codes',
            keywords=self.i2n[self.property],
        )
        action.execute()
        action.result = [d for d in action.result if d['indicator_name'] == self.i2n[self.property]]
        self.actions.append(action.to_dict())
        indicator_code = self.slot_values['property']

        # Get the countries in the region
        action = FrankensteinAction(
            'get_country_codes_in_region',
            region=self.region,
        )
        action.execute()
        self.actions.append(action.to_dict())
        region_countries = action.result

        # Retrieve the property value for the subject at year_a
        action = FrankensteinAction(
            'retrieve_value',
            country_code=self.slot_values['subject'],
            indicator_code=indicator_code,
            year=self.year_a,
        )
        action.execute()
        self.actions.append(action.to_dict())
        subject_value_a = action.result

        # Check for missing data
        if subject_value_a is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Retrieve the property value for the subject at year_b
        action = FrankensteinAction(
            'retrieve_value',
            country_code=self.slot_values['subject'],
            indicator_code=indicator_code,
            year=self.year_b,
        )
        action.execute()
        self.actions.append(action.to_dict())
        subject_value_b = action.result

        # Check for missing data
        if subject_value_b is None:
            self.metadata['data_availability'] = 'missing'
            return

        # Retrieve the property values for the region at year_a
        region_values_a = []
        for country in region_countries:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.year_a,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            region_values_a.append(value)

        if any(v is None for v in region_values_a):
            self.metadata['data_availability'] = 'partial'

        if all(v is None for v in region_values_a):
            self.metadata['data_availability'] = 'missing'
            return

        # Retrieve the property values for the region at year_b
        region_values_b = []
        for country in region_countries:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.year_b,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            region_values_b.append(value)

        # Check for missing data
        if any(v is None for v in region_values_b):
            self.metadata['data_availability'] = 'partial'
        if all(v is None for v in region_values_b):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Compute the total property value for the region at year_a
        action = FrankensteinAction('add', values=[i for i in region_values_a if i is not None])
        action.execute()
        self.actions.append(action.to_dict())
        region_total_a = action.result

        # Compute the total property value for the region at year_b
        action = FrankensteinAction('add', values=[i for i in region_values_b if i is not None])
        action.execute()
        self.actions.append(action.to_dict())
        region_total_b = action.result

        # Compute the proportion for subject at year_a
        action = FrankensteinAction('divide', value_a=subject_value_a, value_b=region_total_a)
        action.execute()
        self.actions.append(action.to_dict())
        proportion_a = action.result

        # Compute the proportion for subject at year_b
        action = FrankensteinAction('divide', value_a=subject_value_b, value_b=region_total_b)
        action.execute()
        self.actions.append(action.to_dict())
        proportion_b = action.result

        # Compare the proportions using the operator
        if self.operator == 'higher':
            action = FrankensteinAction('greater_than', value_a=proportion_a, value_b=proportion_b)
        elif self.operator == 'lower':
            action = FrankensteinAction('greater_than', value_a=proportion_b, value_b=proportion_a)

        action.execute()
        self.actions.append(action.to_dict())
        comparison_result = action.result

        # Set the final answer
        self.answer = comparison_result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionProportionChange question.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to compare.')
    parser.add_argument('--region', type=str, choices=Region.get_values(), help='The region to compare against.')
    parser.add_argument('--operator', type=str, choices=['higher', 'lower'], help='The operator to use for comparison.')
    parser.add_argument('--year_a', type=str, choices=Year.get_values(), help='The first year.')
    parser.add_argument('--year_b', type=str, choices=Year.get_values(), help='The second year.')

    args = parser.parse_args()

    q = RegionProportionChange()
    if all([args.property, args.subject, args.region, args.operator, args.year_a, args.year_b]):
        comb = {
            'property': args.property,
            'subject': args.subject,
            'region': args.region,
            'operator': args.operator,
            'year_a': args.year_a,
            'year_b': args.year_b,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
