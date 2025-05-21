"""Exceptions used for Franklin actions with messages to guide the model in correcting errors."""


class InvalidIndicatorNameError(Exception):
    """Exception raised when an invalid indicator name is used."""

    def __init__(self, indicator_name: str):
        """Initialize the exception with a message.

        Parameters
        ----------
        indicator_name : str
            The invalid indicator name that caused the error.

        """
        super().__init__(
            f"Error: indicator name '{indicator_name}' is not valid. Ensure you have used the correct indicator name from the question."
        )


class InvalidIndicatorCodeError(Exception):
    """Exception raised when an invalid indicator code is used."""

    def __init__(self, indicator_code: str):
        """Initialize the exception with a message.

        Parameters
        ----------
        indicator_code : str
            The invalid indicator code that caused the error.

        """
        super().__init__(
            f"Error: indicator code '{indicator_code}' is not valid. Ensure you have used the 'get_indicator_code_from_name' function to get the code from the indicator name."
        )


class InvalidCountryNameError(Exception):
    """Exception raised when an invalid country name is used."""

    def __init__(self, country_name: str):
        """Initialize the exception with a message.

        Parameters
        ----------
        country_name : str
            The invalid country name that caused the error.

        """
        super().__init__(
            f"Error: country name '{country_name}' is not valid. Double-check the country name in the question and ensure it is spelled correctly."
        )


class InvalidRegionNameError(Exception):
    """Exception raised when an invalid region name is used."""

    def __init__(self, region_name: str):
        """Initialize the exception with a message.

        Parameters
        ----------
        region_name : str
            The invalid region name that caused the error.

        """
        super().__init__(
            f"Error: region name '{region_name}' is not valid. Ensure you have used the correct region name from the question."
        )


class InvalidCountryCodeError(Exception):
    """Exception raised when an invalid country code is used."""

    def __init__(self, country_code: str):
        """Initialize the exception with a message.

        Parameters
        ----------
        country_code : str
            The invalid country code that caused the error.

        """
        super().__init__(
            f"Error: country code '{country_code}' is not valid. Ensure you have used the 'get_country_code_from_name' function to get the code from the country name."
        )


class NoDataAvailableError(Exception):
    """Exception raised when no data is available for a given indicator and country."""

    def __init__(self, arguments: dict):
        """Initialize the exception with a message.

        Parameters
        ----------
        arguments : dict
            The arguments used in the function call that caused the error.

        """
        super().__init__(
            f"Warning: your function call was correct, but no data is available for country code '{arguments['country_code']}' for indicator code '{arguments['indicator_code']}' in year '{arguments['year']}'."
        )
