from typing import Literal

import pandas as pd
import pandera.pandas as pa
import pytest
from pydantic import ValidationError

from crosscontract.contracts.schema.validation.checks import BaseCheck

# BaseCheck is abstract, so its behaviour is exercised through the minimal
# concrete check below. The concrete checks themselves are covered in
# test_base_checks.py.


class StubCheck(BaseCheck):
    """Minimal concrete check: a row passes when its 'ok' column is true."""

    name: Literal["stub"] = "stub"

    def __call__(self, df: pd.DataFrame) -> pd.Series:
        return df["ok"].astype(bool)


class TestBaseCheck:
    def test_cannot_be_instantiated_without_a_predicate(self):
        """The base class is abstract — a check without a `__call__` is not a
        check."""
        with pytest.raises(TypeError):
            BaseCheck(name="stub", label="stub")  # type: ignore[abstract]

    def test_ignore_na_defaults_to_true(self):
        """Checks follow the pandera default unless they handle nulls
        themselves."""
        assert StubCheck(label="stub").ignore_na is True

    def test_name_cannot_be_overridden(self):
        """`name` identifies the check class and serves as discriminator, so an
        instance may not carry a different one."""
        with pytest.raises(ValidationError):
            StubCheck(name="something_else", label="stub")  # type: ignore[arg-type]

    def test_unknown_fields_are_rejected(self):
        """The model forbids extras, so a misspelled argument fails loudly
        instead of being silently dropped."""
        with pytest.raises(ValidationError):
            StubCheck(label="stub", ignore_nulls=True)  # type: ignore[call-arg]

    def test_failure_message_names_the_check_and_the_label(self):
        """The default message identifies both the rule and what it means
        here."""
        message = StubCheck(label="my label").failure_message()
        assert "stub" in message
        assert "my label" in message


class TestToPandera:
    @pytest.fixture
    def check(self) -> StubCheck:
        return StubCheck(label="stub", ignore_na=False)

    def test_returns_one_check_per_rule(self, check: StubCheck):
        """A plain check produces a single pandera check; composites override
        this to produce one per sub-rule."""
        assert len(check.to_pandera()) == 1

    def test_carries_the_failure_message(self, check: StubCheck):
        """The failure message is what identifies the check in a report."""
        assert check.to_pandera()[0].error == check.failure_message()

    def test_carries_ignore_na(self, check: StubCheck):
        """A check that inspects nulls itself must stop pandera dropping the
        null rows first."""
        assert check.to_pandera()[0].ignore_na is False

    def test_is_named_after_the_check_class(self, check: StubCheck):
        """No name is passed, so pandera falls back to the class name and a
        report says which rule broke."""
        assert check.to_pandera()[0].name == "StubCheck"

    def test_passing_frame_validates(self, check: StubCheck):
        """The check instance is accepted as a pandera check callable and lets a
        conforming frame through."""
        schema = pa.DataFrameSchema(
            columns={"ok": pa.Column(bool)}, checks=check.to_pandera()
        )
        df = pd.DataFrame({"ok": [True, True]})
        pd.testing.assert_frame_equal(schema.validate(df), df)

    def test_failing_frame_raises(self, check: StubCheck):
        """A row the predicate rejects surfaces as a pandera schema error."""
        schema = pa.DataFrameSchema(
            columns={"ok": pa.Column(bool)}, checks=check.to_pandera()
        )
        with pytest.raises(pa.errors.SchemaError):
            schema.validate(pd.DataFrame({"ok": [True, False]}))
