"""Base class for Frankenstein questions."""

import itertools
import json
import random
from pathlib import Path
from uuid import uuid4

import pandas as pd
from rich.console import Console
from rich.table import Table

from frankenstein.slot_values import Slot

DATA_DIR = Path('resources')
INDICATOR_DATA_DIR = DATA_DIR / 'wdi'
INDICATOR_KEY = DATA_DIR / 'wdi.csv'
UN_M49 = DATA_DIR / 'un_m49_cleaned.csv'


class FrankensteinQuestion:
    """Base class for Frankenstein questions."""

    def __init__(
        self,
        slot_values: dict[str, str] | None = None,
        allowed_values: dict[str, Slot] | None = None,
    ):
        """Initialize a Frankenstein question.

        Parameters
        ----------
        slot_values: dict[str, str]
            Slot values for the question.
        data_manager: DataManager
            Instance of DataManager with preloaded datasets.


        """
        # Indicator/country-related data things
        # Create mapping of country_codes to country_names
        self.country_region_data = pd.read_csv(UN_M49)
        self.c2n = self.country_region_data.set_index('country_code')['country_name'].to_dict()
        self.n2c = self.country_region_data.set_index('country_name')['country_code'].to_dict()

        # Create mapping of indicator names to indicator ids
        self.indicator_key = pd.read_csv(INDICATOR_KEY)
        self.n2i = self.indicator_key.set_index('name')['id'].to_dict()
        self.i2n = self.indicator_key.set_index('id')['name'].to_dict()

        # Indicator paraphrases
        with Path('resources', 'indicator_paraphrases.json').open() as f:
            self.indicator_paraphrases = json.load(f)

        # Core FrankensteinQuestion attributes
        self.allowed_values = allowed_values
        self.question = None
        self.actions = []
        self.answer = None

        # Metadata
        self.metadata = {
            'id': str(uuid4()),
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

        # --- Add original (non-paraphrased) indicator name to slot_values ---
        if 'property' in slot_values:
            property_id = slot_values['property']
            property_original = self.i2n.get(property_id)
            if property_original:
                slot_values['property_original'] = property_original
                formatted_slot_values['property_original'] = property_original

        # --- Add full country name to slot_values if 'subject', 'subject_a', or 'subject_b' is present ---
        if 'subject' in slot_values:
            subject_code = slot_values['subject']
            subject_name = self.c2n.get(subject_code)
            if subject_name:
                slot_values['subject_name'] = subject_name
                formatted_slot_values['subject_name'] = subject_name
        if 'subject_a' in slot_values:
            subject_a_code = slot_values['subject_a']
            subject_a_name = self.c2n.get(subject_a_code)
            if subject_a_name:
                slot_values['subject_a_name'] = subject_a_name
                formatted_slot_values['subject_a_name'] = subject_a_name
        if 'subject_b' in slot_values:
            subject_b_code = slot_values['subject_b']
            subject_b_name = self.c2n.get(subject_b_code)
            if subject_b_name:
                slot_values['subject_b_name'] = subject_b_name
                formatted_slot_values['subject_b_name'] = subject_b_name

        # Get property name from id (paraphrase)
        if 'property' in slot_values:
            paraphrase = random.choice(
                *[i['paraphrase'] for i in self.indicator_paraphrases if i['id'] == slot_values['property']]
            )
            formatted_slot_values['property'] = paraphrase
        # if 'property_1' in slot_values:
        #     property_1_name = self.i2n[slot_values['property_1']]
        #     formatted_slot_values['property_1'] = property_1_name
        # if 'property_2' in slot_values:
        #     property_2_name = self.i2n[slot_values['property_2']]
        #     formatted_slot_values['property_2'] = property_2_name
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
            'id': self.metadata['id'],
            'question_template': self.metadata['question_template'],
            'question': self.question,
            'actions': self.actions,
            'answer': self.answer,
            'slot_values': self.slot_values,
            'answerable': self.metadata['answerable'],
            'data_availability': self.metadata['data_availability'],
            'answer_format': self.metadata['answer_format'],
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
        table_width = min(128, console.width)

        # Compute answer and format output
        self.compute_actions()
        formatted_output = self.format_output()

        # New table for metadata
        slot_values_table = Table(title='Question Slot Values', show_lines=True, width=table_width)
        slot_values_table.add_column('Key', justify='right', style='cyan', no_wrap=True, width=table_width // 2)
        slot_values_table.add_column('Value', style='magenta', width=table_width // 2)
        for key, value in formatted_output['slot_values'].items():
            slot_values_table.add_row(key, str(value))
        console.print(slot_values_table)

        # Create a table for the question template, slot values, and question
        table = Table(
            title=formatted_output['question'], show_lines=True, width=table_width, show_footer=formatted_output['answerable']
        )

        table.add_column('Action', justify='right', style='cyan', no_wrap=True)
        table.add_column('Arguments', style='magenta')
        table.add_column('Result', style='green')

        for action in formatted_output['actions']:
            table.add_row(
                action['name'],
                json.dumps(action['arguments']),
                str(action['result']),
            )

        # Add a footer row with the answer
        if formatted_output['answerable']:
            table.columns[0].footer = 'Final Answer'
            table.columns[1].footer = ''
            table.columns[2].footer = str(formatted_output['answer'])

        console.print(table)

        # Final table for metadata
        metadata_table = Table(title='Metadata', show_lines=True, width=table_width)
        metadata_table.add_column('Key', justify='right', style='cyan', no_wrap=True, width=table_width // 2)
        metadata_table.add_column('Value', style='magenta', width=table_width // 2)
        metadata_table.add_row('Question Template', formatted_output['question_template'])
        metadata_table.add_row('Answerable', str(formatted_output['answerable']))
        metadata_table.add_row('Data Availability', formatted_output['data_availability'])
        metadata_table.add_row('Answer Format', formatted_output['answer_format'])
        console.print(metadata_table)
