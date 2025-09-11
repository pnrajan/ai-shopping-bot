"""Custom Exception Classes for Inflection Curator.

This module defines a set of custom exception classes used throughout the
Inflection Curator application. These exceptions provide a structured way to
handle errors and distinguish between different types of issues, such as
planning failures, persona errors, or provider issues.

Using custom exceptions allows for more granular error handling and makes
debugging easier by providing more context about what went wrong.

Example:
    >>> from inflection_curator.core.exceptions import PlanningError
    >>> try:
    ...     raise PlanningError("Failed to generate a valid plan.", details={"confidence": 0.2})
    ... except PlanningError as e:
    ...     print(e)
    Failed to generate a valid plan. (Details: {'confidence': 0.2})
"""

from typing import Any, Dict, Optional


class CuratorError(Exception):
    """Base exception class for all Inflection Curator errors.

    This is the base class for all custom exceptions in the application. It
    provides a common structure for error messages and optional details.

    Attributes:
        message (str): The error message.
        details (Dict[str, Any]): A dictionary containing additional details
            about the error.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initializes the CuratorError.

        Args:
            message: The error message.
            details: A dictionary containing additional details about the error.
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Returns the string representation of the error."""
        if self.details:
            return f"{self.message} (Details: {self.details})"
        return self.message


class PersonaError(CuratorError):
    """Exception raised for errors related to personas.

    This exception is raised when there is an issue with loading, configuring,
    or using a persona.
    """

    pass


class PlanningError(CuratorError):
    """Exception raised for errors during the planning phase.

    This exception is raised when the planner fails to generate a valid
    execution plan.
    """

    pass


class ExecutionError(CuratorError):
    """Exception raised for errors during tool execution.

    This exception is raised when a tool fails to execute properly.
    """

    pass


class ValidationError(CuratorError):
    """Exception raised for input validation errors.

    This exception is raised when the input to a function or tool is invalid.
    """

    pass


class ProviderError(CuratorError):
    """Exception raised for errors related to product providers.

    This exception is raised when there is an issue with a product provider,
    such as an API error or a connection failure.
    """

    pass


class ConfigurationError(CuratorError):
    """Exception raised for configuration-related errors.

    This exception is raised when there is an issue with the application's
    configuration.
    """

    pass
