"""Template for region property change questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import NaryOperator, Property, Region, Year


class RegionPropertyChange(FrankensteinQuestion):
    """Class representing a region property change question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a region property change question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'Which country in {region} had the {operator} change in {property} between {year_a} and {year_b}?',
            'Between {year_a} and {year_b}, which country in {region} had the {operator} change in {property}?',
            'For the countries in {region}, which had the {operator} change in {property} between {year_a} and {year_b}?',
        )

        allowed_values = {
            'region': Region,
            'property': Property,
            'operator': NaryOperator,
            'year_a': Year,
            'year_b': Year,
        }

        super().__init__(slot_values, allowed_values)
        self.metadata['answer_format'] = 'list[str]'

    def validate_combination(self, combination: dict) -> bool:
        """Ensure years are different."""
        return combination['year_a'] != combination['year_b']

    def compute_actions(self):
        """Compute actions for the question."""
        # Get countries in the region
        action = FrankensteinAction('get_country_codes_in_region', region=self.region)
        action.execute()
        self.actions.append(action.to_dict())
        countries = action.result

        # Get the indicator code for the property
        action = FrankensteinAction('get_indicator_code_from_name', indicator_name=self.i2n[self.property])
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        # Retrieve values for each country for both years
        changes = []
        for country in countries:
            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.year_a,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value_a = action.result

            action = FrankensteinAction(
                'retrieve_value',
                country_code=country,
                indicator_code=indicator_code,
                year=self.year_b,
            )
            action.execute()
            self.actions.append(action.to_dict())
            value_b = action.result

            # If either value is missing, skip for now
            if value_a is None or value_b is None:
                changes.append((country, None))
            else:
                action = FrankensteinAction('subtract', value_a=value_b, value_b=value_a)
                action.execute()
                self.actions.append(action.to_dict())
                diff = action.result

                changes.append((country, diff))

        # Data availability checks
        if all(change is None for _, change in changes):
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return
        if any(change is None for _, change in changes):
            self.metadata['data_availability'] = 'partial'

        # Find the highest/lowest absolute change
        valid_changes = [(c, v) for c, v in changes if v is not None]
        if not valid_changes:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False
            return

        values = [v for _, v in valid_changes]
        if self.operator == 'highest':
            action = FrankensteinAction('maximum', values=values)
        elif self.operator == 'lowest':
            action = FrankensteinAction('minimum', values=values)
        action.execute()
        self.actions.append(action.to_dict())
        target_change = action.result

        # Get all countries with the target change (handle ties)
        top_countries = [self.c2n[c] for c, v in valid_changes if v == target_change]

        # Set the final answer
        action = FrankensteinAction('final_answer', answer=top_countries)
        action.execute()
        self.actions.append(action.to_dict())
        self.answer = action.result

        return self.answer


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a RegionPropertyChange question.')
    parser.add_argument('--region', type=str, choices=Region.get_values(), help='The region to check.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to check.')
    parser.add_argument('--operator', type=str, choices=NaryOperator.get_values(), help='The operator (highest/lowest).')
    parser.add_argument('--year_a', type=str, choices=Year.get_values(), help='The first year.')
    parser.add_argument('--year_b', type=str, choices=Year.get_values(), help='The second year.')

    args = parser.parse_args()

    q = RegionPropertyChange()
    if all([args.region, args.property, args.operator, args.year_a, args.year_b]):
        comb = {
            'region': args.region,
            'property': args.property,
            'operator': args.operator,
            'year_a': args.year_a,
            'year_b': args.year_b,
        }
    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
