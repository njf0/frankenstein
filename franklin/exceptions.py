class InvalidIndicatorName(Exception):
    """Exception raised when an invalid indicator name is used."""

    def __init__(self, indicator_name: str):
        super().__init__(
            f"Error: indicator name '{indicator_name}' is not valid. Ensure you have used the correct indicator name from the question."
        )


class InvalidIndicatorCode(Exception):
    """Exception raised when an invalid indicator code is used."""

    def __init__(self, indicator_code: str):
        super().__init__(
            f"Error: indicator code '{indicator_code}' is not valid. Ensure you have used the 'get_indicator_code_from_name' function to get the code from the indicator name."
        )


class InvalidCountryName(Exception):
    """Exception raised when an invalid country name is used."""

    def __init__(self, country_name: str):
        super().__init__(
            f"Error: country name '{country_name}' is not valid. Double-check the country name in the question and ensure it is spelled correctly."
        )


class InvalidRegionName(Exception):
    """Exception raised when an invalid region name is used."""

    def __init__(self, region_name: str):
        super().__init__(
            f"Error: region name '{region_name}' is not valid. Ensure you have used the correct region name from the question."
        )


class InvalidCountryCode(Exception):
    """Exception raised when an invalid country code is used."""

    def __init__(self, country_code: str):
        super().__init__(
            f"Error: country code '{country_code}' is not valid. Ensure you have used the 'get_country_code_from_name' function to get the code from the country name."
        )


class NoDataAvailable(Exception):
    """Exception raised when no data is available for a given indicator and country."""

    def __init__(self, arguments: dict):
        super().__init__(
            f"Warning: your function call was correct, but no data is available for country code '{arguments['country_code']}' for indicator code '{arguments['indicator_code']}' in year '{arguments['year']}'."
        )
