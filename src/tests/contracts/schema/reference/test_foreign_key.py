import pandera.pandas as pa
import pytest

from crosscontract.contracts.schema.reference.foreign_key import ForeignKey, ForeignKeys


class TestForeignKey:
    """Test class for single ForeignKey object."""

    def test_foreign_key_singleton_given(self):
        """Test that ForeignKey fields are set correctly."""
        fk = ForeignKey.model_validate(
            {"fields": "id", "reference": {"resource": "test", "fields": "ref_id"}}
        )
        assert fk.fields == ["id"]
        assert fk.reference.resource == "test"
        assert fk.reference.fields == ["ref_id"]

    def test_foreign_key_multiple_fields(self):
        """Test that ForeignKey with multiple fields are set correctly."""
        fk = ForeignKey.model_validate(
            {
                "fields": ["id1", "id2"],
                "reference": {"resource": "test", "fields": ["ref_id1", "ref_id2"]},
            }
        )
        assert fk.fields == ["id1", "id2"]
        assert fk.reference.resource == "test"
        assert fk.reference.fields == ["ref_id1", "ref_id2"]

    def test_foreign_key_field_length_mismatch(self):
        """Test that ForeignKey raises ValueError on field length mismatch."""
        with pytest.raises(ValueError, match="Foreign key length mismatch"):
            ForeignKey.model_validate(
                {
                    "fields": ["id1", "id2"],
                    "reference": {"resource": "test", "fields": ["ref_id1"]},
                }
            )

    def test_validate_fields_success(self):
        """Test that validate_fields passes when all fields exist."""
        fk = ForeignKey.model_validate(
            {
                "fields": ["id1", "id2"],
                "reference": {"resource": "test", "fields": ["ref_id1", "ref_id2"]},
            }
        )
        # Should not raise an exception
        fk.validate_fields(["id1", "id2", "other_field"])

    def test_validate_fields_failure(self):
        """Test that validate_fields raises ValueError when fields are missing."""
        fk = ForeignKey.model_validate(
            {
                "fields": ["id1", "id2"],
                "reference": {"resource": "test", "fields": ["ref_id1", "ref_id2"]},
            }
        )
        with pytest.raises(ValueError, match="Foreign key fields") as execinfo:
            fk.validate_fields(["id1", "other_field"])
        assert "['id2']" in str(execinfo.value)

    def test_validate_referenced_fields_success(self):
        """Test that validate_referenced_fields passes when all referenced
        fields exist."""
        fk = ForeignKey.model_validate(
            {
                "fields": ["id1", "id2"],
                "reference": {"resource": "test", "fields": ["ref_id1", "ref_id2"]},
            }
        )
        # Should not raise an exception
        fk.validate_referenced_fields(["ref_id1", "ref_id2", "other_field"])

    def test_validate_referenced_fields_failure(self):
        """Test that validate_referenced_fields raises ValueError when
        referenced fields are missing."""
        fk = ForeignKey.model_validate(
            {
                "fields": ["id1", "id2"],
                "reference": {"resource": "test", "fields": ["ref_id1", "ref_id2"]},
            }
        )
        with pytest.raises(ValueError, match="Referenced fields") as execinfo:
            fk.validate_referenced_fields(["ref_id1", "other_field"])
        assert "['ref_id2']" in str(execinfo.value)

    def test_foreign_keys_iteration(self):
        """Test iteration over ForeignKeys."""
        fks = ForeignKeys.model_validate(
            [
                {
                    "fields": ["user_id"],
                    "reference": {"resource": "user_contract", "fields": ["id"]},
                },
                {
                    "fields": ["order_id"],
                    "reference": {"resource": "order_contract", "fields": ["id"]},
                },
            ]
        )
        for fk in fks:
            assert isinstance(fk, ForeignKey)
            assert fk.fields in (["user_id"], ["order_id"])


class TestForeignKeys:
    """Test class for ForeignKeys collection."""

    def test_foreign_keys_iteration(self):
        """Test iteration over ForeignKeys."""
        fks = ForeignKeys.model_validate(
            [
                {
                    "fields": ["user_id"],
                    "reference": {"resource": "user_contract", "fields": ["id"]},
                },
                {
                    "fields": ["order_id"],
                    "reference": {"resource": "order_contract", "fields": ["id"]},
                },
            ]
        )
        for fk in fks:
            assert isinstance(fk, ForeignKey)
            assert fk.fields in (["user_id"], ["order_id"])

    def get_checks_self_reference(self):
        """Test getting pandera checks from ForeignKeys collection."""
        fks = ForeignKeys.model_validate(
            [
                {
                    "fields": ["manager_id"],
                    "reference": {"resource": None, "fields": ["emp_id"]},
                },
                {
                    "fields": ["mentor_id"],
                    "reference": {"resource": None, "fields": ["emp_id"]},
                },
            ]
        )

        # Create checks
        checks = fks.get_pandera_checks()

        assert len(checks) == 2
        for check in checks:
            assert isinstance(check, pa.Check)

    def get_checks_self_reference_with_values(self):
        """Test getting pandera checks from ForeignKeys collection with
        static values."""
        fks = ForeignKeys.model_validate(
            [
                {
                    "fields": ["manager_id"],
                    "reference": {"resource": None, "fields": ["emp_id"]},
                },
                {
                    "fields": ["mentor_id"],
                    "reference": {"resource": None, "fields": ["emp_id"]},
                },
            ]
        )

        # Static valid values for both FKs
        valid_values = {
            ("manager_id",): {(1,), (2,)},
            ("mentor_id",): {(3,), (4,)},
        }

        # Create checks
        checks = fks.get_pandera_checks(foreign_key_values=valid_values)

        assert len(checks) == 2
        for check in checks:
            assert isinstance(check, pa.Check)

    def get_checks_external_reference_with_values(self):
        """Test getting pandera checks from ForeignKeys collection with
        static values."""
        fks = ForeignKeys.model_validate(
            [
                {
                    "fields": ["manager_id"],
                    "reference": {"resource": "external_db", "fields": ["emp_id"]},
                },
                {
                    "fields": ["mentor_id"],
                    "reference": {"resource": "external_db", "fields": ["emp_id"]},
                },
            ]
        )

        # Static valid values for both FKs
        valid_values = {
            ("manager_id",): {(1,), (2,)},
            ("mentor_id",): {(3,), (4,)},
        }

        # Create checks
        checks = fks.get_pandera_checks(foreign_key_values=valid_values)

        assert len(checks) == 2
        for check in checks:
            assert isinstance(check, pa.Check)

    def get_checks_external_reference_warning(self):
        """Test getting pandera checks from ForeignKeys collection with
        static values."""
        fks = ForeignKeys.model_validate(
            [
                {
                    "fields": ["manager_id"],
                    "reference": {"resource": "external_db", "fields": ["emp_id"]},
                },
                {
                    "fields": ["mentor_id"],
                    "reference": {"resource": "external_db", "fields": ["emp_id"]},
                },
            ]
        )

        with pytest.warns(
            UserWarning,
            match=r"Foreign Key \['emp_id'\] reference field in external,",
        ):
            fks.get_pandera_checks()
