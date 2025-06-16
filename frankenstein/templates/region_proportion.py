"""Template for region proportion questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Region, Subject, Year


class RegionProportion(FrankensteinQuestion):
    """Class representing a region proportion question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a region proportion question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'In {year}, what proportion of the total {property} of {region} was contributed by {subject}?',
            'What proportion of the total {property} of {region} in {year} was contributed by {subject}?',
            'For the countries in {region}, what proportion of the total {property} was contributed by {subject} in {year}?',
            'What proportion of the total {property} was contributed by {subject} for the countries in {region} in {year}?',
        )

        allowed_values = {
            'property': Property,
            'subject': Subject,
            'region': Region,
            'year': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'float'

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

        # Retrieve the property value for the subject
        action = FrankensteinAction(
            'retrieve_value',
            country_code=subject_code,
            indicator_code=indicator_code,
            year=self.year,
        )
        action.execute()
        self.actions.append(action.to_dict())
        subject_value = action.result

        # Check for missing data
        if subject_value is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False

            return

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
            region_values.append(value)

        # Check for missing data
        if any(v is None for v in region_values):
            self.metadata['data_availability'] = 'partial'

        if all(v is None for v in region_values):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False

            return

        # Compute the total property value for the region
        action = FrankensteinAction('add', values=region_values)
        action.execute()
        self.actions.append(action.to_dict())
        region_total = action.result

        # Compute the proportion
        action = FrankensteinAction('divide', value_a=subject_value, value_b=region_total)
        action.execute()
        self.actions.append(action.to_dict())
        proportion = action.result

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=proportion)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionProportion question.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to compare.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to compare.')
    parser.add_argument('--region', type=str, choices=Region.get_values(), help='The region to compare against.')
    parser.add_argument('--year', type=str, choices=Year.get_values(), help='The year to compare.')

    args = parser.parse_args()

    q = RegionProportion()
    if all([args.property, args.subject, args.region, args.year]):
        comb = {
            'property': args.property,
            'subject': args.subject,
            'region': args.region,
            'year': args.year,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
