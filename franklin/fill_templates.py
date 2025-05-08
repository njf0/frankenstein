"""Generate dataset by filling slot values and computing answers."""

import argparse
import importlib
import inspect
import json
import logging
import pkgutil
from pathlib import Path

import templates
from rich.logging import RichHandler
from rich.progress import Progress


def get_templates(
    package: object,
) -> list:
    """Very stupid way to get all templates from a package.

    Parameters
    ----------
    package : object
        Package object.

    Returns
    -------
    list
        List of templates, where each template is a tuple of (name, module, class).

    """
    submodules = []
    package_name = package.__name__
    package_path = package.__path__

    for _, name, _ in pkgutil.iter_modules(package_path):
        full_name = package_name + '.' + name
        submodules.append(importlib.import_module(full_name))

    templates = []
    for submodule in submodules:
        for cls_name, cls in inspect.getmembers(submodule, inspect.isclass):
            if cls.__module__ == submodule.__name__:
                templates.append((cls_name, submodule, cls))

    return templates


TEMPLATES = get_templates(templates)


class TemplateFiller:
    """Fill slot values in templates and compute answers."""

    def __init__(self, templates, n):
        """Initialize TemplateFiller.

        Parameters
        ----------
        templates : list
            List of templates to fill.
        data_manager : DataManager
            DataManager object to fetch data.
        n : int
            Number of examples to generate.

        """
        self.templates = templates
        self.n = n

    def run(self, save=False):
        """Fill templates, compute answers, and display progress.

        Parameters
        ----------
        save : bool, optional
            Whether to save the generated examples to files, by default False

        Returns
        -------
        dict
            Dictionary of answerable examples for each template.
        dict
            Dictionary of not answerable examples for each template.

        """
        all_answerable, all_not_answerable = {}, {}

        # Initialize Rich progress bar
        with Progress() as progress:
            tasks = {
                template[0]: {
                    'answerable': progress.add_task(f'[green]{template[0]} (Answerable)', start=False, total=self.n),
                    'unanswerable': progress.add_task(f'[red]{template[0]} (Unanswerable)', start=False, total=self.n),
                }
                for template in self.templates
            }

            for template_name, module, template_class in self.templates:
                progress.start_task(tasks[template_name]['answerable'])
                progress.start_task(tasks[template_name]['unanswerable'])

                used_combinations = []
                answerable, not_answerable = [], []

                answerable_attempts = 0
                not_answerable_attempts = 0

                while True:
                    # Generate a random combination of slot values
                    t = template_class()
                    combination = t.get_random_combination()

                    # Check if the combination is already used
                    if combination in used_combinations:
                        continue

                    # Add the combination to the used combinations
                    used_combinations.append(combination)

                    # Compute the answer
                    t.create_question(combination)
                    t.compute_actions()
                    output = t.format_output()

                    # Add to answerable or not_answerable list
                    if output['metadata']['answerable'] and len(answerable) < self.n:
                        answerable.append(output)
                        progress.update(tasks[template_name]['answerable'], advance=1)
                    elif not output['metadata']['answerable'] and len(not_answerable) < self.n:
                        not_answerable.append(output)
                        progress.update(tasks[template_name]['unanswerable'], advance=1)

                    # Check if we have enough examples
                    if len(answerable) == self.n and len(not_answerable) == self.n:
                        break

                    # Check if we have too many attempts
                    if answerable_attempts > 100 * self.n:
                        print(f'Answerable examples not filled after {self.n * 1000} attempts for {template_name}, skipping.')
                        break
                    if not_answerable_attempts > 1000 * self.n:
                        print(f'Unanswerable examples not filled after {self.n * 1000} attempts for {template_name}, skipping.')
                        break

                all_answerable[template_name] = answerable
                all_not_answerable[template_name] = not_answerable

        # Save results to files
        for template_name, answerable in all_answerable.items():
            with Path('dataset', 'answerable', f'{template_name}.jsonl').open('w') as f:
                for example in answerable:
                    f.write(json.dumps(example) + '\n')
                    # f.write(json.dumps(example) + '\n') # Used for 'repeats' dataset
                    # f.write(json.dumps(example) + '\n')
                    # f.write(json.dumps(example) + '\n')
                    # f.write(json.dumps(example) + '\n')
                    # f.write(json.dumps(example) + '\n')
                    # f.write(json.dumps(example) + '\n')
                    # f.write(json.dumps(example) + '\n')
                    # f.write(json.dumps(example) + '\n')
                    # f.write(json.dumps(example) + '\n')

        for template_name, not_answerable in all_not_answerable.items():
            with Path('dataset', 'unanswerable', f'{template_name}.jsonl').open('w') as f:
                for example in not_answerable:
                    f.write(json.dumps(example) + '\n')

        return all_answerable, all_not_answerable


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--number', '-n', type=int, default=-1)
    parser.add_argument(
        '--templates',
        '-t',
        nargs='+',
        choices=[t[0] for t in TEMPLATES],
        default=[t[0] for t in TEMPLATES],
    )
    parser.add_argument('--save', '-s', action='store_true')
    args = parser.parse_args()

    # Set up logging
    FORMAT = '%(message)s'
    logging.basicConfig(
        level=logging.ERROR,
        format=FORMAT,
        datefmt='[%X]',
        handlers=[RichHandler()],
    )

    # Filter selected templates
    selected_templates = [t for t in TEMPLATES if t[0] in args.templates]

    # Fill templates
    filler = TemplateFiller(selected_templates, args.number)
    all_answerable, all_not_answerable = filler.run(save=False)
