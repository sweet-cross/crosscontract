"""The submission path inherits the granularity check with no code of its own.

ADR 0007 claims a bundle is split into targets and each target then validates as
an ordinary variable. These tests hold that claim to account for the granularity
check: nothing in `submission/` knows what a hierarchy is, and a target still
gets checked.
"""

from unittest.mock import Mock

import pandas as pd
import pytest

from crosscontract.contracts import ContractResolver, CrossContract
from crosscontract.contracts.schema import SchemaValidationError
from crosscontract.submission import SubmissionContract, SubmissionHandler
from crosscontract.submission.exceptions import TargetValidationError

DIMENSION_DATA = pd.DataFrame(
    {
        "id": ["ch", "other", "ch_ag", "ch_other"],
        "parent_id": [None, None, "ch", "ch"],
    }
)


@pytest.fixture
def dimension() -> CrossContract:
    """The hierarchical dimension the target's `region` column references."""
    return CrossContract.model_validate(
        {
            "name": "dim_region",
            "title": "Regions",
            "description": "Regions",
            "contract_type": "Dimension",
            "tableschema": {},
        }
    )


@pytest.fixture
def target_contract() -> CrossContract:
    """The ValueVariable a target names, keyed by region and year."""
    return CrossContract.model_validate(
        {
            "name": "emissions",
            "title": "Emissions",
            "description": "Emissions",
            "contract_type": "ValueVariable",
            "tableschema": {
                "primaryKey": ["region", "year"],
                "foreignKeys": [
                    {
                        "fields": ["region"],
                        "reference": {"resource": "dim_region", "fields": ["id"]},
                    }
                ],
                "fields": [
                    {"name": "region", "type": "string"},
                    {"name": "year", "type": "integer"},
                    {"name": "value", "type": "number"},
                ],
            },
        }
    )


@pytest.fixture
def contract() -> SubmissionContract:
    """A bundle carrying one target, which drops the routing column on the way."""
    return SubmissionContract.model_validate(
        {
            "name": "submission_granularity",
            "title": "Test Submission",
            "description": "A bundle whose target references a dimension.",
            "project_name": "project1",
            "tableschema": {
                "fields": [
                    {
                        "name": "variable",
                        "type": "string",
                        "constraints": {"required": True},
                    },
                    {"name": "region", "type": "string"},
                    {"name": "year", "type": "integer"},
                    {"name": "value", "type": "number"},
                ]
            },
            "extraction": {
                "routing_column": "variable",
                "targets": [
                    {
                        "name": "t_emissions",
                        "filters": {"variable": "emissions"},
                        "contract": "emissions",
                        "transformations": [
                            {"type": "drop_columns", "columns": ["variable"]}
                        ],
                    }
                ],
            },
        }
    )


@pytest.fixture
def resolver(dimension: CrossContract, target_contract: CrossContract) -> Mock:
    """Resolves both contracts and serves the dimension's rows."""
    contracts = {"emissions": target_contract, "dim_region": dimension}
    resolver = Mock(spec=ContractResolver)
    resolver.resolve.side_effect = lambda name: contracts[name]
    resolver.get_data.return_value = DIMENSION_DATA
    return resolver


def _bundle(rows: list[tuple[str, int, float]]) -> pd.DataFrame:
    """Build a bundle whose rows all route to the one target."""
    return pd.DataFrame(
        [("emissions", region, year, value) for region, year, value in rows],
        columns=["variable", "region", "year", "value"],
    )


class TestValidateTargetInheritsTheCheck:
    def test_target_reporting_an_aggregate_over_its_detail_fails(
        self, contract: SubmissionContract, resolver: Mock
    ):
        """The bundle's rows become the target's rows, and the target is judged
        exactly as it would be on its own: `ch` alongside `ch_ag` in one year."""
        handler = SubmissionHandler(
            contract, _bundle([("ch", 2030, 100.0), ("ch_ag", 2030, 30.0)])
        )
        with pytest.raises(SchemaValidationError):
            handler.validate_target(
                "t_emissions",
                resolver=resolver,
                check_dimension_granularity=True,
            )

    def test_the_dimension_is_read_through_the_submitter_s_resolver(
        self, contract: SubmissionContract, resolver: Mock
    ):
        """The hierarchy is fetched live, through the same resolver that supplies
        the target contract — there is no submission-specific lookup."""
        handler = SubmissionHandler(contract, _bundle([("ch", 2030, 100.0)]))
        handler.validate_target(
            "t_emissions", resolver=resolver, check_dimension_granularity=True
        )
        assert resolver.get_data.call_args.kwargs["name"] == "dim_region"

    def test_the_flag_is_off_by_default_on_the_handler(
        self, contract: SubmissionContract, resolver: Mock
    ):
        """`SubmissionHandler` keeps the library default; it is
        `CrossSubmitter.validate_submission` that turns the check on."""
        handler = SubmissionHandler(
            contract, _bundle([("ch", 2030, 100.0), ("ch_ag", 2030, 30.0)])
        )
        handler.validate_target("t_emissions", resolver=resolver)
        resolver.get_data.assert_not_called()


class TestValidateTargetsKeepsTheTargetName:
    def test_failure_is_keyed_by_the_target_it_came_from(
        self, contract: SubmissionContract, resolver: Mock
    ):
        """Collected across targets, a granularity failure is named like any
        other, so a submitter is told which part of their bundle to fix."""
        handler = SubmissionHandler(
            contract, _bundle([("ch", 2030, 100.0), ("ch_ag", 2030, 30.0)])
        )
        with pytest.raises(TargetValidationError) as exc_info:
            handler.validate_targets(
                resolver=resolver, check_dimension_granularity=True
            )
        assert list(exc_info.value.errors) == ["t_emissions"]
