"""Template for rank change questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Region, Subject, Year


class RankChange(FrankensteinQuestion):
    """Class representing a rank change question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a rank change question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'Among the countries in {region}, what was the change in rank of {subject} for {property} between {year_a} and {year_b}?',
            'What was the change in rank of {subject} for {property} in {region} between {year_a} and {year_b}?',
            'Between {year_a} and {year_b}, how did the rank of {subject} for {property} change among countries in {region}?',
        )

        allowed_values = {
            'region': Region,
            'subject': Subject,
            'property': Property,
            'year_a': Year,
            'year_b': Year,
        }

        super().__init__(slot_values, allowed_values)
        self.metadata['answer_format'] = 'int'

    def validate_combination(self, combination: dict) -> bool:
        """Ensure subject is in the region and years are different."""
        if combination['year_a'] == combination['year_b']:
            return False
        countries_in_region = FrankensteinAction('get_country_codes_in_region', region=combination['region'])
        countries_in_region.execute()
        return combination['subject'] in countries_in_region.result

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

        # Get the countries in the region
        action = FrankensteinAction(
            'get_country_codes_in_region',
            region=self.region,
        )
        action.execute()
        self.actions.append(action.to_dict())
        region_countries = action.result

        # Retrieve the property values for the region in year_a
        values_a = []
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
            values_a.append((country, value))

        # Retrieve the property values for the region in year_b
        values_b = []
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
            values_b.append((country, value))

        # Check for missing data
        if any(v is None for _, v in values_a) or any(v is None for _, v in values_b):
            self.metadata['data_availability'] = 'partial'
        if all(v is None for _, v in values_a) or all(v is None for _, v in values_b):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Only use countries with non-None values for ranking in each year
        valid_a = [(c, v) for c, v in values_a if v is not None]
        valid_b = [(c, v) for c, v in values_b if v is not None]

        # Get subject value for each year
        subject_value_a = next((v for c, v in valid_a if c == subject_code), None)
        subject_value_b = next((v for c, v in valid_b if c == subject_code), None)
        if subject_value_a is None or subject_value_b is None:
            self.metadata['data_availability'] = 'partial'
            self.metadata['answerable'] = False
            return

        # Get value lists for ranking
        values_list_a = [v for _, v in valid_a]
        values_list_b = [v for _, v in valid_b]

        # Compute rank in year_a
        action = FrankensteinAction('rank', values=values_list_a, query_value=subject_value_a)
        action.execute()
        self.actions.append(action.to_dict())
        rank_a = action.result

        # Compute rank in year_b
        action = FrankensteinAction('rank', values=values_list_b, query_value=subject_value_b)
        action.execute()
        self.actions.append(action.to_dict())
        rank_b = action.result

        if rank_a is None or rank_b is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Compute the change in rank (year_b - year_a)
        action = FrankensteinAction('subtract', value_a=rank_b, value_b=rank_a)
        action.execute()
        self.actions.append(action.to_dict())
        rank_change = action.result

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=rank_change)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RankChange question.')
    parser.add_argument('--region', type=str, choices=Region.get_values(), help='The region to check.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to check.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to check.')
    parser.add_argument('--year_a', type=str, choices=Year.get_values(), help='The first year.')
    parser.add_argument('--year_b', type=str, choices=Year.get_values(), help='The second year.')

    args = parser.parse_args()

    q = RankChange()
    if all([args.region, args.subject, args.property, args.year_a, args.year_b]):
        comb = {
            'region': args.region,
            'subject': args.subject,
            'property': args.property,
            'year_a': args.year_a,
            'year_b': args.year_b,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
