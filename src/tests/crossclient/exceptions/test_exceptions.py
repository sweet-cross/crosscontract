import pytest

from crosscontract.crossclient.exceptions import ValidationError


@pytest.fixture
def validation_error() -> ValidationError:
    """Fixture to provide a ValidationError instance."""
    errors = [
        {"field": "name", "error": "This field is required."},
        {"field": "age", "error": "Must be a positive integer."},
    ]
    return ValidationError(
        message="Validation failed",
        validation_errors=errors,
        status_code=422,
    )


class TestValidationError:
    def test_correct_message(self):
        """Test correct properties of ValidationError."""
        ve = ValidationError(validation_errors=None)
        assert ve.message == ve._default_message + " " + ve._message_note
        ve = ValidationError(
            message="Custom message", validation_errors=None, status_code=400
        )
        assert ve.message == "Custom message" + " " + ve._message_note
        assert ve.status_code == 400
        assert ve._error_list == []

    def test_to_list(self, validation_error: ValidationError):
        """Test to_list method of ValidationError."""
        error_list = validation_error.to_list()
        assert isinstance(error_list, list)
        assert len(error_list) == 2
        assert error_list[0]["field"] == "name"
        assert error_list[0]["error"] == "This field is required."
        assert error_list[1]["field"] == "age"
        assert error_list[1]["error"] == "Must be a positive integer."

    def test_to_pandas(self, validation_error: ValidationError):
        """Test to_pandas method of ValidationError."""
        df = validation_error.to_pandas()
        assert not df.empty
        assert df.shape[0] == 2
        assert "field" in df.columns
        assert "error" in df.columns
        assert df.iloc[0]["field"] == "name"
        assert df.iloc[0]["error"] == "This field is required."
        assert df.iloc[1]["field"] == "age"
        assert df.iloc[1]["error"] == "Must be a positive integer."

    def test_to_pandas_no_validation_errors(self):
        ve = ValidationError()
        assert not ve.to_pandas()

    def test_to_pandas_malformed_validation_errors(self):
        ve = ValidationError(validation_errors="not a list")
        assert not ve.to_pandas()
