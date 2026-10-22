import pytest
from pydantic import ValidationError

from crosscontract.contracts.fetching import FetchSpec


def test_empty_collapses_to_none():
    """An unset spec yields the get_data bypass sentinels."""
    assert FetchSpec(contract="my-contract").get_data_kwargs == {
        "filters": None,
        "aggregation": None,
    }


def test_filters_pass_through():
    """Non-empty filters pass through unchanged."""
    spec = FetchSpec(contract="my-contract", filters={"region": ["a", "b"]})
    assert spec.get_data_kwargs["filters"] == {"region": ["a", "b"]}


def test_aggregation_shapes():
    """Each aggregation form converts to the raw dict get_data expects.

    A bare `level` drops its empty `keep` (plain level-mapping branch), while
    an explicit `keep` is retained.
    """
    spec = FetchSpec(
        contract="my-contract",
        aggregation={
            "region": 1,
            "sector": {"level": 0},
            "scenario": {"level": 2, "keep": ["x"]},
            "product": ["a", "b"],
            "raw": {"leaf_1": "group_x"},
        },
    )
    assert spec.get_data_kwargs == {
        "filters": None,
        "aggregation": {
            "region": 1,
            "sector": {"level": 0},
            "scenario": {"level": 2, "keep": ["x"]},
            "product": ["a", "b"],
            "raw": {"leaf_1": "group_x"},
        },
    }


def test_fetch_spec_rejects_keep_without_level():
    """An invalid aggregation directive is caught when building a FetchSpec."""
    with pytest.raises(ValidationError, match="only valid together with 'level'"):
        FetchSpec(aggregation={"region": {"keep": ["x"]}})
