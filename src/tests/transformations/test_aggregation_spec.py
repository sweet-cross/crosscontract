import pytest
from pydantic import ValidationError

from crosscontract.transformations import AggregationSpec
from crosscontract.transformations.aggregation_spec import (
    ColumnAggregation,
    LevelKeepSpec,
)


def test_int_form():
    """An int is a level roll-up and passes through unchanged."""
    ca = ColumnAggregation.model_validate(1)
    assert ca.root == 1
    assert ca.to_arg() == 1


def test_list_form():
    """A list is a target-id set and passes through unchanged."""
    ca = ColumnAggregation.model_validate(["a", "b"])
    assert ca.to_arg() == ["a", "b"]


def test_level_only_dict_becomes_levelkeepspec():
    """A dict with only `level` resolves to a LevelKeepSpec with empty keep."""
    ca = ColumnAggregation.model_validate({"level": 1})
    assert isinstance(ca.root, LevelKeepSpec)
    assert ca.to_arg() == {"level": 1, "keep": []}


def test_level_with_keep():
    """A dict with `level` and `keep` round-trips to the same primitive form."""
    ca = ColumnAggregation.model_validate({"level": 0, "keep": ["x"]})
    assert ca.to_arg() == {"level": 0, "keep": ["x"]}


def test_raw_mapping_passthrough():
    """A dict without spec keys is a raw mapping passthrough."""
    ca = ColumnAggregation.model_validate({"leaf_1": "group_x"})
    assert ca.to_arg() == {"leaf_1": "group_x"}


def test_keep_without_level_rejected():
    """`keep` without `level` is rejected, matching get_data."""
    with pytest.raises(ValidationError):
        ColumnAggregation.model_validate({"keep": ["x"]})


def test_levelkeepspec_forbids_extra_keys():
    """A spec-dict with `level` rejects unknown keys."""
    with pytest.raises(ValidationError):
        ColumnAggregation.model_validate({"level": 0, "bogus": 1})


def test_aggregation_spec_to_get_data_arg():
    """The whole spec converts to a plain get_data-compatible dict."""
    spec = AggregationSpec.model_validate(
        {
            "region": 1,
            "sector": {"level": 0, "keep": ["x"]},
            "scenario": ["a", "b"],
            "product": {"leaf_1": "group_x"},
        }
    )
    assert spec.to_get_data_arg() == {
        "region": 1,
        "sector": {"level": 0, "keep": ["x"]},
        "scenario": ["a", "b"],
        "product": {"leaf_1": "group_x"},
    }
