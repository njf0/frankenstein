"""Template for subject_set comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import BinaryOperator, Property, Subject, SubjectSet, Time


class CountryThresholdCount(FrankensteinQuestion):
    """Class representing a CountryThresholdCount question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a CountryThresholdCount question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'How many countries in the region of {subject_set} had a {operator} {property} than {subject} in {time}?',
            'In {time}, how many countries in the region of {subject_set} had a {operator} {property} than {subject}?',
            'In {subject_set}, how many countries had a {operator} {property} than {subject} in {time}?',
        )

        allowed_values = {
            'subject_set': SubjectSet,
            'operator': BinaryOperator,
            'property': Property,
            'subject': Subject,
            'time': Time,
        }

        super().__init__(slot_values, allowed_values)

    def validate_combination(self, combination: dict) -> bool:
        """Apply constraints to the combination of slot values.

        For this question type, we need to ensure that the subject is not in the subject_set.

        Parameters
        ----------
        combination: dict
            A combination of slot values.

        Returns
        -------
        bool
            True if the combination is valid, False otherwise.

        """
        countries_in_region = FrankensteinAction('get_country_codes_in_region', region_name=combination['subject_set'])
        countries_in_region.execute()

        return combination['subject'] not in countries_in_region.result

    def compute_actions(
        self,
    ):
        """Compute result for the question using FrankensteinActions."""
        # Get countries in the subject_set
        action = FrankensteinAction('get_country_codes_in_region', region_name=self.subject_set)
        action.execute()
        self.actions.append(action.to_dict())
        country_codes = action.result

        # Get the country code for the threshold subject
        if self.c2n[self.subject] not in country_codes:
            action = FrankensteinAction(
                'get_country_code_from_name',
                country_name=self.c2n[self.subject],
            )
            action.execute()
            self.actions.append(action.to_dict())
            threshold_subject_country_code = action.result
        else:
            threshold_subject_country_code = None

        # Get the indicator code from the property name
        action = FrankensteinAction(
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Retrieve the values for the subjects in the subject_set
        values = []
        for country_code in country_codes:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=country_code,
                indicator_code=indicator_code,
                year=self.time,
            )
            action.execute()
            self.actions.append(action.to_dict())
            values.append(action.result)

        # Check if any values are None
        if any(value is None for value in values):
            self.metadata['data_availability'] = 'partial'

        if all(value is None for value in values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Retrieve the value for the threshold subject
        if threshold_subject_country_code is not None:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=threshold_subject_country_code,
                indicator_code=indicator_code,
                year=self.time,
            )
            action.execute()
            self.actions.append(action.to_dict())
            threshold_value = action.result

        elif threshold_subject_country_code is None:
            # Country code is already in the list
            action = FrankensteinAction(
                'retrieve_value',
                country_code=self.c2n[self.subject],
                indicator_code=indicator_code,
                year=self.time,
            )
            action.execute()
            self.actions.append(action.to_dict())
            threshold_value = action.result

        if threshold_value is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False

            return

        # Now compare if values meet the threshold
        comparisons = []
        for value in values:
            if self.operator == 'higher':
                action = FrankensteinAction(
                    'greater_than',
                    value_a=value,
                    value_b=threshold_value,
                )
                action.execute()
                self.actions.append(action.to_dict())
                comparisons.append(action.result)
            elif self.operator == 'lower':
                action = FrankensteinAction(
                    'less_than',
                    value_a=value,
                    value_b=threshold_value,
                )
                action.execute()
                self.actions.append(action.to_dict())
                comparisons.append(action.result)

        # Filter out None results and set data availability accordingly
        valid_comparisons = [c for c in comparisons if c is not None]

        if not valid_comparisons:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False

        # Get the number of countries that satisfy the condition
        self.answer = sum(valid_comparisons)

        # Final answer
        action = FrankensteinAction('final_answer', answer=self.answer)
        action.execute()
        self.actions.append(action.to_dict())

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a CountryThresholdCount question.')
    parser.add_argument('--subject_set', type=str, choices=SubjectSet.get_values(), help='The subject_set to compare.')
    parser.add_argument('--operator', type=str, choices=BinaryOperator.get_values(), help='The operator to use for comparison.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to compare.')
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time to compare.')

    args = parser.parse_args()

    q = CountryThresholdCount()
    if all(
        [
            args.subject_set,
            args.operator,
            args.property,
            args.subject,
            args.time,
        ]
    ):
        comb = {
            'subject_set': args.subject_set,
            'operator': args.operator,
            'property': args.property,
            'subject': args.subject,
            'time': args.time,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
