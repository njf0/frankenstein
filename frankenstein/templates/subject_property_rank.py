"""Template for subject property rank questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Region, Subject, Year


class SubjectPropertyRank(FrankensteinQuestion):
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
            'What rank did {subject} have for {property} among countries in {region} in {year}?',
            'In {year}, what was the rank of {subject} for {property} among countries in {region}?',
            'Among countries in {region}, what was the rank of {subject} for {property} in {year}?',
        )

        allowed_values = {
            'subject': Subject,
            'property': Property,
            'region': Region,
            'year': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'int'

    def validate_combination(self, combination: dict) -> bool:
        """Ensure subject is in the region."""
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

        # Search for the indicator code for the property (for traceability)
        action = FrankensteinAction(
            'search_for_indicator_codes',
            keywords=self.i2n[self.property],
        )
        action.execute()
        action.result = [d for d in action.result if d['indicator_name'] == self.i2n[self.property]]
        self.actions.append(action.to_dict())
        indicator_code = self.slot_values['property']

        # Get the countries in the region
        action = FrankensteinAction(
            'get_country_codes_in_region',
            region=self.region,
        )
        action.execute()
        self.actions.append(action.to_dict())
        region_countries = action.result

        # Retrieve the property values for the region
        region_values = []
        for country in region_countries:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.year,
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
        subject_value = next((v for c, v in valid_values if c == subject_code), None)
        if subject_value is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        action = FrankensteinAction('rank', values=values_list, query_value=subject_value)
        action.execute()
        self.actions.append(action.to_dict())
        subject_rank = action.result

        if subject_rank is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=subject_rank)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a SubjectPropertyRank question.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to rank.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to rank by.')
    parser.add_argument('--region', type=str, choices=Region.get_values(), help='The region to rank within.')
    parser.add_argument('--year', type=str, choices=Year.get_values(), help='The year to rank for.')

    args = parser.parse_args()

    q = SubjectPropertyRank()
    if all([args.subject, args.property, args.region, args.year]):
        comb = {
            'subject': args.subject,
            'property': args.property,
            'region': args.region,
            'year': args.year,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
