"""Library of tools to be provided to the model and provide the basis for solutions.

Currently unused in favour of existing/simpler approach in tools.py, but kept for future reference.
"""

from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from frankenstein.exceptions import (
    InvalidCountryCodeError,
    InvalidCountryNameError,
    InvalidIndicatorCodeError,
    InvalidIndicatorNameError,
    InvalidRegionNameError,
)


class Think(BaseModel):
    """Think aloud about the actions required to solve the problem."""

    thought: str

    def forward(self):
        """Return the thought."""
        return self.thought


class Add(BaseModel):
    """Add a list of numbers."""

    values: list[str]

    def forward(self):
        """Return the sum of the values."""
        return sum([float(value) for value in self.values])


class Subtract(BaseModel):
    """Subtract value_b from value_a."""

    value_a: str
    value_b: str

    def forward(self):
        """Return the difference of the values."""
        return float(self.value_a) - float(self.value_b)


class GreaterThan(BaseModel):
    """Check if value_a is greater than value_b."""

    value_a: str
    value_b: str

    def forward(self):
        """Return True if value_a is greater than value_b, else False."""
        return float(self.value_a) > float(self.value_b)


class LessThan(BaseModel):
    """Check if value_a is less than value_b."""

    value_a: str
    value_b: str

    def forward(self):
        """Return True if value_a is less than value_b, else False."""
        return float(self.value_a) < float(self.value_b)


class Multiply(BaseModel):
    """Multiply a list of numbers."""

    values: list[str]

    def forward(self):
        """Return the product of the values."""
        result = 1
        for value in self.values:
            result *= float(value)
        return result


class Divide(BaseModel):
    """Divide value_a by value_b."""

    value_a: str
    value_b: str

    def forward(self):
        """Return the quotient of the values."""
        if float(self.value_b) == 0:
            raise ValueError('Division by zero is not allowed.')
        return float(self.value_a) / float(self.value_b)


class Mean(BaseModel):
    """Calculate the mean of a list of numbers."""

    values: list[str]

    def forward(self):
        """Return the mean of the values."""
        return sum([float(value) for value in self.values]) / len(self.values)


class GetCountryCodeFromName(BaseModel):
    """Get the country code for a given country name."""

    country_name: str

    def forward(self):
        data = pd.read_csv(Path('resources', 'iso_3166.csv'))
        try:
            return data[data['country_name'] == self.country_name]['country_code'].to_list()[0]
        except IndexError as e:
            raise InvalidCountryNameError(self.country_name) from e


class GetIndicatorCodeFromName(BaseModel):
    """Get the indicator code for a given indicator name."""

    indicator_name: str

    def forward(self):
        data = pd.read_csv(Path('resources', 'wdi.csv'))
        try:
            return data[data['name'] == self.indicator_name.strip()]['id'].to_list()[0]
        except IndexError as e:
            raise InvalidIndicatorNameError(self.indicator_name) from e


class GetMembership(BaseModel):
    """Get the country codes for a given region name."""

    region: str

    def forward(self):
        data = pd.read_csv(Path('resources', 'iso_3166.csv'))
        try:
            return data[data['region'] == self.region]['country_code'].to_list()
        except IndexError as e:
            raise InvalidRegionNameError(self.region) from e


class RetrieveValue(BaseModel):
    """Retrieve the value for a given country code, indicator code, and year."""

    country_code: str
    indicator_code: str
    year: str

    def forward(self):
        # Check country code is valid
        data = pd.read_csv(Path('resources', 'iso_3166.csv'))
        if self.country_code not in data['country_code'].tolist():
            raise InvalidCountryCodeError(self.country_code)

        try:
            data = pd.read_csv(
                Path('resources', 'wdi', f'{self.indicator_code}.csv'),
                index_col='country_code',
            )
        except FileNotFoundError as e:
            raise InvalidIndicatorCodeError(self.indicator_code) from e

        try:
            value = data.loc[self.country_code, self.year]
        except KeyError:
            return None

        if pd.isna(value):
            return None

        return value


class FinalAnswer(BaseModel):
    """Return the final answer."""

    answer: str

    def forward(self):
        """Return the final answer."""
        return self.answer


class ToolCalls(BaseModel):
    tool_calls: list[
        Think | Add
        # | Subtract
        # | GreaterThan
        # | LessThan
        # | Multiply
        # | Divide
        # | GetCountryCodeFromName
        # | GetIndicatorCodeFromName
        # | GetMembership
        # | RetrieveValue
        # | FinalAnswer
    ]


if __name__ == '__main__':
    # Example usage
    tool = GetCountryCodeFromName(country_name='Senegal')
    print(tool.forward())  # Output: SEN

    print(ToolCalls.model_json_schema())
