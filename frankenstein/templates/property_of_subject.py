"""Template for subject set comparison questions."""

import argparse

from frankenstein.action import FrankensteinAction
from frankenstein.frankenstein_question import FrankensteinQuestion
from frankenstein.slot_values import Property, Subject, Time


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
            'What was the {property} of {subject} in {time}?',
            'In {time}, what was the {property} of {subject}?',
        )

        allowed_values = {
            'property': Property,
            'subject': Subject,
            'time': Time,
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
            'get_indicator_code_from_name',
            indicator_name=self.i2n[self.property],
        )
        action.execute()
        self.actions.append(action.to_dict())
        indicator_code = action.result

        action = FrankensteinAction(
            'retrieve_value',
            country_code=country,
            indicator_code=indicator_code,
            year=self.time,
        )
        action.execute()
        self.actions.append(action.to_dict())
        value = action.result

        if value is None:
            self.metadata['data_availability'] = 'missing'
            self.metadata['answerable'] = False

            return None

        self.metadata['data_availability'] = 'full'
        answer = FrankensteinAction('final_answer', answer=value)
        answer.execute()
        self.actions.append(answer.to_dict())
        self.answer = value

        return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate a PropertyOfSubject question.')
    parser.add_argument('--subject', type=str, choices=Subject.get_values(), help='The subject to retrieve the property for.')
    parser.add_argument('--property', type=str, choices=Property.get_values(), help='The property to retrieve.')
    parser.add_argument('--time', type=str, choices=Time.get_values(), help='The time at which to retrieve the property.')

    args = parser.parse_args()

    q = PropertyOfSubject()

    if all(
        [
            args.subject,
            args.property,
            args.time,
        ]
    ):
        comb = {
            'subject': args.subject,
            'property': args.property,
            'time': args.time,
        }

    else:
        comb = q.get_random_combination()

    q.create_question(comb)
    q.pretty_print()
