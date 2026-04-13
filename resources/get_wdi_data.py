import argparse
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import BarColumn, Progress, ProgressColumn, SpinnerColumn, TextColumn, TimeRemainingColumn

# Constants
YEAR_BEGIN = 2003
YEAR_END = 2023
DATA_PATH = Path('resources')
WDI_IND_DIR = DATA_PATH / 'wdi'
UN_M49_PATH = DATA_PATH / 'un_m49_cleaned.csv'

console = Console()


class CountColumn(ProgressColumn):
    """Custom column to show completed/total count."""

    def render(self, task):
        return f'[yellow]{int(task.completed)}/{int(task.total)}[/yellow]'


class WDIDataFetcher:
    def __init__(
        self,
        featured: bool = True,
        output: str = 'wdi.csv',
        year_start: int = YEAR_BEGIN,
        year_end: int = YEAR_END,
        overwrite: bool = False,
    ):
        self.featured = featured
        self.output = output
        self.year_start = year_start
        self.year_end = year_end
        self.overwrite = overwrite
        self.data_path = DATA_PATH
        self.wdi_ind_dir = WDI_IND_DIR
        self.un_m49_cleaned_path = UN_M49_PATH
        self.console = console

    def get_country_codes(
        self,
    ) -> list:
        """Load ISO 3166-1 alpha-3 country codes from a CSV file.

        Returns
        -------
        list
            List of ISO 3166-1 alpha-3 country codes.

        """
        un_m49_cleaned = pd.read_csv(UN_M49_PATH)

        return un_m49_cleaned['country_code'].to_list()

    def get_featured_indicators(
        self,
    ) -> list:
        """Scrape the list of featured indicators from the World Bank website and return their codes.

        Returns
        -------
        list
            List of featured indicator codes.

        """
        # Scrape the World Bank website to get featured indicators
        url = 'https://data.worldbank.org/indicator'
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')

        # Find all links to indicators and extract their codes
        featured_indicators = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith('/indicator/') and href.count('/') == 2:
                indicator_code = href.split('/')[-1].split('?')[0]
                featured_indicators.append(indicator_code)

        return featured_indicators

    def get_indicators(
        self,
    ) -> list:
        """Fetch all WDI indicators from the World Bank API.

        Parameters
        ----------
        featured : bool, optional
            If True, only return featured indicators, by default True

        Returns
        -------
        list
            List of dictionaries containing indicator IDs, names, and descriptions.

        """
        # Fetch the total number of indicators from the World Bank API
        url = 'https://api.worldbank.org/v2/source/2/indicator?format=json&per_page=1'
        response = requests.get(url)
        data = response.json()
        total_indicators = data[0]['total']

        # Second request to get all indicators
        url = f'https://api.worldbank.org/v2/source/2/indicator?format=json&per_page={total_indicators}'
        response = requests.get(url)
        data = response.json()[1:][0]
        indicators = [{'id': i['id'], 'name': i['name'], 'description': i['sourceNote']} for i in data]

        # Filter indicators based on the 'featured' flag
        if self.featured:
            featured_codes = self.get_featured_indicators()
            indicators = [i for i in indicators if i['id'] in featured_codes]

        return indicators

    def fetch_indicator_data(
        self,
        indicator: str,
        year_begin: int,
        year_end: int,
    ) -> list:
        """Fetch data for a specific indicator from the World Bank API.

        Parameters
        ----------
        indicator : str
            The indicator code to fetch data for.
        year_begin : int
            The start year for the data.
        year_end : int
            The end year for the data.

        Returns
        -------
        list
            List of dictionaries containing the indicator data for the specified years.

        """
        # Fetch data for the specified indicator and years
        params = {'format': 'json', 'date': f'{year_begin}:{year_end}', 'page': 1}
        url = f'https://api.worldbank.org/v2/country/all/indicator/{indicator}'
        response = requests.get(url, params=params)
        data = response.json()
        if response.status_code != 200 or len(data) < 2:
            self.console.log(f'[red]Indicator {indicator} not found or error: {data}[/red]')
            return None

        total_indicators = data[0]['total']
        params['per_page'] = total_indicators
        response = requests.get(url, params=params)
        data = response.json()[1:][0]

        return data

    def save_indicator_data(
        self,
        indicator_data: list,
        country_codes: list,
        save_path: Path,
    ) -> None:
        """Save the indicator_data data to a CSV file.

        Parameters
        ----------
        indicator_data : list
            List of dictionaries containing the indicator data.
        country_codes : list
            List of ISO 3166-1 alpha-3 country codes to filter the data.
        save_path : Path
            Path to save the CSV file.

        """
        df = pd.DataFrame(indicator_data)
        pivot = df.pivot_table(index='countryiso3code', columns='date', values='value')
        pivot = pivot[pivot.index.isin(country_codes)]
        pivot.index.name = 'country_code'
        pivot = pivot.sort_index()
        pivot.to_csv(save_path)

    def ensure_dirs(
        self,
    ) -> None:
        """Ensure that the necessary directories exist."""
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.wdi_ind_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
    ) -> None:
        """Run the WDI data fetching process."""
        self.console.rule('[bold blue]WDI Data Fetcher')
        # Ensure necessary directories exist
        self.ensure_dirs()

        # Get indicators and country codes
        indicators = self.get_indicators()
        country_codes = self.get_country_codes()
        n_indicators = len(indicators)

        # Check if the output directory already contains indicator files
        existing_files = {f.stem for f in self.wdi_ind_dir.iterdir() if f.is_file()}
        missing_indicators = [i for i in indicators if i['id'] not in existing_files]
        already_present = [i for i in indicators if i['id'] in existing_files]
        available_indicators = []

        output_csv_path = self.data_path / self.output

        if self.overwrite:
            self.console.log('[bold yellow]Overwrite enabled: re-fetching all indicators.[/bold yellow]')
            missing_indicators = indicators
            already_present = []
            # Do not delete any files, just overwrite as we fetch
            available_indicators = []
        elif output_csv_path.exists() and not missing_indicators:
            self.console.log(
                f"[bold green]All indicator data is already present in '{self.wdi_ind_dir}'. Use --overwrite to refresh.[/bold green]"
            )
            return

        if not missing_indicators:
            self.console.log(
                f"[bold green]All indicator data is already present in '{self.wdi_ind_dir}'. Use --overwrite to refresh.[/bold green]"
            )
            available_indicators = indicators
        else:
            max_code_width = max(len(i['id']) for i in missing_indicators) if missing_indicators else 12
            with Progress(
                SpinnerColumn(),
                TextColumn('[progress.description]{task.description}'),
                BarColumn(),
                CountColumn(),
                '[progress.percentage]{task.percentage:>3.0f}%',
                TimeRemainingColumn(),
                console=self.console,
            ) as progress:
                self.console.log('[bold cyan]Getting indicator data with configuration...[/bold cyan]')
                self.console.log(f'[cyan]Years[/cyan]         {self.year_start} - {self.year_end}')
                self.console.log(f'[cyan]Featured only[/cyan] {self.featured}')
                self.console.log(f"[cyan]Output file[/cyan]   '{self.output}'")
                self.console.log(
                    f'[cyan]Indicators[/cyan]    {n_indicators} total ([green][bold]{len(already_present)}[/bold] already present[/green], [bold][yellow]{len(missing_indicators)}[/bold] to fetch[/yellow])'
                )
                task = progress.add_task('Fetching missing indicators...', total=len(missing_indicators))
                available_indicators.extend(already_present)
                for i in missing_indicators:
                    padded_code = f'{i["id"]:<{max_code_width}}'
                    short_name = (i['name'][:27] + '...') if len(i['name']) > 30 else i['name']
                    padded_name = f'{short_name:<30}'
                    progress.update(
                        task,
                        description=f'[yellow]{padded_code}[/yellow] [bold]·[/bold] [dim][yellow]{padded_name}[/yellow][/dim]',
                    )
                    data = self.fetch_indicator_data(i['id'], self.year_start, self.year_end)
                    if data:
                        self.save_indicator_data(data, country_codes, self.wdi_ind_dir / f'{i["id"]}.csv')
                        available_indicators.append(i)
                    time.sleep(0.1)
                    progress.advance(task)

        indicators_df = pd.DataFrame(available_indicators)
        indicators_df.to_csv(output_csv_path, index=False)
        self.console.log(f'[green]Saved indicator summary to {output_csv_path}.[/green]')


def main():
    parser = argparse.ArgumentParser(description='Fetch World Development Indicators data from the World Bank API.')
    parser.add_argument('--featured', action='store_true', help='Fetch only featured indicators.')
    parser.add_argument('--output', type=str, default='wdi.csv', help='Output CSV filename (default: wdi.csv)')
    parser.add_argument('--year-start', type=int, default=2003, help='Start year (default: 2003)')
    parser.add_argument('--year-end', type=int, default=2023, help='End year (default: 2023)')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing output file if present')
    args = parser.parse_args()

    fetcher = WDIDataFetcher(
        featured=args.featured,
        output=args.output,
        year_start=args.year_start,
        year_end=args.year_end,
        overwrite=args.overwrite,
    )
    fetcher.run()


if __name__ == '__main__':
    main()
