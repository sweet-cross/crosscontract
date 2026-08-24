import pandas as pd
import pytest

from crosscontract.submission import SubmissionContract, SubmissionHandler


@pytest.fixture(scope="class")
def contract() -> SubmissionContract:
    """Return a SubmissionContract instance for the coverage_data fixture."""
    coverage_data = {
        "name": "submission2",
        "title": "Test Submission",
        "description": "A submission contract carrying several targets.",
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
                # Renames, then drops the routing column — the rename-then-act shape
                # the real `demand` / `supply` profiles have.
                "regional": [
                    {"type": "rename_columns", "mapping": {"country": "region"}},
                    {"type": "drop_columns", "columns": ["variable"]},
                ],
                # A second profile, so profile selection is per target rather than
                # global.
                "annual": [
                    {"type": "rename_columns", "mapping": {"year": "period"}},
                    {"type": "drop_columns", "columns": ["variable"]},
                ],
            },
            "targets": [
                # Profile only — no transformations of its own. The shape that
                # `carbon_emissions` has in the real spec, and the one an
                # implementation looping `target.transformations` alone gets wrong.
                {
                    "name": "t_a",
                    "filters": {"variable": "a"},
                    "contract": "contract_a",
                    "transformation_profile": "regional",
                },
                # Own transformations only, no profile.
                {
                    "name": "t_b_ch",
                    "filters": {"variable": "b", "country": "CH"},
                    "contract": "contract_b",
                    "transformations": [
                        {"type": "drop_columns", "columns": ["variable"]},
                        {
                            "type": "map_column_values",
                            "column_name": "country",
                            "mapping": {"CH": "ch"},
                        },
                    ],
                },
                # Both. The own step addresses `period`, which only exists *after*
                # the profile has run — so a reversed order raises rather than
                # quietly producing something else.
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
                # Neither.
                {
                    "name": "t_none",
                    "filters": {"variable": "d"},
                    "contract": "contract_d",
                },
            ],
        },
    }
    return SubmissionContract.model_validate(coverage_data)


def bundle(*rows: tuple[str, str, int, float]) -> pd.DataFrame:
    """Build a submission frame according to the submission contract's schema.

    Args:
        *rows (tuple[str, str, int, float]): One tuple per row, holding
            `variable`, `country`, `year` and `value`.

    Returns:
        pd.DataFrame: The frame, with `year` as a nullable integer column so the
            string-form matching is exercised against a typed column.
    """
    return pd.DataFrame(
        list(rows), columns=["variable", "country", "year", "value"]
    ).astype({"year": "Int64"})


def claimed_bundle() -> pd.DataFrame:
    """Build a frame holding one row for each transforming target.

    Returns:
        pd.DataFrame: One row claimed by `t_a`, `t_b_ch`, `t_year` and `t_none`
            respectively.
    """
    return bundle(
        ("a", "CH", 2020, 1.0),  # claimed by t_a
        ("b", "CH", 2020, 2.0),  # claimed by t_b_ch
        ("c", "DE", 2030, 4.0),  # claimed by t_year
        ("d", "DE", 2020, 5.0),  # claimed by t_none
    )


