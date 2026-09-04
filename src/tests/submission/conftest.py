from unittest.mock import Mock

import pandas as pd
import pytest

from crosscontract.contracts import BaseContract, ContractResolver
from crosscontract.submission import SubmissionContract


@pytest.fixture(scope="class")
def contract() -> SubmissionContract:
    """Return a SubmissionContract carrying targets with and without their own
    transformations."""
    submission_data = {
        "name": "submission3",
        "title": "Test Submission",
        "description": "A submission contract whose targets get validated.",
        "project_name": "project1",
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


def bundle(*rows: tuple[str, str, int, float]) -> pd.DataFrame:
    """Build a submission frame according to the submission contract's schema.

    Args:
        *rows (tuple[str, str, int, float]): One tuple per row, holding
            `variable`, `country`, `year` and `value`.

    Returns:
        pd.DataFrame: The frame, with `year` as a nullable integer column.
    """
    return pd.DataFrame(
        list(rows), columns=["variable", "country", "year", "value"]
    ).astype({"year": "Int64"})


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


@pytest.fixture
def bad_contract_a() -> BaseContract:
    """Return a `contract_a` whose `region` the target's rows cannot satisfy."""
    return target_contract(
        "contract_a",
        [
            {"name": "region", "type": "integer"},
            {"name": "year", "type": "integer"},
            {"name": "value", "type": "number"},
        ],
    )


@pytest.fixture
def bad_contract_c() -> BaseContract:
    """Return a `contract_c` whose `country` the target's rows cannot satisfy."""
    return target_contract(
        "contract_c",
        [
            {"name": "country", "type": "integer"},
            {"name": "period", "type": "integer"},
            {"name": "value", "type": "number"},
        ],
    )
