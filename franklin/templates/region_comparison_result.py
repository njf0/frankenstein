"""Template for subject_set comparison questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import NaryOperator, Property, SubjectSet, Time


class RegionComparisonResult(FranklinQuestion):
    """Template for subject_set comparison subgoal questions."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize the template.

        Parameters
        ----------
        slot_values: dict
            Slot values for the question.
        data_manager: DataManager
            Instance of DataManager with preloaded datasets.

        """
        self.template = 'For the country in {subject_set} that had the {operator} {property_2} in {time_2}, and what was its value in {time_1}?'
        allowed_values = {
            'time_1': Time,
            'property_1': Property,
            'subject_set': SubjectSet,
            'operator': NaryOperator,
            'property_2': Property,
            'time_2': Time,
        }

        self.answer_format = 'tuple(str, float)'

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
        # Get the countries in the subject_set
        action = FranklinAction('get_country_codes_in_region', region_name=self.subject_set)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # # Get the indicator code for property_1
        # action = FranklinAction('get_indicator_code_from_name', indicator_name=self.i2n[self.property_1])
        # action.execute()
        # self.actions.append(action.to_dict())
        # indicator_code_1 = action.result

        # Get the indicator code for property_2
        action = FranklinAction('get_indicator_code_from_name', indicator_name=self.i2n[self.property_2])
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code_2 = action.result

        # Retrieve the property_2 values for the countries
        property_2_values = []
        for country in countries:
            action = FranklinAction('get_country_code_from_name', country_name=self.c2n[country])
            action.execute()
            self.actions.append(action.to_dict())
            country_code = action.result

            action = FranklinAction(
                'retrieve_value', country_code=country_code, indicator_code=indicator_code_2, year=self.time_2
            )
            action.execute()
            self.actions.append(action.to_dict())
            value = action.result

            property_2_values.append((country_code, value))

        # Check if all values are missing
        if all(v[1] is None for v in property_2_values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            self.answer = None
            return

        # Check if any values are missing
        if any(v[1] is None for v in property_2_values):
            self.metadata['data_availability'] = 'partial'
            self.metadata['answerable'] = False
            self.answer = None
            return

        # Use maximum or minimum tool to find the target value
        values = [v[1] for v in property_2_values if v[1] is not None]
        if self.operator == 'highest':
            action = FranklinAction('maximum', values=values)
        elif self.operator == 'lowest':
            action = FranklinAction('minimum', values=values)
        action.execute()
        self.actions.append(action.to_dict())
        target_value = action.result

        target_country = next((c for c, v in property_2_values if v == target_value), None)

        # Retrieve the property_1 value for the target country
        action = FranklinAction(
            'retrieve_value', country_code=target_country, indicator_code=indicator_code_2, year=self.time_1
        )
        action.execute()
        self.actions.append(action.to_dict())
        property_1_value = action.result

        # Check if the required value is missing
        if property_1_value is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            self.answer = None
            return

        # Set the final answer
        action = FranklinAction('final_answer', answer=(property_1_value))
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        self.metadata['answerable'] = True
        self.metadata['data_availability'] = 'full'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionComparison question.')
    parser.add_argument('--time_1', type=str, choices=Time.get_values())
    parser.add_argument('--subject_set', type=str, choices=SubjectSet.get_values())
    parser.add_argument('--operator', type=str, choices=NaryOperator.get_values())
    parser.add_argument('--property_2', type=str, choices=Property.get_values())
    parser.add_argument('--time_2', type=str, choices=Time.get_values())

    args = parser.parse_args()

    q = RegionComparisonResult()

    if all(
        [
            args.time_1,
            # args.property_1,
            args.subject_set,
            args.operator,
            args.property_2,
            args.time_2,
        ]
    ):
        comb = {
            'time_1': args.time_1,
            # 'property_1': args.property_1,
            'subject_set': args.subject_set,
            'operator': args.operator,
            'property_2': args.property_2,
            'time_2': args.time_2,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
