"""Template for rank position change questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import NaryOperator, Number, Property, SubjectSet, Time


class RankPositionChange(FranklinQuestion):
    """Class representing a rank position change question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a rank position change question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'For the countries in {subject_set}, did the country with the {n} {operator} {property} in {time_a} retain that position in {time_b}?',
            'Did the country ranked {n} {operator} for {property} in {time_a} in {subject_set} keep the same rank in {time_b}?',
            'In {subject_set}, did the country with the {n} {operator} {property} in {time_a} keep that position in {time_b}?',
        )

        allowed_values = {
            'subject_set': SubjectSet,
            'n': Number,
            'operator': NaryOperator,
            'property': Property,
            'time_a': Time,
            'time_b': Time,
        }

        super().__init__(slot_values, allowed_values)

    def validate_combination(self, combination: dict) -> bool:
        """Ensure time_a != time_b and n is valid."""
        return combination['time_a'] != combination['time_b']

    def compute_actions(self):
        """Compute actions for the question."""
        # Get countries in the subject_set
        action = FranklinAction('get_country_codes_in_region', region_name=self.subject_set)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # Get the indicator code for the property
        action = FranklinAction('get_indicator_code_from_name', indicator_name=self.i2n[self.property])
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Retrieve property values for all countries in time_a
        values_a = []
        for country in countries:
            action = FranklinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.time_a,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            if value is not None:
                values_a.append((country, value))

        if not values_a:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Sort values for time_a
        reverse = self.operator == 'highest'
        sorted_a = sorted(values_a, key=lambda x: x[1], reverse=reverse)
        n_idx = int(self.n) - 1
        if n_idx >= len(sorted_a):
            self.metadata['data_availability'] = 'partial'
            self.metadata['answerable'] = False
            return

        target_country = sorted_a[n_idx][0]
        target_value_a = sorted_a[n_idx][1]

        # Retrieve property values for all countries in time_b
        values_b = []
        for country in countries:
            action = FranklinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.time_b,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result
            if value is not None:
                values_b.append((country, value))

        if not values_b:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Sort values for time_b
        sorted_b = sorted(values_b, key=lambda x: x[1], reverse=reverse)
        values_b_list = [v for _, v in sorted_b]

        # Get the value for the target country in time_b
        target_value_b = next((v for c, v in values_b if c == target_country), None)
        if target_value_b is None:
            self.metadata['data_availability'] = 'partial'
            self.metadata['answerable'] = False
            return

        # Find index of target country in sorted_b (i.e., its position in time_b)
        action = FranklinAction('index', values=values_b_list, query_value=target_value_b)
        action.execute()
        self.actions.append(action.to_dict())
        index_b = action.result

        if index_b is None or index_b == -1:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Compare the index in time_b to n_idx
        retained = index_b == n_idx

        # Set the final answer
        action = FranklinAction('final_answer', answer=retained)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RankPositionChange question.')
    parser.add_argument('--subject_set', type=str, choices=SubjectSet.get_values(), help='The region to check.')
    parser.add_argument('--n', type=str, choices=Number.get_values(), help='The rank position to check.')
    parser.add_argument('--operator', type=str, choices=NaryOperator.get_values(), help='The operator (highest/lowest).')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to check.')
    parser.add_argument('--time_a', type=str, choices=Time.get_values(), help='The first time.')
    parser.add_argument('--time_b', type=str, choices=Time.get_values(), help='The second time.')

    args = parser.parse_args()

    q = RankPositionChange()
    if all([args.subject_set, args.n, args.operator, args.property, args.time_a, args.time_b]):
        comb = {
            'subject_set': args.subject_set,
            'n': args.n,
            'operator': args.operator,
            'property': args.property,
            'time_a': args.time_a,
            'time_b': args.time_b,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
