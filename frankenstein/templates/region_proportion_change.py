"""Template for region proportion comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import BinaryOperator, Property, Subject, SubjectSet, Time


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
            "Was {subject}'s share of the total {property} in {subject_set} {operator} in {time_a} than it was in {time_b}?",
            "In {time_a}, was {subject}'s share of the total {property} in {subject_set} {operator} than it was in {time_b}?",
            "Compared to {subject_set} as a whole, was {subject}'s share of the total {property} in {time_a} {operator} than it was in {time_b}?",
        )

        allowed_values = {
            'property': Property,
            'subject': Subject,
            'subject_set': SubjectSet,
            'operator': BinaryOperator,
            'time_a': Time,
            'time_b': Time,
        }
        super().__init__(slot_values, allowed_values)

    def validate_combination(self, combination: dict) -> bool:
        """Ensure subject is in the subject_set and times are different."""
        countries_in_region = FrankensteinAction('get_country_codes_in_region', region_name=combination['subject_set'])
        countries_in_region.execute()
        return combination['subject'] in countries_in_region.result and combination['time_a'] != combination['time_b']

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the country code for the subject
        action = FrankensteinAction(
            'get_country_code_from_name',
            country_name=self.c2n[self.subject],
        )
        action.execute()
        self.actions.append(action.to_dict())
        subject_code = action.result

        # Get the indicator code for the property
        action = FrankensteinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Get the countries in the subject_set
        action = FrankensteinAction(
            'get_country_codes_in_region',
            region_name=self.subject_set,
        )
        action.execute()
        self.actions.append(action.to_dict())
        region_countries = action.result

        # Retrieve the property value for the subject at time_a
        action = FrankensteinAction(
            'retrieve_value',
            country_code=subject_code,
            indicator_code=indicator_code,
            year=self.time_a,
        )
        action.execute()
        self.actions.append(action.to_dict())
        subject_value_a = action.result

        # Check for missing data
        if subject_value_a is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Retrieve the property value for the subject at time_b
        action = FrankensteinAction(
            'retrieve_value',
            country_code=subject_code,
            indicator_code=indicator_code,
            year=self.time_b,
        )
        action.execute()
        self.actions.append(action.to_dict())
        subject_value_b = action.result

        # Check for missing data
        if subject_value_b is None:
            self.metadata['data_availability'] = 'missing'
            return

        # Retrieve the property values for the region at time_a
        region_values_a = []
        for country in region_countries:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.time_a,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            if value is not None:
                region_values_a.append(value)

        if any(v is None for v in region_values_a):
            self.metadata['data_availability'] = 'partial'

        if all(v is None for v in region_values_a):
            self.metadata['data_availability'] = 'missing'
            return

        # Retrieve the property values for the region at time_b
        region_values_b = []
        for country in region_countries:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.time_b,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            if value is not None:
                region_values_b.append(value)

        # Check for missing data
        if any(v is None for v in region_values_b):
            self.metadata['data_availability'] = 'partial'
        if all(v is None for v in region_values_b):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Compute the total property value for the region at time_a
        action = FrankensteinAction('add', values=region_values_a)
        action.execute()
        self.actions.append(action.to_dict())
        region_total_a = action.result

        # Compute the total property value for the region at time_b
        action = FrankensteinAction('add', values=region_values_b)
        action.execute()
        self.actions.append(action.to_dict())
        region_total_b = action.result

        # Compute the proportion for subject at time_a
        action = FrankensteinAction('divide', value_a=subject_value_a, value_b=region_total_a)
        action.execute()
        self.actions.append(action.to_dict())
        proportion_a = action.result

        # Compute the proportion for subject at time_b
        action = FrankensteinAction('divide', value_a=subject_value_b, value_b=region_total_b)
        action.execute()
        self.actions.append(action.to_dict())
        proportion_b = action.result

        # Compare the proportions using the operator
        if self.operator == 'higher':
            action = FrankensteinAction('greater_than', value_a=proportion_a, value_b=proportion_b)
        elif self.operator == 'lower':
            action = FrankensteinAction('less_than', value_a=proportion_a, value_b=proportion_b)

        action.execute()
        self.actions.append(action.to_dict())
        comparison_result = action.result

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=comparison_result)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionProportionChange question.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to compare.')
    parser.add_argument('--subject_set', type=str, choices=SubjectSet.get_values(), help='The region to compare against.')
    parser.add_argument('--operator', type=str, choices=['higher', 'lower'], help='The operator to use for comparison.')
    parser.add_argument('--time_a', type=str, choices=Time.get_values(), help='The first time.')
    parser.add_argument('--time_b', type=str, choices=Time.get_values(), help='The second time.')

    args = parser.parse_args()

    q = RegionProportionChange()
    if all([args.property, args.subject, args.subject_set, args.operator, args.time_a, args.time_b]):
        comb = {
            'property': args.property,
            'subject': args.subject,
            'subject_set': args.subject_set,
            'operator': args.operator,
            'time_a': args.time_a,
            'time_b': args.time_b,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
