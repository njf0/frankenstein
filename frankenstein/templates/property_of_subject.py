"""Template for region comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Subject, Year


class PropertyOfSubject(FrankensteinQuestion):
    """Class representing a simple retrieval question."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
    ):
        """Initialize a simple retrieval question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.

        """
        self.templates = (
            'What was the {property} of {subject} in {year}?',
            'In {year}, what was the {property} of {subject}?',
        )

        allowed_values = {
            'property': Property,
            'subject': Subject,
            'year': Year,
        }

        super().__init__(slot_values, allowed_values)

        self.metadata['answer_format'] = 'float'

    def compute_actions(self):
        """Perform steps using FrankensteinQuestion methods."""
        action = FrankensteinAction(
            'get_country_code_from_name',
            country_name=self.c2n[self.subject],
        )
        action.execute()
        self.actions.append(action.to_dict())
        country = action.result

        action = FrankensteinAction(
            'search_for_indicator_codes',
            keywords=self.i2n[self.property],
        )
        action.execute()
        action.result = [d for d in action.result if d['indicator_name'] == self.i2n[self.property]]
        self.actions.append(action.to_dict())
        indicator_code = self.slot_values['property']

        action = FrankensteinAction(
            'retrieve_value',
            country_code=country,
            indicator_code=indicator_code,
            year=self.year,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value = action.result

        if value is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False

            return None

        self.answer = value

        return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a PropertyOfSubject question.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to retrieve the property for.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to retrieve.')
    parser.add_argument('--year', type=str, choices=Year.get_values(), help='The year at which to retrieve the property.')

    args = parser.parse_args()

    q = PropertyOfSubject()

    if all(
        [
            args.subject,
            args.property,
            args.year,
        ]
    ):
        comb = {
            'subject': args.subject,
            'property': args.property,
            'year': args.year,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
