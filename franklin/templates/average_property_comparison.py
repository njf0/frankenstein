"""Template for average property comparison questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import BinaryOperator, Property, Subject, SubjectSet, Time


class AveragePropertyComparison(FranklinQuestion):
    """Class representing an average property comparison question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize an average property comparison question."""
        self.templates = (
            'Was the {property} of {subject} {operator} than the average value for {subject_set} in {time}?',
            'In {time}, was the {property} of {subject} {operator} than the average value for {subject_set}?',
            "Was {subject}'s {property} {operator} than the average value for {subject_set} in {time}?",
            "In {time}, was {subject}'s {property} {operator} than the average value for {subject_set}?",
        )

        allowed_values = {
            'property': Property,
            'subject': Subject,
            'operator': BinaryOperator,
            'subject_set': SubjectSet,
            'time': Time,
        }
        super().__init__(slot_values, allowed_values)

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the country code for the subject
        action = FranklinAction(
            'get_country_code_from_name',
            country_name=self.c2n[self.subject],
        )
        action.execute()
        self.actions.append(action.to_dict())
        subject_code = action.result

        # Get the indicator code for the property
        action = FranklinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Retrieve the property value for the subject
        action = FranklinAction(
            'retrieve_value',
            country_code=subject_code,
            indicator_code=indicator_code,
            year=self.time,
        )
        action.execute()
        self.actions.append(action.to_dict())
        subject_value = action.result

        # Check for missing data
        if subject_value is None:
            self.metadata['data_availability'] = 'missing'
            return

        # Get the countries in the subject_set
        action = FranklinAction(
            'get_country_codes_in_region',
            region_name=self.subject_set,
        )
        action.execute()
        self.actions.append(action.to_dict())
        region_countries = action.result

        # Retrieve the property values for the region
        region_values = []
        for country in region_countries:
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
                region_values.append(value)

        # Check for missing data
        if any(value is None for value in region_values):
            self.metadata['data_availability'] = 'partial'

        if all(v is None for v in region_values):
            self.metadata['data_availability'] = 'missing'

            return

        # Compute the average property value for the region
        action = FranklinAction('mean', values=region_values)
        action.execute()
        self.actions.append(action.to_dict())
        region_mean = action.result

        # Compare subject value to region mean
        if self.operator == 'higher':
            action = FranklinAction('greater_than', value_a=subject_value, value_b=region_mean)
        elif self.operator == 'lower':
            action = FranklinAction('less_than', value_a=subject_value, value_b=region_mean)

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
    parser = argparse.ArgumentParser(description='Generate an AveragePropertyComparison question.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to compare.')
    parser.add_argument('--operator', type=str, choices=BinaryOperator.get_values(), help='The operator to use for comparison.')
    parser.add_argument('--subject_set', type=str, choices=SubjectSet.get_values(), help='The region to compare against.')
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time to compare.')

    args = parser.parse_args()

    q = AveragePropertyComparison()
    if all([args.property, args.subject, args.operator, args.subject_set, args.time]):
        comb = {
            'property': args.property,
            'subject': args.subject,
            'operator': args.operator,
            'subject_set': args.subject_set,
            'time': args.time,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
