import argparse
import json
from pathlib import Path

import pandas as pd
from openai import OpenAI
from rich.console import Console
from rich.progress import BarColumn, Progress, ProgressColumn, SpinnerColumn, TextColumn, TimeRemainingColumn

console = Console()

SUFFIXES_TO_FILTER = {
    'PC',
    'CD',
    'XD',
    'ZS',
    'PP',
    'P6',
    'P5',
    'P2',
}
SYSTEM_PROMPT = """You are a helpful assistant that paraphrases World Bank indicator names using the context provided in the additional description.

    Return exactly {n} clear, concise **noun phrases** that faithfully represent the meaning of the original indicator name. Output them as a semicolon-delimited list.

    These noun phrases will be inserted into questions like:

    - "Which country in Eastern Europe had the highest <paraphrased indicator name> in 2020?"
    - "Was the average <paraphrased indicator name> in Northern America higher or lower than the value for Ghana in 2020?"
    - "What was the <paraphrased indicator name> in 2020 for the country with the highest value in South Asia?"
    - "Did <country> have a higher <paraphrased indicator name> than <other_country> in 2020?"

    Write the paraphrases **as if a person were using them to ask a question like the ones above**. Make them sound **natural and conversational**, like something someone would realistically say or hear, without compromising technical accuracy.

    Follow these guidelines:
    - Make all outputs concise, grammatical, easy to understand and **suitable for inserting into questions** like these.
    - Compress the phrase into the **shortest possible form** while retaining the meaning.
    - Do not use the words **total** or **average** in the paraphrase as this will interfere with the grammar of the wider questions.
    - Include bracketed elements, e.g., "(% of GDP)" as natural language phrases, such as "as a percentage of GDP".
    - **Do not include units of measurement**, e.g., "in US dollars", or "in TEUs".
    - Avoid embellished and abstract language, or esoteric terms. If an indicator name is very simple (e.g., 'rural population', 'net migration', 'surface area'), use that as one of the {n} paraphrases.
    - **Only capitalize proper nouns or acronyms**. Even though these are noun phrases, they will be inserted into the middle of sentences.
    - Use the additional description only to **clarify meaning**, not to add new information.
    - To repeat, paraphrases should be **noun phrases**. Start the phrase with something like 'count of', 'number of', 'percentage of', 'area of', 'rate of' if you are not sure how to begin.

    Reminder: preserve the meaning of the original indicator name; shorten as much as possible; and do not use unusual phrasing.
    """


