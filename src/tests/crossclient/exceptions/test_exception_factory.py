from unittest.mock import Mock

import pytest
from httpx import Response

from crosscontract.crossclient.exceptions.exception_factory import raise_from_response
from crosscontract.crossclient.exceptions.exceptions import (
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


class TestRaiseFromResponse:
    """Tests for the raise_from_response function using class-based structure."""

    @pytest.fixture
    def mock_response(self):
        """Fixture to create a mock requests.Response."""
        response = Mock(spec=Response)
        # Default behavior: success
        response.status_code = 200
        response.json.return_value = {}
        return response

    def test_success_response_does_not_raise(self, mock_response):
        """Test that responses with 2xx status codes do not raise exceptions."""
        for status in [200, 201, 204, 299]:
            mock_response.status_code = status
            # Should not raise
            raise_from_response(mock_response)

    def test_custom_error_mapping_by_status_code(self, mock_response):
        """Test mapping errors based on status code when no specific name is
        provided."""
        error_cases = [
            (401, AuthenticationError),
            (403, PermissionDeniedError),
            (404, ResourceNotFoundError),
            (409, ConflictError),
            (422, UnprocessableEntityError),
            (500, ServerError),
        ]

        for status, exc_class in error_cases:
            mock_response.status_code = status
            mock_response.json.return_value = {
                "detail": {
                    "message": "Something went wrong",
                    "exception_name": "UnknownException",
                }
            }

            with pytest.raises(exc_class) as exc_info:
                raise_from_response(mock_response)

            # Verify the message includes the exception name from the payload if present
            assert "Something went wrong" in str(exc_info.value)

    def test_custom_error_mapping_by_exception_name(self, mock_response):
        """Test that exception_name in the payload takes precedence for mapped names."""
        mock_response.status_code = 400  # Generic 400
        mock_response.json.return_value = {
            "detail": {
                "message": "Validation failed",
                "exception_name": "ValidationError",
                "validation_errors": [{"field": "age", "message": "Must be positive"}],
            }
        }

        with pytest.raises(ValidationError) as exc_info:
            raise_from_response(mock_response)

        assert "Validation failed" in str(exc_info.value)
        assert exc_info.value.validation_errors == [
            {"field": "age", "message": "Must be positive"}
        ]

    def test_request_validation_error_mapping(self, mock_response):
        """Test mapping for RequestValidationError specifically."""
        mock_response.status_code = 422
        mock_response.json.return_value = {
            "detail": {
                "message": "Request invalid",
                "exception_name": "RequestValidationError",
            }
        }

        with pytest.raises(RequestValidationError):
            raise_from_response(mock_response)

    def test_legacy_error_string_format(self, mock_response):
        """Test handling of legacy/FastAPI default responses where detail is a
        string."""
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Not Found"}

        with pytest.raises(ResourceNotFoundError) as exc_info:
            raise_from_response(mock_response)

        # message logic: f"{status} Error: {original_message}"
        assert "404 Error: Not Found" in str(exc_info.value)

    def test_malformed_json_response(self, mock_response):
        """Test handling when response body is not valid JSON."""
        mock_response.status_code = 502
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with pytest.raises(ServerError) as exc_info:
            raise_from_response(mock_response)

        # Should likely default to generic message since parsing failed
        assert "HTTP 502 Error" in str(exc_info.value)

    def test_fallback_client_error(self, mock_response):
        """Test fallback to CrossClientError for unmapped 4xx errors."""
        mock_response.status_code = 418  # I'm a teapot
        mock_response.json.return_value = {}

        with pytest.raises(CrossClientError) as exc_info:
            raise_from_response(mock_response)

        assert "HTTP 418 Error" in str(exc_info.value)

    def test_fallback_server_error(self, mock_response):
        """Test fallback to ServerError for unmapped 5xx errors
        (or others outside 4xx)."""
        mock_response.status_code = 503
        mock_response.json.return_value = {}

        with pytest.raises(ServerError) as exc_info:
            raise_from_response(mock_response)

        assert "HTTP 503 Error" in str(exc_info.value)

    def test_detailed_validation_errors(self, mock_response):
        """Test that validation_errors are correctly extracted and passed to the
        exception."""
        mock_response.status_code = 422
        validation_payload = [
            {"field": "username", "message": "Too short"},
            {"field": "email", "message": "Invalid format"},
        ]
        mock_response.json.return_value = {
            "detail": {
                "message": "Validation Error",
                "exception_name": "UnprocessableEntityError",
                "validation_errors": validation_payload,
            }
        }

        # 422 maps to UnprocessableEntityError in STATUS_ERROR_MAPPING
        with pytest.raises(UnprocessableEntityError) as exc_info:
            raise_from_response(mock_response)

        assert exc_info.value.validation_errors == validation_payload

    def test_unknown_format_response(self, mock_response):
        """Test handling when response is JSON but doesn't have 'detail' field."""
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Something else"}

        with pytest.raises(CrossClientError):
            raise_from_response(mock_response)

    def test_exception_name_only(self, mock_response):
        """Test handling when response provides exception_name but no message."""
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "detail": {"exception_name": "SomeSpecificError"}
        }

        with pytest.raises(CrossClientError) as exc_info:
            raise_from_response(mock_response)

        # message logic: f"{exception_name} ({status} Error)"
        assert "SomeSpecificError (400 Error)" in str(exc_info.value)
