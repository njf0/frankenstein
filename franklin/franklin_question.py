"""Base class for Franklin questions."""

import itertools
import json
import random
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

from franklin.slot_values import Slot

DATA_DIR = Path('resources')
INDICATOR_DATA_DIR = DATA_DIR / 'wdi'
INDICATOR_KEY = DATA_DIR / 'wdi.csv'
ISO_3166 = DATA_DIR / 'iso_3166.csv'


class FranklinQuestion:
    """Base class for Franklin questions."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
        allowed_values: dict[str, Slot] | None = None,
    ):
        """Initialize a Franklin question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.
        data_manager: DataManager
            Instance of DataManager with preloaded datasets.


        """
        # Indicator/country-related data things
        # Create mapping of country_codes to country_names
        self.country_region_data = pd.read_csv(ISO_3166)
        self.c2n = self.country_region_data.set_index('country_code')['country_name'].to_dict()
        self.n2c = self.country_region_data.set_index('country_name')['country_code'].to_dict()

        # Create mapping of indicator names to indicator ids
        self.indicator_key = pd.read_csv(INDICATOR_KEY)
        self.n2i = self.indicator_key.set_index('name')['id'].to_dict()
        self.i2n = self.indicator_key.set_index('id')['name'].to_dict()

        # Indicator paraphrases
        with Path('resources', 'indicator_paraphrases.json').open() as f:
            self.indicator_paraphrases = json.load(f)

        # Core FranklinQuestion attributes
        self.allowed_values = allowed_values
        self.question = None
        self.actions = []
        self.answer = None

        # Metadata
        self.metadata = {
            'answerable': True,
            'answer_format': None,
            'data_availability': 'full',
            'question_template': self.__class__.__name__,
        }

    def get_random_combination(
        self,
    ) -> dict:
        """Get a random combination of slot values based on the allowed values.

        Parameters
        ----------
        allowed_values: dict
            Allowed values for the slots.

        Returns
        -------
        combination: dict
            A random combination of slot values.

        """
        valid_combination = False
        while not valid_combination:
            # Fill slot values with random values from the allowed values
            comb = {slot_name: random.choice(slot.get_values()) for slot_name, slot in self.allowed_values.items()}
            # Validate the combination
            valid_combination = self.validate_combination(comb)

        return comb

    def get_all_combinations(
        self,
        allowed_values: dict[str, Slot],
    ) -> list:
        """Get all possible combinations of slot values, bearing in mind constraints. Could be very slow.

        Parameters
        ----------
        allowed_values: dict
            Allowed values for the slots.

        Returns
        -------
        combinations: list
            A list of all possible combinations of slot values.

        """
        # Get all possible combinations of slot values
        combs = itertools.product(*[v.get_values() for v in allowed_values.values()])

        # Filter out invalid combinations
        combs = [c for c in combs if self.validate_combination(dict(zip(allowed_values.keys(), c)))]

        # Convert to list of dictionaries
        return [dict(zip(allowed_values.keys(), combination)) for combination in combs]

    def validate_combination(self, combination: dict) -> bool:
        """Validate the combination of slot values. Can be overridden in subclasses.

        This method is used to check if the combination of slot values is valid. It can be overridden in subclasses
        to add custom validation logic. The default implementation always returns True.

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

    def create_question(
        self,
        slot_values: dict[str, str],
    ) -> str:
        """Turn a collection of slot values in to a natural language question."""
        formatted_slot_values = slot_values.copy()

        # Get property name from id
        if 'property' in slot_values:
            paraphrase = random.choice(self.indicator_paraphrases[slot_values['property']])
            formatted_slot_values['property'] = paraphrase
        if 'property_1' in slot_values:
            property_1_name = self.i2n[slot_values['property_1']]
            formatted_slot_values['property_1'] = property_1_name
        if 'property_2' in slot_values:
            property_2_name = self.i2n[slot_values['property_2']]
            formatted_slot_values['property_2'] = property_2_name
        # Get country name from code
        if 'subject' in slot_values:
            subject_name = self.c2n[slot_values['subject']]
            formatted_slot_values['subject'] = subject_name
        if 'subject_a' in slot_values:
            subject_a_name = self.c2n[slot_values['subject_a']]
            formatted_slot_values['subject_a'] = subject_a_name
        if 'subject_b' in slot_values:
            subject_b_name = self.c2n[slot_values['subject_b']]
            formatted_slot_values['subject_b'] = subject_b_name

        self.slot_values = slot_values

        for key, value in slot_values.items():
            setattr(self, key, value)

        template_choice = random.choice(self.templates)

        self.question = template_choice.format(**formatted_slot_values)

        return self.question

    def format_output(
        self,
    ) -> dict:
        """Format question, facts, etc., for output into dataset."""
        return {
            'question': self.question,
            'actions': self.actions,
            'answer': self.answer,
            'metadata': {
                'question_template': self.__class__.__name__,
                'slot_values': self.slot_values,
                'answerable': self.metadata['answerable'],
                'data_availability': self.metadata['data_availability'],
                'answer_format': self.metadata['answer_format'],
                'total_actions': len(self.actions),
            },
        }

    def compute_answer(self) -> str:
        """Compute the answer to the question."""
        raise NotImplementedError

    def compute_actions(self) -> str:
        """Compute the actions to be taken for the question."""
        raise NotImplementedError

    def pretty_print(self) -> str:
        """Pretty print the question."""
        console = Console()

        # Compute answer and format output
        self.compute_actions()

        # Decide if data_availability == partial is answerable or not
        # if self.metadata['data_availability'] == 'missing' or self.metadata['data_availability'] == 'partial':
        #     self.metadata['answerable'] = False
        # elif self.metadata['data_availability'] == 'full':
        #     self.metadata['answerable'] = True

        formatted_output = self.format_output()

        # Create a table for the question template, slot values, and question
        table = Table(title=formatted_output['question'], show_lines=True, width=128)

        table.add_column('Action', justify='right', style='cyan', no_wrap=True)
        table.add_column('Arguments', style='magenta')
        table.add_column('Result', style='green')

        for action in formatted_output['actions']:
            table.add_row(
                action['name'],
                json.dumps(action['arguments']),
                str(action['result']),
            )
        # table.add_row('answer', str(self.answer))

        console.print(table)

        # New table for metadata
        metadata_table = Table(title='Metadata', show_lines=True, width=128)
        metadata_table.add_column('Key', justify='right', style='cyan', no_wrap=True)
        metadata_table.add_column('Value', style='magenta')
        for key, value in formatted_output['metadata'].items():
            metadata_table.add_row(key, str(value))
        console.print(metadata_table)