class TestTransformTargetData:
    def test_applies_the_profile_when_the_target_has_no_own_steps(
        self, contract: SubmissionContract
    ):
        """Test that a target carrying only a transformation profile gets the
        profile's steps."""
        handler = SubmissionHandler(specs=contract, df=claimed_bundle())
        data = handler.transform_target_data(
            handler.extract_target_data("t_a"), "t_a"
        )
        assert list(data.columns) == ["region", "year", "value"]

    def test_applies_own_steps_when_the_target_has_no_profile(
        self, contract: SubmissionContract
    ):
        """Test that a target carrying only its own transformations gets them."""
        handler = SubmissionHandler(specs=contract, df=claimed_bundle())
        data = handler.transform_target_data(
            handler.extract_target_data("t_b_ch"), "t_b_ch"
        )
        assert list(data.columns) == ["country", "year", "value"]
        assert list(data["country"]) == ["ch"]

    def test_applies_the_profile_before_the_targets_own_steps(
        self, contract: SubmissionContract
    ):
        """Test that the profile runs first when a target carries both.

        `t_year`'s own step casts `period`, a column that exists only after the
        `annual` profile has renamed `year` to it — so the reverse order raises
        on a missing column rather than returning a different frame.
        """
        handler = SubmissionHandler(specs=contract, df=claimed_bundle())
        data = handler.transform_target_data(
            handler.extract_target_data("t_year"), "t_year"
        )
        assert list(data.columns) == ["country", "period", "value"]
        assert data["period"].dtype == "string"
        assert list(data["period"]) == ["2030"]

    def test_is_a_no_op_when_the_target_has_neither(
        self, contract: SubmissionContract
    ):
        """Test that a target with no profile and no transformations returns the
        claimed rows unchanged."""
        handler = SubmissionHandler(specs=contract, df=claimed_bundle())
        claimed = handler.extract_target_data("t_none")
        data = handler.transform_target_data(claimed, "t_none")
        pd.testing.assert_frame_equal(data, claimed)

    def test_unknown_target_name_raises(self, contract: SubmissionContract):
        """Test that an unknown target name surfaces the lookup's KeyError."""
        df = claimed_bundle()
        handler = SubmissionHandler(specs=contract, df=df)
        with pytest.raises(KeyError, match="No target with name 'nope' found."):
            handler.transform_target_data(df, "nope")

    def test_input_frame_is_not_mutated(self, contract: SubmissionContract):
        """Test that transforming leaves the frame it was handed untouched."""
        df = claimed_bundle()
        before = df.copy()
        handler = SubmissionHandler(specs=contract, df=df)
        handler.transform_target_data(df, "t_b_ch")
        pd.testing.assert_frame_equal(df, before)


class TestGetTargetData:
    def test_composes_extraction_and_transformation(
        self, contract: SubmissionContract
    ):
        """Test that the composition equals transforming the extracted rows."""
        handler = SubmissionHandler(specs=contract, df=claimed_bundle())
        expected = handler.transform_target_data(
            handler.extract_target_data("t_year"), "t_year"
        )
        pd.testing.assert_frame_equal(handler.get_target_data("t_year"), expected)

    def test_returns_only_the_targets_rows_transformed(
        self, contract: SubmissionContract
    ):
        """Test that the result carries the target's rows in their transformed
        shape."""
        handler = SubmissionHandler(specs=contract, df=claimed_bundle())
        data = handler.get_target_data("t_year")
        assert list(data.columns) == ["country", "period", "value"]
        assert list(data["value"]) == [4.0]


