"""Template for subject property rank questions."""

import argparse

from franklin.action import FranklinAction
from franklin.franklin_question import FranklinQuestion
from franklin.slot_values import Property, Subject, SubjectSet, Time


class SubjectPropertyRank(FranklinQuestion):
    """Class representing a subject property rank question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a subject property rank question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'What rank did {subject} have for {property} among countries in {subject_set} in {time}?',
            'In {time}, what was the rank of {subject} for {property} among countries in {subject_set}?',
            'Among countries in {subject_set}, what was the rank of {subject} for {property} in {time}?',
        )

        allowed_values = {
            'subject': Subject,
            'property': Property,
            'subject_set': SubjectSet,
            'time': Time,
        }

        super().__init__(slot_values, allowed_values)

    def validate_combination(self, combination: dict) -> bool:
        """Ensure subject is in the subject_set."""
        countries_in_region = FranklinAction('get_country_codes_in_region', region_name=combination['subject_set'])
        countries_in_region.execute()
        return combination['subject'] in countries_in_region.result

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
            region_values.append((country, value))

        # Check for missing data
        if any(v is None for _, v in region_values):
            self.metadata['data_availability'] = 'partial'

        if all(v is None for _, v in region_values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Only use countries with non-None values for ranking
        valid_values = [(c, v) for c, v in region_values if v is not None]
        if not valid_values:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        values_list = [v for _, v in valid_values]
        # Use FranklinAction to compute rank of the subject's value
        subject_value = next((v for c, v in valid_values if c == subject_code), None)
        if subject_value is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        action = FranklinAction('rank', values=values_list, query_value=subject_value)
        action.execute()
        self.actions.append(action.to_dict())
        subject_rank = action.result

        if subject_rank is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Set the final answer
        action = FranklinAction('final_answer', answer=subject_rank)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a SubjectPropertyRank question.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to rank.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to rank by.')
    parser.add_argument('--subject_set', type=str, choices=SubjectSet.get_values(), help='The region to rank within.')
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time to rank for.')

    args = parser.parse_args()

    q = SubjectPropertyRank()
    if all([args.subject, args.property, args.subject_set, args.time]):
        comb = {
            'subject': args.subject,
            'property': args.property,
            'subject_set': args.subject_set,
            'time': args.time,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
