"""Template for subject_set comparison questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import NaryOperator, Property, SubjectSet, Time


class IncreasePropertyComparison(FranklinQuestion):
    """Class representing an IncreasePropertyComparison question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize an IncreasePropertyComparison question."""
        self.template = (
            'Which country in {subject_set} had the {operator} increase in {property} between {time_a} and {time_b}?'
        )
        allowed_values = {
            'subject_set': SubjectSet,
            'operator': NaryOperator,
            'property': Property,
            'time_a': Time,
            'time_b': Time,
        }
        super().__init__(slot_values, allowed_values)

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
        """Compute answer in terms of FranklinAction."""
        # Get countries in the subject_set
        action = FranklinAction(
            'get_countries_in_region',
            region_name=self.subject_set,
        )
        action.execute()
        self.actions.append(action.to_dict())
        countries_in_region = action.result

        # Get the indicator code for the property
        action = FranklinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Get the values for each country in the subject_set for both time_a and time_b
        values = []
        for country in countries_in_region:
            action = FranklinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.time_a,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value_a = action.result

            action = FranklinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.time_b,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value_b = action.result

            if value_a is None or value_b is None:
                self.metadata['data_availability'] = 'partial'
                self.metadata['answerable'] = False
                self.answer = None
                return

            values.append((country, value_a, value_b))

        # Check if all values are None
        if all(value_a is None and value_b is None for _, value_a, value_b in values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            self.answer = None
            return

        # Get the country with the largest increase
        deltas = []
        for country, value_a, value_b in values:
            if value_a is None or value_b is None:
                self.metadata['data_availability'] = 'partial'
                self.metadata['answerable'] = False
                self.answer = None
                return

            action = FranklinAction('subtract', a=value_b, b=value_a)
            action.execute()
            self.actions.append(action.to_dict())
            delta = action.result
            deltas.append((country, delta))

        # Check if deltas is empty
        if all(delta is None for delta in deltas):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            self.answer = None
            return

        # Sort the countries by the largest increase
        action = FranklinAction('sort', data=[d[1] for d in deltas])
        action.execute()
        self.actions.append(action.to_dict())
        sorted_countries = action.result

        # Get the country with the 'operator' increase
        if self.operator == 'highest':
            action = FranklinAction('maximum', data=sorted_countries)
        elif self.operator == 'lowest':
            action = FranklinAction('minimum', data=sorted_countries)

        action.execute()
        self.actions.append(action.to_dict())

        # Set the answer to the country with the 'operator' increase
        self.answer = [country for country, delta in deltas if delta == action.result]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionComparison question.')
    parser.add_argument('--subject_set', type=str, choices=SubjectSet.get_values(), help='The subject_set to compare.')
    parser.add_argument('--operator', type=str, choices=NaryOperator.get_values(), help='The operator to use for comparison.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--time_a', type=str, choices=Time.get_values(), help='The first time to compare.')
    parser.add_argument('--time_b', type=str, choices=Time.get_values(), help='The second time to compare.')

    args = parser.parse_args()

    q = IncreasePropertyComparison()
    if all(
        [
            args.subject_set,
            args.operator,
            args.property,
            args.time_a,
            args.time_b,
        ]
    ):
        comb = {
            'subject_set': args.subject_set,
            'operator': args.operator,
            'property': args.property,
            'time_a': args.time_a,
            'time_b': args.time_b,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
