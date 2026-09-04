import pytest

from crosscontract.contracts.schema.validation.checks.utils import (
    validate_existing_length_match,
)

# The checks that carry existing values delegate their model validator here.
# That each of them does so is covered alongside those checks.


class TestValidateExistingLengthMatch:
    def test_matching_width_passes(self):
        """One entry per column is what the comparison expects."""
        validate_existing_length_match(["id"], [("a",), ("b",)])

    def test_matching_composite_width_passes(self):
        """A composite key is satisfied by values of the same width."""
        validate_existing_length_match(["x", "y"], [("a", 1)])

    def test_no_existing_values_passes(self):
        """Nothing to compare is not a mismatch."""
        validate_existing_length_match(["id"], [])

    def test_too_wide_raises(self):
        """A value wider than the key would match nothing."""
        with pytest.raises(ValueError):
            validate_existing_length_match(["id"], [("a", 1)])

    def test_too_narrow_raises(self):
        """A value narrower than the key would match nothing either."""
        with pytest.raises(ValueError):
            validate_existing_length_match(["x", "y"], [("a",)])

    def test_one_bad_value_among_good_ones_raises(self):
        """Every value is measured, not just the first."""
        with pytest.raises(ValueError):
            validate_existing_length_match(["id"], [("a",), ("b", 1)])

    def test_error_names_the_expected_width_and_the_offending_values(self):
        """The message says how wide a value must be and which ones were not,
        so the caller can fix the input without guessing."""
        with pytest.raises(ValueError) as exc_info:
            validate_existing_length_match(["x", "y"], [("a",)])
        message = str(exc_info.value)
        assert "must have 2 entries" in message
        assert "('a',)" in message
