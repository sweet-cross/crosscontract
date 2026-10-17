from collections.abc import Hashable
from typing import Any

import pandas as pd


class CrossClientError(Exception):
    """Base class for all client exceptions."""

    _default_message: str = "An error occurred in the CrossClient."

    def __init__(
        self,
        message: str | None = None,
        validation_errors: list[dict[Hashable, Any]] | None = None,
        status_code: int | None = None,
    ):
        self.message = message or self._default_message
        self.validation_errors = validation_errors or []
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(CrossClientError):
    """422: The data sent was invalid."""

    _default_message: str = "The data sent was invalid."
    _message_note: str = (
        "To get detailed error information, catch the ValidationError "
        "and use its .to_list() or .to_pandas() methods."
    )

    def __init__(
        self,
        message: str | None = None,
        validation_errors: list[dict[Hashable, Any]] | None = None,
        status_code: int | None = None,
    ):
        """Initialize the ValidationError with detailed error information.

        Args:
            message (str | None): Custom error message.
            validation_errors (list[dict[str, Any]] | None): List of validation error
                details.
            status_code (int | None): HTTP status code associated with the error.
        """
        my_message = (message or self._default_message) + " " + self._message_note
        # Ensure we have a list for the error logic, even if None passed
        self._error_list = validation_errors or []
        super().__init__(my_message, validation_errors, status_code)

    def to_list(self) -> list[dict[Hashable, Any]]:
        """Return the validation errors as a list of dictionaries.

        Returns:
            list[dict[Hashable, Any]]: List of validation error details.
        """
        return self._error_list

    def to_pandas(self) -> pd.DataFrame | None:
        """
        Return the validation errors as a pandas DataFrame.
        Reconstructs the DataFrame from the standard dictionary list.

        Returns:
            pd.DataFrame | None: DataFrame of validation errors, or None if
                not possible.
        """
        if not self._error_list:
            return None

        try:
            return pd.DataFrame(self._error_list)
        except Exception:
            # Fallback if the data structure doesn't match what DataFrame expects
            return None


class RequestValidationError(ValidationError):
    _default_message: str = "The request data sent was invalid."


class UnprocessableEntityError(CrossClientError):
    _default_message = "Unprocessable entity."


class AuthenticationError(CrossClientError):
    _default_message = "Authentication failed."


class PermissionDeniedError(CrossClientError):
    _default_message = "Permission denied."


class ResourceNotFoundError(CrossClientError):
    _default_message = "The requested resource was not found."


class ServerError(CrossClientError):
    _default_message = "The server encountered an internal error."


class ConflictError(CrossClientError):
    _default_message = "Conflict occurred with the current state of the resource."
