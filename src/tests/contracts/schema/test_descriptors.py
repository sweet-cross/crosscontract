import pytest
from pydantic import ValidationError

# Assuming your code is in a file named 'contract.py'
from crosscontract.contracts.schema.field_descriptors import (
    FieldDescriptors,
    Frequency,
    LocationFieldDescriptor,
    LocationType,
    TimeFieldDescriptor,
    ValueFieldDescriptor,
)


class TestFieldDescriptors:
    @pytest.fixture
    def sample_descriptors(self) -> FieldDescriptors:
        """Fixture to provide a standard set of valid descriptors."""
        return FieldDescriptors(
            root=[
                ValueFieldDescriptor(field="price_eur", unit="EUR"),
                TimeFieldDescriptor(field="timestamp_utc", frequency=Frequency.HOURLY),
                LocationFieldDescriptor(
                    field="grid_region", locationType=LocationType.REGION
                ),
            ]
        )

    def test_instantiate_valid_descriptors(self, sample_descriptors):
        """Test that we can create the container and it holds the correct types."""
        assert len(sample_descriptors) == 3

        # Verify the discriminator worked (correct classes instantiated)
        assert isinstance(sample_descriptors[0], ValueFieldDescriptor)
        assert isinstance(sample_descriptors[1], TimeFieldDescriptor)
        assert isinstance(sample_descriptors[2], LocationFieldDescriptor)

    def test_json_loading_discriminator(self):
        """
        Critical Test: Ensure Pydantic correctly picks the subclass
        based on the 'type' field in a raw dictionary (simulating JSON parsing).
        """
        raw_data = [
            {"type": "value", "field": "revenue", "unit": "USD"},
            {"type": "time", "field": "date", "frequency": "daily"},
        ]

        descriptors = FieldDescriptors.model_validate(raw_data)

        assert len(descriptors) == 2
        assert isinstance(descriptors[0], ValueFieldDescriptor)
        assert descriptors[0].unit == "USD"
        assert isinstance(descriptors[1], TimeFieldDescriptor)
        assert descriptors[1].frequency == Frequency.DAILY

    def test_access_methods(self, sample_descriptors):
        """Test dictionary-style access, .get(), and .names."""
        # 1. Test __getitem__ (string lookup)
        assert sample_descriptors["price_eur"].type == "value"

        # 2. Test __getitem__ (integer lookup)
        assert sample_descriptors[0].field == "price_eur"

        # 3. Test .get()
        assert sample_descriptors.get("grid_region").type == "location"
        assert sample_descriptors.get("non_existent") is None

        # 4. Test .names property
        assert set(sample_descriptors.names) == {
            "price_eur",
            "timestamp_utc",
            "grid_region",
        }

    def test_key_error_on_missing_field(self, sample_descriptors):
        """Test that dictionary access raises the correct KeyError."""
        with pytest.raises(
            KeyError, match='Field "missing_field" not found in field descriptors'
        ):
            _ = sample_descriptors["missing_field"]

    def test_validate_all_exist_success(self, sample_descriptors):
        """Test validation passes when all referenced fields exist in the schema
        list."""
        schema_fields = ["price_eur", "timestamp_utc", "grid_region", "other_field"]
        # Should not raise
        sample_descriptors.validate_all_exist(schema_fields)

    def test_validate_all_exist_failure(self, sample_descriptors):
        """Test validation raises ValueError when fields are missing."""
        # 'grid_region' is missing from this list
        incomplete_schema = ["price_eur", "timestamp_utc"]

        with pytest.raises(
            ValueError,
            match="Field 'grid_region' referenced in descriptor",
        ):
            sample_descriptors.validate_all_exist(incomplete_schema)

    def test_invalid_enum_value(self):
        """Test that invalid enum values raise Pydantic validation errors."""
        raw_data = [{"type": "time", "field": "bad_time", "frequency": "minutely"}]

        with pytest.raises(ValidationError) as exc:
            FieldDescriptors.model_validate(raw_data)

        # Check that it caught the enum error
        assert "Input should be 'yearly', 'monthly', 'daily' or 'hourly'" in str(
            exc.value
        )

    def test_missing_required_field(self):
        """Test failure when a required field (like 'frequency') is missing."""
        raw_data = [{"type": "time", "field": "bad_time"}]  # Missing frequency

        with pytest.raises(ValidationError) as exc:
            FieldDescriptors.model_validate(raw_data)

        assert "Field required" in str(exc.value)
        assert "frequency" in str(exc.value)

    def test_iterator(self, sample_descriptors):
        """Test that the object is iterable."""
        fields = [d.field for d in sample_descriptors]
        assert fields == ["price_eur", "timestamp_utc", "grid_region"]
