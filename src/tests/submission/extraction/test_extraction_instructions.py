import pytest

from crosscontract.submission.extraction import ExtractionInstructions, Target
from crosscontract.transformations import DropColumns


class TestExtractionInstructions:
    def test_valid(self):
        """Test the creation of an ExtractionInstructions instance with valid data."""
        instructions = ExtractionInstructions(
            routing_column="variable",
            transformation_profiles={
                "profile1": [DropColumns(columns=["col1", "col2"])],
            },
            targets=[
                Target(
                    filters={"variable": "var1"},
                    contract="contract1",
                    transformation_profile="profile1",
                    transformations=[DropColumns(columns=["col3"])],
                ),
                Target(
                    filters={"variable": "var2"},
                    contract="contract2",
                ),
            ],
        )
        assert instructions.routing_column == "variable"
        assert len(instructions.transformation_profiles) == 1
        assert len(instructions.targets) == 2

    def test_filter_created(self):
        """Test that the filters are correctly created in the Target instances."""
        data = {
            "routing_column": "variable",
            "targets": [
                {
                    "filters": "var1",
                    "contract": "contract1",
                }
            ],
        }
        instructions = ExtractionInstructions.model_validate(data)
        my_target = instructions.targets[0]
        assert isinstance(my_target.filters, dict)
        assert my_target.filters == {"variable": "var1"}

    def test_filter_raises_validation_error_no_routing_column(self):
        """Test that a ValidationError is raised when filters are provided but
        routing_column is missing."""
        data = {
            "targets": [
                {
                    "filters": "Sas",  # Invalid type
                    "contract": "contract1",
                }
            ],
        }
        with pytest.raises(ValueError, match="routing_column"):
            ExtractionInstructions.model_validate(data)

    def test_non_unique_contract_raises(self):
        """Test that a ValueError is raised when duplicate contracts are present."""
        data = {
            "routing_column": "variable",
            "targets": [
                {
                    "filters": {"variable": "var1"},
                    "contract": "contract1",
                },
                {
                    "filters": {"variable": "var2"},
                    "contract": "contract1",  # Duplicate contract
                },
            ],
        }
        with pytest.raises(
            ValueError, match="Duplicate contracts found in targets: contract1"
        ):
            ExtractionInstructions.model_validate(data)

    def test_undefined_transformation_profile_raises(self):
        """Test that a ValueError is raised when a target references an undefined
        transformation profile.
        """
        data = {
            "routing_column": "variable",
            "transformation_profiles": {
                "profile1": [DropColumns(columns=["col1", "col2"])],
            },
            "targets": [
                {
                    "filters": {"variable": "var1"},
                    "contract": "contract1",
                    "transformation_profile": "undefined_profile",  # Undefined profile
                }
            ],
        }
        with pytest.raises(
            ValueError,
            match="Undefined transformation profiles referenced in targets: "
            "undefined_profile",
        ):
            ExtractionInstructions.model_validate(data)
