import pytest
from pydantic import ValidationError

from crosscontract.transformations.fetch import ColumnAggregation, LevelKeepSpec


def test_int_form():
    """An int is a level roll-up and passes through unchanged."""
    ca = ColumnAggregation.model_validate(1)
    assert ca.root == 1
    assert ca.model_dump(exclude_defaults=True) == 1


def test_list_form():
    """A list is a target-id set and passes through unchanged."""
    ca = ColumnAggregation.model_validate(["a", "b"])
    assert ca.model_dump(exclude_defaults=True) == ["a", "b"]


def test_level_only_dict_becomes_levelkeepspec():
    """A dict with only `level` resolves to a LevelKeepSpec.

    With `exclude_defaults=True` the empty `keep` is dropped, so it dumps to
    the plain `{"level": N}` form that hits get_data's level-mapping branch.
    """
    ca = ColumnAggregation.model_validate({"level": 1})
    assert isinstance(ca.root, LevelKeepSpec)
    assert ca.model_dump(exclude_defaults=True) == {"level": 1}


def test_level_with_keep():
    """A dict with `level` and `keep` keeps both on dump."""
    ca = ColumnAggregation.model_validate({"level": 0, "keep": ["x"]})
    assert ca.model_dump(exclude_defaults=True) == {"level": 0, "keep": ["x"]}


def test_raw_mapping_passthrough():
    """A dict without spec keys is a raw mapping passthrough."""
    ca = ColumnAggregation.model_validate({"leaf_1": "group_x"})
    assert ca.model_dump(exclude_defaults=True) == {"leaf_1": "group_x"}


def test_levelkeepspec_forbids_extra_keys():
    """A spec-dict with `level` rejects unknown keys."""
    with pytest.raises(ValidationError):
        ColumnAggregation.model_validate({"level": 0, "bogus": 1})


def test_keep_without_level_rejected():
    """`keep` without `level` is rejected at spec time, matching get_data."""
    with pytest.raises(ValidationError, match="only valid together with 'level'"):
        ColumnAggregation.model_validate({"keep": ["x"]})
