"""Integration tests: the granularity check running inside a converted schema.

`HasNoDescendantInGroup` is covered directly under validation/checks/, and its
derivation under test_adapter.py. What these add is the assembled schema meeting
data, and the failure travelling all the way back out as a parsed report.

These build a `TableSchema` rather than a contract: `validate_dataframe` takes
the hierarchies directly, so nothing here needs a resolver. The resolve step —
which references are hierarchical, and what is read from them — is covered where
it lives, in test_validate_data.py.
"""

import pandas as pd
import pytest

from crosscontract.contracts.schema import SchemaValidationError, TableSchema

PARENT_MAP = {"ch": None, "other": None, "ch_ag": "ch", "ch_other": "ch"}


@pytest.fixture
def schema() -> TableSchema:
    """A fact table keyed by model, scenario, year and region."""
    return TableSchema.model_validate(
        {
            "primaryKey": ["model", "scenario", "year", "region"],
            "foreignKeys": [
                {
                    "fields": ["region"],
                    "reference": {"resource": "dim_region", "fields": ["id"]},
                }
            ],
            "fields": [
                {"name": "model", "type": "string"},
                {"name": "scenario", "type": "string"},
                {"name": "year", "type": "integer"},
                {"name": "region", "type": "string"},
                {"name": "value", "type": "number"},
            ],
        }
    )


def _df(rows: list[tuple[str, str, int, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["model", "scenario", "year", "region", "value"])


class TestGranularityEndToEnd:
    """The PRD's done-means pair, run through the assembled schema."""

    def test_aggregate_beside_its_child_is_rejected(self, schema: TableSchema):
        """`(A, 2030, ch, 100)` and `(A, 2030, ch_ag, 30)` in one frame: summing
        the region column would count the 30 twice."""
        df = _df(
            [
                ("m1", "A", 2030, "ch", 100.0),
                ("m1", "A", 2030, "ch_ag", 30.0),
            ]
        )
        with pytest.raises(SchemaValidationError):
            schema.validate_dataframe(df, dimension_hierarchies={"region": PARENT_MAP})

    def test_the_same_members_under_different_scenarios_pass(self, schema: TableSchema):
        """`(A, 2030, ch, 100)` and `(B, 2030, ch_ag, 30)` are two groups, each
        summing correctly on its own."""
        df = _df(
            [
                ("m1", "A", 2030, "ch", 100.0),
                ("m1", "B", 2030, "ch_ag", 30.0),
            ]
        )
        schema.validate_dataframe(df, dimension_hierarchies={"region": PARENT_MAP})

    def test_hierarchies_are_opt_in(self, schema: TableSchema):
        """The same violating frame passes when no hierarchy is supplied — the
        schema alone cannot tell that `region` names a hierarchical dimension."""
        df = _df(
            [
                ("m1", "A", 2030, "ch", 100.0),
                ("m1", "A", 2030, "ch_ag", 30.0),
            ]
        )
        schema.validate_dataframe(df)


class TestGranularityReport:
    """What the submitter is told, once the failure has been parsed back out."""

    @pytest.fixture
    def error(self, schema: TableSchema) -> SchemaValidationError:
        df = _df(
            [
                ("m1", "A", 2030, "ch", 100.0),
                ("m1", "A", 2030, "ch_ag", 30.0),
            ]
        )
        with pytest.raises(SchemaValidationError) as exc_info:
            schema.validate_dataframe(df, dimension_hierarchies={"region": PARENT_MAP})
        return exc_info.value

    @staticmethod
    def _granularity_rows(error: SchemaValidationError) -> list[dict]:
        return [
            row for row in error.errors if "dimension granularity" in str(row["check"])
        ]

    def test_the_report_names_the_dimension_column(self, error: SchemaValidationError):
        """`failure_message()` leads with `Columns '...'` so that
        `SchemaValidationError` recognises it and parses the columns back out.
        Without that shape the report would name no column at all."""
        rows = self._granularity_rows(error)
        assert rows
        assert all("region" in str(row["column"]) for row in rows)

    def test_the_report_points_at_the_aggregate_row(self, error: SchemaValidationError):
        """The `ch` row is the one to remove, so it is the one reported. A check
        that flagged the detail row instead would still raise, and would send the
        submitter after the wrong row."""
        rows = self._granularity_rows(error)
        assert len(rows) == 1
        # the message lists the dimension column first, so it leads the tuple
        assert rows[0]["failure_case"][0] == "ch"


class TestSeveralRulesInOneRun:
    """Each defect is reported by the rule that owns it."""

    def test_three_violations_are_reported_separately(self, schema: TableSchema):
        """One frame breaking three rules at once, validated lazily. Each rule
        answers under its own label, which is also what keeps a granularity
        failure from being read as a broken dimension hierarchy."""
        df = _df(
            [
                # duplicated primary key
                ("m1", "A", 2030, "ch", 100.0),
                ("m1", "A", 2030, "ch", 100.0),
                # makes the two rows above report an aggregate over a detail row
                ("m1", "A", 2030, "ch_ag", 30.0),
                # not a member of the referenced dimension
                ("m1", "B", 2030, "atlantis", 5.0),
            ]
        )
        with pytest.raises(SchemaValidationError) as exc_info:
            schema.validate_dataframe(
                df,
                primary_key_values=[],
                foreign_key_values={("region",): [(m,) for m in PARENT_MAP]},
                dimension_hierarchies={"region": PARENT_MAP},
                lazy=True,
            )

        reported = " ".join(str(row["check"]) for row in exc_info.value.errors)
        assert "primary key" in reported
        assert "foreign key" in reported
        assert "dimension granularity" in reported
