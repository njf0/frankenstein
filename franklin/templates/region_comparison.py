"""Template for subject_set comparison questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import NaryOperator, Property, SubjectSet, Time


class RegionComparison(FranklinQuestion):
    """Class representing a subject_set comparison question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a subject_set comparison question."""
        self.template = 'Which country in the region of {subject_set} had the {operator} {property} in {time}?'
        allowed_values = {'subject_set': SubjectSet, 'operator': NaryOperator, 'property': Property, 'time': Time}

        super().__init__(slot_values, allowed_values)

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the countries in the subject_set
        action = FranklinAction('get_country_codes_in_region', region_name=self.subject_set)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # Get the indicator code for the property
        action = FranklinAction('get_indicator_code_from_name', indicator_name=self.i2n[self.property])
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Retrieve the property values for the countries
        property_values = []
        for country in countries:
            action = FranklinAction('get_country_code_from_name', country_name=self.c2n[country])
            action.execute()
            self.actions.append(action.to_dict())
            country_code = action.result

            action = FranklinAction('retrieve_value', country_code=country_code, indicator_code=indicator_code, year=self.time)
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result

            property_values.append((country_code, value))

        # Check if all values are missing
        if all(v[1] is None for v in property_values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            self.answer = None
            return

        # Use maximum or minimum tool to find the target value
        values = [v[1] for v in property_values if v[1] is not None]
        if self.operator == 'highest':
            action = FranklinAction('maximum', values=values)
        elif self.operator == 'lowest':
            action = FranklinAction('minimum', values=values)
        action.execute()
        self.actions.append(action.to_dict())
        target_value = action.result

        target_country = next((c for c, v in property_values if v == target_value), None)

        # Check if the required value is missing
        if target_country is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            self.answer = None
            return

        # Set the final answer
        action = FranklinAction('final_answer', answer=self.c2n[target_country])
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        self.metadata['answerable'] = True
        self.metadata['data_availability'] = 'full'

    def validate_combination(self, combination: dict) -> bool:
        """Validate the combination of slot values.

        For this question type, no specific constraints are required.

        Parameters
        ----------
        combination: dict
            A combination of slot values.

        Returns
        -------
        bool
            True if the combination is valid, False otherwise.

        """
        return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionComparison question.')
    parser.add_argument('--subject_set', type=str, choices=SubjectSet.get_values(), help='The subject_set to compare.')
    parser.add_argument('--operator', type=str, choices=NaryOperator.get_values(), help='The operator to use for comparison.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time to compare.')

    args = parser.parse_args()

    q = RegionComparison()
    if all(
        [
            args.subject_set,
            args.operator,
            args.property,
            args.time,
        ]
    ):
        comb = {
            'subject_set': args.subject_set,
            'operator': args.operator,
            'property': args.property,
            'time': args.time,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
