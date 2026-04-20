import pytest

from crosscontract.contracts import BaseContract, CrossContract


class FakeResolver:
    """In-memory resolver for testing."""

    def __init__(self, *contracts: BaseContract):
        self._by_name = {c.name: c for c in contracts}

    def resolve(self, name: str) -> BaseContract | None:
        return self._by_name.get(name)


def _base_contract(name: str, foreign_keys: list | None = None) -> BaseContract:
    """Build a BaseContract with the given name and optional foreign keys."""
    return BaseContract.model_validate(
        {
            "name": name,
            "tableschema": {
                "primaryKey": ["id"],
                "foreignKeys": foreign_keys or [],
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "value", "type": "number"},
                ],
            },
        }
    )


def _dimension_contract(name: str) -> CrossContract:
    """Build a CrossContract with a FlexibleDimension tableschema."""
    return CrossContract.model_validate(
        {
            "name": name,
            "title": name,
            "description": f"{name} dimension",
            "contract_type": "FlexibleDimension",
            "tableschema": {
                "primaryKey": ["id"],
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "label", "type": "string"},
                    {"name": "description", "type": "string"},
                ],
            },
        }
    )


def _general_cross_contract(name: str) -> CrossContract:
    """Build a non-dimension CrossContract for negative star-schema tests."""
    return CrossContract.model_validate(
        {
            "name": name,
            "title": name,
            "description": f"{name} general",
            "contract_type": "General",
            "tableschema": {
                "primaryKey": ["id"],
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "value", "type": "number"},
                ],
            },
        }
    )


FK_TO_OTHER = [
    {
        "fields": ["id"],
        "reference": {"resource": "other_contract", "fields": ["id"]},
    }
]


class TestBaseContractReferences:
    def test_no_foreign_keys_passes(self):
        """A contract without foreign keys validates trivially."""
        contract = _base_contract("fact")
        contract.validate_references(FakeResolver())

    def test_valid_external_reference_passes(self):
        """An external reference that resolves with matching fields passes."""
        fact = _base_contract("fact", FK_TO_OTHER)
        other = _base_contract("other_contract")
        fact.validate_references(FakeResolver(other))

    def test_unknown_reference_fails(self):
        """An external reference to a non-existent contract is reported."""
        fact = _base_contract("fact", FK_TO_OTHER)
        with pytest.raises(ValueError, match="unknown contract 'other_contract'"):
            fact.validate_references(FakeResolver())

    def test_mismatched_referenced_field_fails(self):
        """A reference pointing to a field that doesn't exist in the target fails."""
        fact = _base_contract(
            "fact",
            [
                {
                    "fields": ["id"],
                    "reference": {
                        "resource": "other_contract",
                        "fields": ["nonexistent_field"],
                    },
                }
            ],
        )
        other = _base_contract("other_contract")
        with pytest.raises(ValueError, match="Foreign key to 'other_contract'"):
            fact.validate_references(FakeResolver(other))

    def test_star_schema_opt_in_rejects_non_dimension(self):
        """With enforce_star_schema=True, references to non-dimensions fail."""
        fact = _base_contract("fact", FK_TO_OTHER)
        other = _base_contract("other_contract")
        with pytest.raises(ValueError, match="invalid schema type"):
            fact.validate_references(FakeResolver(other), enforce_star_schema=True)

    def test_star_schema_opt_in_accepts_dimension(self):
        """With enforce_star_schema=True, references to dimensions pass."""
        fact = _base_contract("fact", FK_TO_OTHER)
        dimension = _dimension_contract("other_contract")
        fact.validate_references(FakeResolver(dimension), enforce_star_schema=True)

    def test_multiple_errors_aggregated(self):
        """All failures are collected into a single exception message."""
        fact = _base_contract(
            "fact",
            [
                {
                    "fields": ["id"],
                    "reference": {"resource": "missing_a", "fields": ["id"]},
                },
                {
                    "fields": ["value"],
                    "reference": {"resource": "missing_b", "fields": ["id"]},
                },
            ],
        )
        with pytest.raises(ValueError) as exc_info:
            fact.validate_references(FakeResolver())
        message = str(exc_info.value)
        assert "missing_a" in message
        assert "missing_b" in message

    def test_self_reference_skipped(self):
        """Self-references (resource=None) are skipped — validated at schema
        construction via validate_structural_integrity, not resolver lookup."""
        contract = BaseContract.model_validate(
            {
                "name": "hierarchy",
                "tableschema": {
                    "primaryKey": ["id"],
                    "foreignKeys": [
                        {
                            "fields": ["parent_id"],
                            "reference": {"resource": None, "fields": ["id"]},
                        }
                    ],
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "parent_id", "type": "integer"},
                    ],
                },
            }
        )
        # Empty resolver — if self-ref wasn't skipped, this would raise
        # "unknown contract" for the None target.
        contract.validate_references(FakeResolver())

    def test_self_reference_skipped_with_star_schema(self):
        """Self-references bypass the star-schema check — a table pointing at
        itself doesn't need to satisfy 'references must be dimensions'."""
        contract = BaseContract.model_validate(
            {
                "name": "hierarchy",
                "tableschema": {
                    "primaryKey": ["id"],
                    "foreignKeys": [
                        {
                            "fields": ["parent_id"],
                            "reference": {"resource": None, "fields": ["id"]},
                        }
                    ],
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "parent_id", "type": "integer"},
                    ],
                },
            }
        )
        contract.validate_references(FakeResolver(), enforce_star_schema=True)


class TestCrossContractReferences:
    def test_star_schema_enforced_by_default(self):
        """CrossContract rejects non-dimension references when omitting the
        enforce_star_schema argument (default is True)."""
        fact = CrossContract.model_validate(
            {
                "name": "fact",
                "title": "Fact",
                "description": "Fact table",
                "contract_type": "General",
                "tableschema": {
                    "primaryKey": ["id"],
                    "foreignKeys": FK_TO_OTHER,
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "value", "type": "number"},
                    ],
                },
            }
        )
        non_dimension = _general_cross_contract("other_contract")
        with pytest.raises(ValueError, match="invalid schema type"):
            fact.validate_references(FakeResolver(non_dimension))

    def test_references_to_dimensions_pass(self):
        """Calling validate_references with default arguments accepts references
        to dimension contracts."""
        fact = CrossContract.model_validate(
            {
                "name": "fact",
                "title": "Fact",
                "description": "Fact table",
                "contract_type": "General",
                "tableschema": {
                    "primaryKey": ["id"],
                    "foreignKeys": FK_TO_OTHER,
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "value", "type": "number"},
                    ],
                },
            }
        )
        dimension = _dimension_contract("other_contract")
        fact.validate_references(FakeResolver(dimension))

    def test_star_schema_opt_out_accepts_non_dimension(self):
        """Passing enforce_star_schema=False falls back to base-level check."""
        fact = CrossContract.model_validate(
            {
                "name": "fact",
                "title": "Fact",
                "description": "Fact table",
                "contract_type": "General",
                "tableschema": {
                    "primaryKey": ["id"],
                    "foreignKeys": FK_TO_OTHER,
                    "fields": [
                        {"name": "id", "type": "integer"},
                        {"name": "value", "type": "number"},
                    ],
                },
            }
        )
        non_dimension = _general_cross_contract("other_contract")
        fact.validate_references(FakeResolver(non_dimension), enforce_star_schema=False)
