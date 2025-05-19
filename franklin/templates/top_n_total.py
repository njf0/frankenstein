"""Template for subject_set comparison questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import NaryOperator, Number, Property, SubjectSet, Time


class TopNTotal(FranklinQuestion):
    """Class representing a TopNTotal question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a TopNTotal question."""
        self.template = 'Which {n} countries in {subject_set} had the {operator} {property} in {time}?'
        allowed_values = {'property': Property, 'n': Number, 'subject_set': SubjectSet, 'operator': NaryOperator, 'time': Time}

        super().__init__(slot_values, allowed_values)

    def compute_actions(self):
        """Compute actions for the question."""
        # Get the countries in the subject_set
        action = FranklinAction('get_country_codes_in_region', region_name=self.subject_set)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # Get the indicator code for the property
        action = FranklinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Retrieve the property values for the countries
        property_values = []
        for country in countries:
            action = FranklinAction(
                'get_country_code_from_name',
                country_name=self.c2n[country],
            )
            action.execute()
            self.actions.append(action.to_dict())
            country_code = action.result

            action = FranklinAction(
                'retrieve_value',
                country_code=country_code,
                indicator_code=indicator_code,
                year=self.time,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result

            if value is not None:
                property_values.append((country_code, value))
            else:
                self.metadata['data_availability'] = 'partial'

        # Check if all values are missing
        if all(v[1] is None for v in property_values):
            self.metadata['data_availability'] = 'missing'

            return

        # Check if any values are missing
        if any(v[1] is None for v in property_values):
            self.metadata['data_availability'] = 'partial'

            return

        # Use maximum or minimum tool to find the top `n` values
        values = [float(v[1]) for v in property_values]
        action = FranklinAction('sort', values=values)
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
        action = FranklinAction('final_answer', answer=[self.c2n[c] for c in top_countries])
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

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
        '--subject_set',
        type=str,
        choices=SubjectSet.get_values(),
        help='The subject_set to compare.',
    )
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time to compare.')

    args = parser.parse_args()

    q = TopNTotal()
    if all(
        [
            args.property,
            args.n,
            args.operator,
            args.subject_set,
            args.time,
        ]
    ):
        comb = {
            'property': args.property,
            'n': args.n,
            'operator': args.operator,
            'subject_set': args.subject_set,
            'time': args.time,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
