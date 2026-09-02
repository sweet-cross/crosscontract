from unittest.mock import Mock

import pandas as pd
import pytest

from crosscontract.contracts import BaseContract
from crosscontract.contracts.contracts.resolvers import ContractResolver
from crosscontract.submission import SubmissionContract, SubmissionHandler


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


class TestValidateTarget:
    def test_returns_the_validated_frame(
        self, contract: SubmissionContract, contract_a: BaseContract
    ):
        """Test that the target's rows are extracted, transformed and returned."""
        handler = SubmissionHandler(
            contract=contract,
            bundle=bundle(("a", "CH", 2020, 1.0), ("b", "DE", 2020, 2.0)),
        )
        data = handler.validate_target("t_a", contract=contract_a)
        assert list(data.columns) == ["region", "year", "value"]
        assert list(data["region"]) == ["CH"]
        assert list(data["value"]) == [1.0]

    def test_coerces_to_the_contracts_types(
        self, contract: SubmissionContract, contract_c: BaseContract
    ):
        """Test that the returned frame is coerced, not merely accepted.

        `t_year`'s own transformation casts `period` to a string; `contract_c`
        declares it an integer, so the validated frame carries it back as one.
        """
        handler = SubmissionHandler(
            contract=contract, bundle=bundle(("c", "DE", 2030, 4.0))
        )
        transformed = handler.get_target_data("t_year")
        assert transformed["period"].dtype == "string"

        data = handler.validate_target("t_year", contract=contract_c)
        assert data["period"].dtype == "Int64"
        assert list(data["period"]) == [2030]

    def test_resolves_the_contract_when_only_a_resolver_is_given(
        self, contract: SubmissionContract, contract_a: BaseContract
    ):
        """Test that the target's contract is looked up by name."""
        resolver = resolver_returning(contract_a)
        handler = SubmissionHandler(
            contract=contract, bundle=bundle(("a", "CH", 2020, 1.0))
        )
        data = handler.validate_target("t_a", resolver=resolver)
        resolver.resolve.assert_called_once_with("contract_a")
        assert list(data["region"]) == ["CH"]

    def test_contract_takes_precedence_over_the_resolver(
        self, contract: SubmissionContract, contract_a: BaseContract
    ):
        """Test that an explicit contract wins and the resolver is never asked.

        The resolver would hand back a contract declaring `region` an integer,
        which the target's rows cannot satisfy — so a resolved contract would
        surface as a failure rather than as a passing test.
        """
        resolver = resolver_returning(
            target_contract(
                "contract_a",
                [
                    {"name": "region", "type": "integer"},
                    {"name": "year", "type": "integer"},
                    {"name": "value", "type": "number"},
                ],
            )
        )
        handler = SubmissionHandler(
            contract=contract, bundle=bundle(("a", "CH", 2020, 1.0))
        )
        data = handler.validate_target("t_a", contract=contract_a, resolver=resolver)
        resolver.resolve.assert_not_called()
        assert list(data["region"]) == ["CH"]

    def test_passes_its_arguments_through_to_validate_data(
        self, contract: SubmissionContract
    ):
        """Test that the resolver, the check flags and `lazy` arrive unchanged,
        alongside the target's transformed rows."""
        resolver = Mock(spec=ContractResolver)
        target_contract_mock = Mock(spec=BaseContract)
        target_contract_mock.name = "contract_a"
        handler = SubmissionHandler(
            contract=contract, bundle=bundle(("a", "CH", 2020, 1.0))
        )

        handler.validate_target(
            "t_a",
            contract=target_contract_mock,
            resolver=resolver,
            check_existing_primary_key=True,
            check_existing_foreign_key=True,
            lazy=False,
        )

        target_contract_mock.validate_data.assert_called_once()
        args, kwargs = target_contract_mock.validate_data.call_args
        pd.testing.assert_frame_equal(args[0], handler.get_target_data("t_a"))
        assert kwargs == {
            "resolver": resolver,
            "check_existing_primary_key": True,
            "check_existing_foreign_key": True,
            "lazy": False,
        }

    def test_target_claiming_no_rows_returns_an_empty_frame(
        self, contract: SubmissionContract, contract_a: BaseContract
    ):
        """Test that an empty target validates to an empty frame, not an error."""
        handler = SubmissionHandler(
            contract=contract, bundle=bundle(("b", "DE", 2020, 2.0))
        )
        data = handler.validate_target("t_a", contract=contract_a)
        assert data.empty
        assert list(data.columns) == ["region", "year", "value"]