class TestExtractTargetData:
    def test_returns_only_rows_claimed_by_target(self, contract: SubmissionContract):
        """Test that only rows matched by the target's filters are returned."""
        df = bundle(
            ("a", "CH", 2020, 1.0),  # claimed by t_a
            ("b", "CH", 2020, 2.0),  # claimed by t_b_ch
            ("b", "DE", 2020, 3.0),  # unclaimed: country does not match
            ("c", "DE", 2030, 4.0),  # claimed by t_year
            ("c", "DE", 2020, 5.0),  # unclaimed: no target wants it
        )
        handler = SubmissionHandler(specs=contract, df=df)
        t_a_data = handler.extract_target_data("t_a")
        assert list(t_a_data.index) == [0]
        assert list(t_a_data["value"]) == [1.0]

    def test_returns_an_empty_frame_when_no_row_matches(
        self, contract: SubmissionContract
    ):
        """Test that a target claiming no rows yields an empty frame, not an
        error."""
        df = bundle(("c", "DE", 2020, 5.0))
        handler = SubmissionHandler(specs=contract, df=df)
        claimed = handler.extract_target_data("t_a")
        assert claimed.empty
        assert list(claimed.columns) == list(df.columns)

    def test_non_routing_filter_column_claims_rows(self, contract: SubmissionContract):
        """Test that a target constraining only a non-routing integer column
        claims every matching row, matched against the column's string form."""
        df = bundle(
            ("c", "DE", 2030, 4.0),  # claimed by t_year
            ("d", "CH", 2030, 6.0),  # claimed by t_year
            ("c", "DE", 2020, 5.0),  # wrong year
        )
        handler = SubmissionHandler(specs=contract, df=df)
        claimed = handler.extract_target_data("t_year")
        assert list(claimed.index) == [0, 1]
        assert list(claimed["value"]) == [4.0, 6.0]

    def test_unknown_target_name_raises(self, contract: SubmissionContract):
        """Test that an unknown target name surfaces the lookup's KeyError."""
        df = bundle(("a", "CH", 2020, 1.0))
        handler = SubmissionHandler(specs=contract, df=df)
        with pytest.raises(KeyError, match="No target with name 'nope' found."):
            handler.extract_target_data("nope")


class TestUnclaimedRows:
    def test_returns_the_rows_no_target_claims(self, contract: SubmissionContract):
        """Test that only rows matched by no target are returned, with their
        original index labels."""
        df = bundle(
            ("a", "CH", 2020, 1.0),  # claimed by t_a
            ("b", "CH", 2020, 2.0),  # claimed by t_b_ch
            ("b", "DE", 2020, 3.0),  # unclaimed: country does not match
            ("c", "DE", 2030, 4.0),  # claimed by t_year
            ("c", "DE", 2020, 5.0),  # unclaimed: no target wants it
        )
        handler = SubmissionHandler(specs=contract, df=df)
        unclaimed = handler.unclaimed_rows()
        assert list(unclaimed.index) == [2, 4]
        assert list(unclaimed["value"]) == [3.0, 5.0]

    def test_all_rows_claimed_returns_an_empty_frame(
        self, contract: SubmissionContract
    ):
        """Test that a fully claimed bundle yields an empty frame, not None."""
        df = bundle(("a", "CH", 2020, 1.0), ("b", "CH", 2020, 2.0))
        handler = SubmissionHandler(specs=contract, df=df)
        unclaimed = handler.unclaimed_rows()
        assert unclaimed.empty
        assert list(unclaimed.columns) == list(df.columns)

    def test_non_routing_typed_column_claims_rows(self, contract: SubmissionContract):
        """Test that a target constraining only a non-routing integer column
        claims its rows, matched against the column's string form."""
        df = bundle(("c", "DE", 2030, 4.0))
        handler = SubmissionHandler(specs=contract, df=df)
        assert handler.unclaimed_rows().empty

    def test_filters_are_a_conjunction(self, contract: SubmissionContract):
        """Test that a row matching one filter entry but not the other is
        unclaimed."""
        df = bundle(("b", "DE", 2020, 3.0))
        handler = SubmissionHandler(specs=contract, df=df)
        assert list(handler.unclaimed_rows().index) == [0]

    def test_row_claimed_by_two_targets_is_claimed(self, contract: SubmissionContract):
        """Test that a row matched by more than one target is claimed, since
        overlapping targets are legal."""
        df = bundle(("b", "CH", 2030, 6.0))  # claimed by both t_b_ch and t_year
        handler = SubmissionHandler(specs=contract, df=df)
        assert handler.unclaimed_rows().empty

    def test_input_frame_is_not_mutated(self, contract: SubmissionContract):
        """Test that the submitted frame is left untouched."""
        df = bundle(("a", "CH", 2020, 1.0), ("c", "DE", 2020, 5.0))
        before = df.copy()
        handler = SubmissionHandler(specs=contract, df=df)
        handler.unclaimed_rows()
        pd.testing.assert_frame_equal(df, before)