class Paraphraser:
    def __init__(
        self,
        output_file: str | Path | None = None,
        model: str = 'gpt-4.1-mini',
        overwrite: bool = False,
        num_paraphrases: int = 3,
    ):
        """Initialize the Paraphraser with configuration options.

        Parameters
        ----------
        output_file : str | Path | None, optional
            The output file to save paraphrases to. If None, defaults to 'resources/indicator_paraphrases.json'.
        model : str, optional
            The OpenAI model to use for paraphrasing, by default 'gpt-4.1-mini'.
        overwrite : bool, optional
            Whether to overwrite existing paraphrase files, by default False.
        num_paraphrases : int, optional
            The number of paraphrases to generate for each indicator, by default 3.

        """
        self.output_file = Path(output_file) if output_file else Path('resources', 'indicator_paraphrases.json')
        self.model = model
        self.overwrite = overwrite
        self.num_paraphrases = num_paraphrases

    def filter_indicators(
        self,
        df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Filter out indicators with specific suffixes in their IDs.

        Parameters
        ----------
        df : pd.DataFrame
            DataFrame containing World Bank indicators with an 'id' column.

        Returns
        -------
        pd.DataFrame
            Filtered DataFrame excluding indicators with specified suffixes in their IDs.

        """
        return df[~df['id'].apply(lambda x: any(suffix in x.split('.') for suffix in SUFFIXES_TO_FILTER))]

    def paraphrase_indicator(
        self,
        name: str,
        source_note: str = '',
    ) -> str:
        """Generate paraphrases for a World Bank indicator name using OpenAI's API.

        Parameters
        ----------
        name : str
            The name of the World Bank indicator to paraphrase.
        source_note : str, optional
            Additional description or context for the indicator, by default ''.

        Returns
        -------
        str
            A semicolon-delimited string of paraphrases.

        """
        user_prompt = f"""Indicator name: {name}

        Additional description of indicator: {source_note}
        """

        client = OpenAI()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT.format(n=self.num_paraphrases)},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0,
            max_tokens=90,
        )
        return response.choices[0].message.content

    def get_all_paraphrase_lengths(
        self,
        data: list,
    ) -> list:
        """Get the lengths of all paraphrases in the provided data.

        Parameters
        ----------
        data : list
            List of dictionaries containing paraphrases under the 'paraphrase' key.

        Returns
        -------
        list
            List of lengths of each paraphrase in words.

        """
        lengths = []
        for entry in data:
            for p in entry.get('paraphrase', []):
                lengths.append(len(p.split(' ')))
        return lengths

    def paraphrase_file_complete(
        self,
        sample: list,
    ):
        """Check which indicator ids are missing or incomplete in the paraphrase file.

        Returns
        -------
        missing_ids : set
            Set of indicator ids that are missing or have incomplete paraphrases.

        """
        # If no output file, all ids are missing
        if not self.output_file.exists():
            return set(s['id'] for s in sample)

        # If the file exists, read it and check for missing ids
        with self.output_file.open('r') as f:
            try:
                existing_file = json.load(f)
            except json.JSONDecodeError:
                console.log(f'[red]Error reading JSON from {self.output_file}[/red]')
                return {s['id'] for s in sample}

        # Create a mapping from id to paraphrase list
        id_to_paraphrase = {p['id']: p.get('paraphrase', []) for p in existing_file if 'id' in p}
        sample_ids = {s['id'] for s in sample}
        missing_ids = set()

        # Check each sample id against the existing paraphrases
        for s in sample:
            paraphrases = id_to_paraphrase.get(s['id'])
            if not paraphrases or len(paraphrases) != 3 or not all(isinstance(p, str) and p.strip() for p in paraphrases):
                missing_ids.add(s['id'])

        # Also include any sample ids not present in the file
        missing_ids |= sample_ids - set(id_to_paraphrase.keys())
        return missing_ids

    def run(
        self,
    ) -> None:
        """Run the paraphrasing process."""
        # Load the indicators data
        console.rule('[bold blue]World Bank Indicator Paraphraser')

        console.log('[bold cyan]Loading indicator data...[/bold cyan]')
        try:
            with Path('resources', 'wdi.csv').open('r') as f:
                indicators = pd.read_csv(f)
        except FileNotFoundError:
            console.log('[red]Error: wdi.csv file not found in resources directory.[/red]')
            return

        console.log(f"Loaded {len(indicators)} indicators from 'wdi.csv'")

        # Filter indicators to remove those with specific suffixes
        console.log(f'Filtering indicators with suffixes: {", ".join([f"'{s}'" for s in SUFFIXES_TO_FILTER])}')
        indicators = self.filter_indicators(indicators)
        console.log(f'{len(indicators)} indicators remaining after filtering.')
        console.log(indicators)
        sample = indicators.to_dict(orient='records')

        # Determine which ids need paraphrasing
        missing_ids = self.paraphrase_file_complete(sample)
        if not missing_ids and not self.overwrite:
            console.log(
                f"[bold green]Paraphrases already present in '{self.output_file}'. Use --overwrite to re-generate.[/bold green]"
            )
            return
        elif not missing_ids and self.overwrite:
            console.log(f"[bold yellow]Overwriting all paraphrases in '{self.output_file}'.[/bold yellow]")
            to_paraphrase = sample
            existing_paraphrases = []
        else:
            if self.output_file.exists():
                with self.output_file.open('r') as f:
                    try:
                        existing_paraphrases = json.load(f)
                    except Exception:
                        existing_paraphrases = []
            else:
                existing_paraphrases = []
            to_paraphrase = [s for s in sample if s['id'] in missing_ids]

        console.log('[bold cyan]Paraphrasing with configuration...[/bold cyan]')
        console.log('[cyan]Model[/cyan]      ', f"'{self.model}'")
        console.log('[cyan]Output file[/cyan]', f"'{self.output_file}'")
        console.log(
            '[cyan]Indicators[/cyan] ',
            f'{len(sample)} [cyan]total[/cyan] ([green][bold]{len(existing_paraphrases)}[/bold] already paraphrased[/green], [bold][yellow]{len(to_paraphrase)}[/bold] to paraphrase[/yellow])',
        )

        all_paraphrases = [p for p in existing_paraphrases if p['id'] not in {s['id'] for s in to_paraphrase}]
        max_code_width = max(len(s['id']) for s in sample) if sample else 12

        with Progress(
            SpinnerColumn(),
            TextColumn('[progress.description]{task.description}'),
            BarColumn(),
            CountColumn(),
            '[progress.percentage]{task.percentage:>3.0f}%',
            TimeRemainingColumn(),
            console=console,
        ) as progress:
            task = progress.add_task('Paraphrasing indicators...', total=len(to_paraphrase))
            for s in to_paraphrase:
                padded_code = f'{s["id"]:<{max_code_width}}'
                short_name = (s['name'][:27] + '...') if len(s['name']) > 30 else s['name']
                padded_name = f'{short_name:<30}'
                progress.update(
                    task, description=f'[yellow]{padded_code}[/yellow] [bold]·[/bold] [dim][yellow]{padded_name}[/yellow][/dim]'
                )
                try:
                    model_paraphrases = self.paraphrase_indicator(s['name'], s.get('description'))
                    paraphrase_list = [p.strip() for p in model_paraphrases.split(';')]
                except Exception as e:
                    console.log(f'[red]Error paraphrasing {s["id"]}: {e}[/red]')
                    paraphrase_list = []
                out = {
                    'id': s['id'],
                    'name': s['name'],
                    'description': s.get('description'),
                    'paraphrase': paraphrase_list,
                }
                all_paraphrases.append(out)
                progress.advance(task)

        # Merge with any existing paraphrases for ids not paraphrased in this run
        all_paraphrases_dict = {p['id']: p for p in all_paraphrases}

        # Add/replace with new paraphrases
        for p in all_paraphrases:
            all_paraphrases_dict[p['id']] = p

        # Add any existing paraphrases for ids not paraphrased in this run
        for p in existing_paraphrases:
            if p['id'] not in all_paraphrases_dict:
                all_paraphrases_dict[p['id']] = p

        # Save all paraphrases sorted by id
        all_paraphrases_sorted = [all_paraphrases_dict[k] for k in sorted(all_paraphrases_dict.keys())]
        with self.output_file.open('w') as f:
            json.dump(all_paraphrases_sorted, f, indent=2)

        lengths = self.get_all_paraphrase_lengths(all_paraphrases_sorted)
        avg_len = sum(lengths) / len(lengths) if lengths else 0
        console.log(f'[bold green]Saved paraphrases to {self.output_file}[/bold green]')
        console.log(f'[bold cyan]Average paraphrase length: {avg_len:.2f} words[/bold cyan]')


class CountColumn(ProgressColumn):
    """Custom column to show completed/total count."""

    def render(self, task):
        return f'[yellow]{int(task.completed)}/{int(task.total)}[/yellow]'


def main():
    parser = argparse.ArgumentParser(description='Paraphrase World Bank indicator names using OpenAI.')
    parser.add_argument(
        '--output', type=str, default=None, help='Output filename for paraphrases (default: indicator_paraphrases.json)'
    )
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing paraphrase file if present')
    parser.add_argument('--model', type=str, default='gpt-4.1-mini', help='OpenAI model to use (default: gpt-4.1-mini)')
    parser.add_argument(
        '--num-paraphrases', type=int, default=3, help='Number of paraphrases to generate for each indicator (default: 3)'
    )
    args = parser.parse_args()

    runner = Paraphraser(
        output_file=args.output,
        model=args.model,
        overwrite=args.overwrite,
        num_paraphrases=args.num_paraphrases,
    )
    runner.run()


if __name__ == '__main__':
    main()
