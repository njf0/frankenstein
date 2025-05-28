"""Generate dataset by filling slot values and computing answers."""

import argparse
import importlib
import inspect
import json
import logging
import pkgutil
import time
from pathlib import Path

import templates
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress
from rich.table import Table


def get_templates(
    package: object,
) -> list:
    """Get all templates from a package.

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
        n : int
            Number of examples to generate.

        """
        self.templates = templates
        self.n = n
        # Optional: mapping of template_name to set of categories to skip
        self.skip_categories = {
            'AverageChange': {'unanswerable_partial'},
            'AverageProperty': {'unanswerable_partial'},
            'AveragePropertyComparison': {'unanswerable_partial'},
            'CountryPropertyComparison': {'answerable_partial'},
            'CountryThresholdCount': {'unanswerable_partial'},
            'FactorIncreaseComparison': {'answerable_partial'},
            'IncreasePropertyComparison': {'unanswerable_partial'},
            'PropertyOfSubject': {'unanswerable_partial', 'answerable_partial'},
            'PropertyRatio': {'unanswerable_partial'},
            'RankPositionChange': {'answerable_partial'},
            'RegionComparisonResult': {'unanswerable_partial'},
            'RegionComparison': {'unanswerable_partial', 'answerable_partial'},
            'RegionProportionChange': {'unanswerable_partial', 'answerable_partial'},
            'RegionProportion': {'unanswerable_partial', 'answerable_partial'},
            'RegionRangeComparison': {'unanswerable_partial'},
            'SubjectPropertyRank': {'unanswerable_partial'},
            'TopNTotal': {'unanswerable_partial'},
            'TotalProperty': {'unanswerable_partial', 'answerable_partial'},
        }

    def set_skip_categories(
        self,
        skip_dict: dict,
    ) -> None:
        """Set skip categories for templates.

        Parameters
        ----------
            skip_dict: dict
                dict mapping template_name to set of category strings to skip.

        """
        self.skip_categories = skip_dict

    def run(
        self,
        save=False,
        unified_progress=True,  # always use unified progress bar now
    ) -> dict:
        """Fill templates, compute answers, and display progress.

        Parameters
        ----------
        save : bool, optional
            Whether to save the generated examples to files, by default False
        unified_progress : bool, optional
            Whether to use a unified progress bar for all templates, by default False

        Returns
        -------
        dict
            Dictionary of examples for each template and category.

        """
        all_results = {}
        template_timings = []
        total_start = time.time()

        # Always use unified progress bar
        total_to_fill = 0
        for template in self.templates:
            template_name = template[0]
            skip_set = self.skip_categories.get(template_name, set())
            total_to_fill += (4 - len(skip_set)) * self.n

        with Progress() as progress:
            unified_task = progress.add_task('[cyan]All Templates', total=total_to_fill)

            for template_name, module, template_class in self.templates:
                # Initialise success counts for each category
                success_counts = {
                    'answerable_full': 0,
                    'answerable_partial': 0,
                    'unanswerable_partial': 0,
                    'unanswerable_missing': 0,
                }

                def progress_desc(template_name, success_counts, skip_set):
                    def fmt(cat, color):
                        val = success_counts[cat]
                        if cat in skip_set:
                            return f'[{color} dim]{val}[/{color} dim]'
                        else:
                            return f'[{color}]{val}[/{color}]'

                    return (
                        f'[cyan]Filling: [bold]{template_name}[/bold] ('
                        f'{fmt("answerable_full", "green")} / '
                        f'{fmt("answerable_partial", "yellow")} / '
                        f'{fmt("unanswerable_partial", "magenta")} / '
                        f'{fmt("unanswerable_missing", "red")})'
                    )

                skip_set = self.skip_categories.get(template_name, set())
                progress.update(
                    unified_task,
                    description=progress_desc(template_name, success_counts, skip_set),
                )
                template_start = time.time()

                skip_set = self.skip_categories.get(template_name, set())

                used_combinations = []
                answerable_full, answerable_partial = [], []
                unanswerable_partial, unanswerable_missing = [], []

                attempts = 0
                max_attempts = 1000 * self.n if self.n > 0 else 1000
                filled_attempts = {
                    'answerable_full': None,
                    'answerable_partial': None,
                    'unanswerable_partial': None,
                    'unanswerable_missing': None,
                }

                while True:
                    attempts += 1
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

                    # Determine answerability and data availability
                    answerable = output['metadata'].get('answerable', None)
                    data_availability = output['metadata'].get('data_availability', None)

                    updated_any = False
                    if (
                        'answerable_full' not in skip_set
                        and answerable is True
                        and data_availability == 'full'
                        and len(answerable_full) < self.n
                    ):
                        answerable_full.append(output)
                        success_counts['answerable_full'] += 1
                        if len(answerable_full) == self.n and filled_attempts['answerable_full'] is None:
                            filled_attempts['answerable_full'] = attempts
                        updated_any = True
                    elif (
                        'answerable_partial' not in skip_set
                        and answerable is True
                        and data_availability == 'partial'
                        and len(answerable_partial) < self.n
                    ):
                        answerable_partial.append(output)
                        success_counts['answerable_partial'] += 1
                        if len(answerable_partial) == self.n and filled_attempts['answerable_partial'] is None:
                            filled_attempts['answerable_partial'] = attempts
                        updated_any = True
                    elif (
                        'unanswerable_partial' not in skip_set
                        and answerable is False
                        and data_availability == 'partial'
                        and len(unanswerable_partial) < self.n
                    ):
                        unanswerable_partial.append(output)
                        success_counts['unanswerable_partial'] += 1
                        if len(unanswerable_partial) == self.n and filled_attempts['unanswerable_partial'] is None:
                            filled_attempts['unanswerable_partial'] = attempts
                        updated_any = True
                    elif (
                        'unanswerable_missing' not in skip_set
                        and answerable is False
                        and data_availability == 'missing'
                        and len(unanswerable_missing) < self.n
                    ):
                        unanswerable_missing.append(output)
                        success_counts['unanswerable_missing'] += 1
                        if len(unanswerable_missing) == self.n and filled_attempts['unanswerable_missing'] is None:
                            filled_attempts['unanswerable_missing'] = attempts
                        updated_any = True

                    # Unified progress bar: advance for every successful fill
                    if updated_any:
                        progress.update(unified_task, advance=1)
                        # Update the progress bar description with new counts and dim skipped
                        progress.update(
                            unified_task,
                            description=progress_desc(template_name, success_counts, skip_set),
                        )

                    # Check if we have enough examples for all non-skipped categories
                    enough = True
                    if 'answerable_full' not in skip_set and len(answerable_full) < self.n:
                        enough = False
                    if 'answerable_partial' not in skip_set and len(answerable_partial) < self.n:
                        enough = False
                    if 'unanswerable_partial' not in skip_set and len(unanswerable_partial) < self.n:
                        enough = False
                    if 'unanswerable_missing' not in skip_set and len(unanswerable_missing) < self.n:
                        enough = False
                    if enough:
                        break

                    if attempts > max_attempts:
                        print(f'Not all categories filled after {max_attempts} attempts for {template_name}, skipping.')
                        break

                template_end = time.time()
                elapsed = template_end - template_start
                num_categories = 4 - len(skip_set)
                time_per_attempt = elapsed / attempts if attempts > 0 else 0

                template_timings.append(
                    {
                        'template': template_name,
                        'answerable_full': filled_attempts['answerable_full'] if 'answerable_full' not in skip_set else None,
                        'answerable_partial': filled_attempts['answerable_partial']
                        if 'answerable_partial' not in skip_set
                        else None,
                        'unanswerable_partial': filled_attempts['unanswerable_partial']
                        if 'unanswerable_partial' not in skip_set
                        else None,
                        'unanswerable_missing': filled_attempts['unanswerable_missing']
                        if 'unanswerable_missing' not in skip_set
                        else None,
                        'total_time': elapsed,
                        'time_per_attempt': time_per_attempt,
                    }
                )

                all_results[template_name] = {
                    'answerable_full': answerable_full,
                    'answerable_partial': answerable_partial,
                    'unanswerable_partial': unanswerable_partial,
                    'unanswerable_missing': unanswerable_missing,
                }

                # Save results to files, one folder per category
                outdir = Path('dataset')
                (outdir / 'answerable_full').mkdir(parents=True, exist_ok=True)
                (outdir / 'answerable_partial').mkdir(parents=True, exist_ok=True)
                (outdir / 'unanswerable_partial').mkdir(parents=True, exist_ok=True)
                (outdir / 'unanswerable_missing').mkdir(parents=True, exist_ok=True)

                with (outdir / 'answerable_full' / f'{template_name}.jsonl').open('w') as f:
                    for example in answerable_full:
                        f.write(json.dumps(example) + '\n')
                with (outdir / 'answerable_partial' / f'{template_name}.jsonl').open('w') as f:
                    for example in answerable_partial:
                        f.write(json.dumps(example) + '\n')
                with (outdir / 'unanswerable_partial' / f'{template_name}.jsonl').open('w') as f:
                    for example in unanswerable_partial:
                        f.write(json.dumps(example) + '\n')
                with (outdir / 'unanswerable_missing' / f'{template_name}.jsonl').open('w') as f:
                    for example in unanswerable_missing:
                        f.write(json.dumps(example) + '\n')

        total_end = time.time()
        total_time = total_end - total_start

        # Print summary table
        console = Console()
        table = Table(title='Template Fill Timing Summary')
        table.add_column('Template', style='cyan')
        table.add_column('Ans-Full', justify='right', style='green')
        table.add_column('Ans-Part', justify='right', style='yellow')
        table.add_column('Unans-Part', justify='right', style='magenta')
        table.add_column('Unans-Miss', justify='right', style='red')
        table.add_column('Total Time (s)', justify='right', style='cyan')
        table.add_column('Time/Attempt (s)', justify='right', style='cyan')

        for entry in template_timings:

            def fmt(val):
                return str(val) if val is not None else ''

            table.add_row(
                entry['template'],
                fmt(entry['answerable_full']),
                fmt(entry['answerable_partial']),
                fmt(entry['unanswerable_partial']),
                fmt(entry['unanswerable_missing']),
                f'{entry["total_time"]:.2f}',
                f'{entry["time_per_attempt"]:.3f}',
            )
        table.add_section()
        # Totals: sum of filled categories, total time, avg time/attempt
        total_templates = len(template_timings)
        total_categories_filled = sum(
            1
            for entry in template_timings
            for k in ['answerable_full', 'answerable_partial', 'unanswerable_partial', 'unanswerable_missing']
            if entry[k] is not None
        )
        avg_time_per_attempt = (
            sum(entry['time_per_attempt'] for entry in template_timings) / total_templates if total_templates > 0 else 0
        )
        table.add_row(
            '[bold]Total[/bold]',
            '',
            '',
            '',
            '',
            f'{total_time:.2f}',
            f'{avg_time_per_attempt:.3f}',
            end_section=True,
        )
        console.print(table)

        return all_results


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
    results = filler.run(save=False)
