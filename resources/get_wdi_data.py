import argparse
import logging
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Constants
YEAR_BEGIN = 2003
YEAR_END = 2023
DATA_PATH = Path('resources')
WDI_IND_DIR = DATA_PATH / 'wdi'
ISO_3166_PATH = DATA_PATH / 'iso_3166.csv'

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_country_codes(
    filepath: Path = ISO_3166_PATH,
) -> list:
    """Load ISO 3166-1 alpha-3 country codes from a CSV file."""
    iso_3166 = pd.read_csv(filepath)
    return iso_3166['country_code'].to_list()


def get_featured_indicators() -> None:
    """Scrape the list of featured indicators from the World Bank website and return their codes.

    Returns
    -------
    list
        A list of featured indicator codes.

    """
    url = 'https://data.worldbank.org/indicator'
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    featured_indicators = []
    for link in soup.find_all('a', href=True):
        href = link['href']
        if href.startswith('/indicator/') and href.count('/') == 2:
            indicator_code = href.split('/')[-1].split('?')[0]
            featured_indicators.append(indicator_code)

    return featured_indicators


def get_indicators(
    featured: bool = True,
    save: bool = True,
    data_dir: Path = DATA_PATH,
) -> dict:
    """Fetch all WDI indicators from the World Bank API.

    Parameters
    ----------
    featured : bool
        Whether to fetch only featured indicators.
    save : bool
        Whether to save the indicator data to a CSV file.
    data_dir : Path
        The path to save the indicator data.

    Returns
    -------
    dict
        A dictionary of indicator codes, names, and descriptions.

    """
    data_dir = Path(data_dir) if isinstance(data_dir, str) else data_dir

    logging.info('Fetching WDI indicators from the World Bank API.')

    # Initial request to get the total number of indicators
    url = 'https://api.worldbank.org/v2/source/2/indicator?format=json&per_page=1'
    response = requests.get(url)
    data = response.json()
    total_indicators = data[0]['total']

    # Request all indicators
    url = f'https://api.worldbank.org/v2/source/2/indicator?format=json&per_page={total_indicators}'
    response = requests.get(url)
    data = response.json()[1:][0]

    # Need a list[dict] of indicator codes, names, and descriptions
    indicators = [{'id': i['id'], 'name': i['name'], 'description': i['sourceNote']} for i in data]

    if featured:
        # Get the list of featured indicator codes
        featured_codes = get_featured_indicators()
        # Now filter the indicators to only include the featured ones
        indicators = [i for i in indicators if i['id'] in featured_codes]

    # # Save the indicator key to a CSV file
    # indicators = pd.DataFrame(indicators)
    # filename = 'wdi.csv' if featured else 'wdi.csv'

    # if save:
    #     indicators.to_csv(data_dir / filename, index=False)

    return indicators


def fetch_indicator_data(indicator, year_begin, year_end):
    """Fetch data for a specific indicator from the World Bank API."""
    params = {'format': 'json', 'date': f'{year_begin}:{year_end}', 'page': 1}
    url = f'https://api.worldbank.org/v2/country/all/indicator/{indicator}'

    response = requests.get(url, params=params)
    data = response.json()
    # Raise an error if the request was unsuccessful
    if response.status_code != 200 or len(data) < 2:
        logging.error(f'Indicator {indicator} not found: {data}')
        return None

    total_indicators = data[0]['total']

    params['per_page'] = total_indicators
    response = requests.get(url, params=params)
    data = response.json()[1:][0]

    return data


def save_indicator_data(indicator_data: list, country_codes: list, save_path: Path) -> None:
    """Save the indicator_data data to a CSV file."""
    df = pd.DataFrame(indicator_data)
    pivot = df.pivot_table(index='countryiso3code', columns='date', values='value')
    pivot = pivot[pivot.index.isin(country_codes)]
    pivot.index.name = 'country_code'
    pivot = pivot.sort_index()
    pivot.to_csv(save_path)


def main(
    featured: bool = True,
) -> None:
    """Fetch World Development Indicators data from the World Bank API.

    Parameters
    ----------
    featured : bool
        Whether to fetch only featured indicators.

    """
    if not DATA_PATH.exists():
        DATA_PATH.mkdir(parents=True)

    if not WDI_IND_DIR.exists():
        WDI_IND_DIR.mkdir(parents=True)

    indicators = get_indicators(featured=True)
    country_codes = get_country_codes()

    # Check which indicators have already been fetched
    existing_files = [f.stem for f in WDI_IND_DIR.iterdir() if f.is_file()]

    print(f'Processing data for {len(indicators)} remaining indicators.')
    pbar = tqdm(indicators, desc='Indicators processed')

    available_indicators = []

    # Fetch and save data for each indicator
    for i in pbar:
        pbar.set_description(f'Processing {i["id"]}')
        data = fetch_indicator_data(i['id'], YEAR_BEGIN, YEAR_END)
        if data:
            save_indicator_data(data, country_codes, WDI_IND_DIR / f'{i["id"]}.csv')
            available_indicators.append(i)

        # Sleep for 1 second to avoid hitting the API too hard
        time.sleep(0.5)

    # Save the list of available indicators to a CSV file
    indicators = pd.DataFrame(available_indicators)
    filename = 'wdi.csv'
    indicators.to_csv(DATA_PATH / filename, index=False)
    logging.info(f'Saved {len(available_indicators)} indicators to {DATA_PATH / filename}.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fetch World Development Indicators data from the World Bank API.')
    parser.add_argument('--featured', action='store_true', help='Fetch only featured indicators.')
    args = parser.parse_args()

    main(args.featured)
