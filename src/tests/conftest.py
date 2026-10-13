from unittest.mock import Mock

import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from crosscontract.contracts import (
    BaseContract,
    ContractResolver,
    CrossContract,
    SubmissionContract,
    TableSchema,
)
from crosscontract.contracts.contracts.metadata_models import License


class CrossContractFactory(ModelFactory[CrossContract]):
    __model__ = CrossContract

    # set the general contract relying on the default TableSchema
    contract_type = "General"

    # Pinned to a Frictionless-legal lowercase name (see `CONTRACT_NAME_PATTERN`).
    name = "my-contract"

    @classmethod
    def tableschema(cls):
        # Force empty foreign keys to avoid 'validate_self_reference' issues entirely
        return TableSchema(fields=[{"name": "id", "type": "string"}], foreignKeys=[])

    @classmethod
    def licenses(cls) -> list[License] | None:
        """
        Overrides the 'licenses' field to handle the custom Pydantic validation
        for the nested License objects.
        """
        return [
            License(
                title="Creative Commons Attribution 4.0",
                path="https://creativecommons.org/licenses/by/4.0/",
            )
        ]


@pytest.fixture(scope="session")
def contract_factory() -> type[CrossContractFactory]:
    """
    Returns the Factory CLASS itself, allowing tests to call .build()
    with different overrides.
    """
    return CrossContractFactory


@pytest.fixture(scope="class")
def contract() -> SubmissionContract:
    """Return a SubmissionContract carrying targets with and without their own
    transformations."""
    submission_data = {
        "name": "submission3",
        "title": "Test Submission",
        "description": "A submission contract whose targets get validated.",
        "project_name": "project1",
        # `all` rather than a column list: the target contracts these tests
        # resolve to need not declare a key column.
        "replace_key": "all",
        "tableschema": {
            "fields": [
                {
                    "name": "variable",
                    "type": "string",
                    "constraints": {"required": True},
                },
                {"name": "country", "type": "string"},
                {"name": "year", "type": "integer"},
                {"name": "value", "type": "number"},
            ]
        },
        "extraction": {
            "routing_column": "variable",
            "transformation_profiles": {
                "regional": [
                    {"type": "rename_columns", "mapping": {"country": "region"}},
                    {"type": "drop_columns", "columns": ["variable"]},
                ],
                "annual": [
                    {"type": "rename_columns", "mapping": {"year": "period"}},
                    {"type": "drop_columns", "columns": ["variable"]},
                ],
            },
            "targets": [
                # Profile only.
                {
                    "name": "t_a",
                    "filters": {"variable": "a"},
                    "contract": "contract_a",
                    "transformation_profile": "regional",
                },
                # Profile plus its own step, which casts `period` to a string.
                # `contract_c` declares it an integer, so validation has to coerce
                # it back.
                {
                    "name": "t_year",
                    "filters": {"year": "2030"},
                    "contract": "contract_c",
                    "transformation_profile": "annual",
                    "transformations": [
                        {
                            "type": "cast_column",
                            "column_name": "period",
                            "to_type": "string",
                        },
                    ],
                },
            ],
        },
    }
    return SubmissionContract.model_validate(submission_data)


def target_contract(name: str, fields: list[dict]) -> BaseContract:
    """Build the contract a target names.

    Args:
        name (str): The contract name, matching the target's `contract`.
        fields (list[dict]): The field descriptions.

    Returns:
        BaseContract: The contract.
    """
    return BaseContract.model_validate(
        {"name": name, "tableschema": {"fields": fields}}
    )


@pytest.fixture
def contract_a() -> BaseContract:
    """Return the contract `t_a` names, matching its transformed columns."""
    return target_contract(
        "contract_a",
        [
            {"name": "region", "type": "string"},
            {"name": "year", "type": "integer"},
            {"name": "value", "type": "number"},
        ],
    )


@pytest.fixture
def contract_c() -> BaseContract:
    """Return the contract `t_year` names, declaring `period` an integer."""
    return target_contract(
        "contract_c",
        [
            {"name": "country", "type": "string"},
            {"name": "period", "type": "integer"},
            {"name": "value", "type": "number"},
        ],
    )


def resolver_returning(contract: BaseContract | None) -> Mock:
    """Build a resolver double that resolves to the given contract.

    Args:
        contract (BaseContract | None): What `resolve` returns.

    Returns:
        Mock: A `ContractResolver` mock recording its calls.
    """
    resolver = Mock(spec=ContractResolver)
    resolver.resolve.return_value = contract
    return resolver


def resolver_for(**contracts: BaseContract | None) -> Mock:
    """Build a resolver double resolving each contract name to its contract.

    Args:
        **contracts (BaseContract | None): One entry per contract name, holding
            what `resolve` returns for it.

    Returns:
        Mock: A `ContractResolver` mock recording its calls.
    """
    resolver = Mock(spec=ContractResolver)
    resolver.resolve.side_effect = lambda name: contracts[name]
    return resolver
