from httpx import Response

from .exceptions import (
    AuthenticationError,
    ConflictError,
    CrossClientError,
    PermissionDeniedError,
    RequestValidationError,
    ResourceNotFoundError,
    ServerError,
    UnprocessableEntityError,
    ValidationError,
)

STATUS_ERROR_MAPPING: dict[int, type[CrossClientError]] = {
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: ResourceNotFoundError,
    409: ConflictError,
    422: UnprocessableEntityError,
    500: ServerError,
}
NAME_ERROR_MAPPING: dict[str, type[CrossClientError]] = {
    "ValidationError": ValidationError,
    "RequestValidationError": RequestValidationError,
}


def raise_from_response(response: Response) -> None:
    """Raise an appropriate CrossClientError based on the HTTP response.

    Args:
        response (Response): The HTTP response object.
    Raises:
        CrossClientError: An appropriate exception based on the response status code.
    """
    if 200 <= response.status_code < 400:
        return None

    status = response.status_code

    # 1. Parse details safely
    try:
        json_body = response.json()
    except Exception:
        json_body = {}

    # 2. Extract Standardized Fields
    # We expect: {"detail":
    #   {"message": "...",
    #   "exception_name": "...",
    #   "validation_errors": [...]}}
    # But 'detail' can also be a string in case of fastapi responses
    error_details = json_body.get("detail")

    # Initialize variables
    original_message = None
    exception_name = None
    validation_errors = None

    # Handle different 'detail' formats
    if isinstance(error_details, dict):
        # Case A: Our Custom Rich Error (Dict)
        original_message = error_details.get("message")
        exception_name = error_details.get("exception_name")
        validation_errors = error_details.get("validation_errors")
    elif isinstance(error_details, str):
        # Case B: Legacy/Simple Error (String)
        original_message = error_details
    else:
        # Case C: Standard FastAPI Validation Error (List of dicts)
        # We generally treat this as generic UnprocessableEntityError
        pass

    # 3. Construct a helpful log message
    message = f"HTTP {status} Error"
    if exception_name and original_message:
        message = f"{exception_name} ({status}): {original_message}"
    elif original_message:
        message = f"{status} Error: {original_message}"
    elif exception_name:
        message = f"{exception_name} ({status} Error)"

    # 4. Select the exception class
    exc_class = None

    # A: Mapping on the Exception Name
    if exception_name in NAME_ERROR_MAPPING:
        exc_class = NAME_ERROR_MAPPING[exception_name]
    # B. Selection on Status Code
    if not exc_class:
        exc_class = STATUS_ERROR_MAPPING.get(status)

    # C. Fallbacks
    if not exc_class:
        if 400 <= status < 500:
            exc_class = CrossClientError
        else:
            exc_class = ServerError

    # 5. Instantiate and Raise
    raise exc_class(
        message=message, validation_errors=validation_errors, status_code=status
    )
