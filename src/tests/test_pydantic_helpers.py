import pytest
from pydantic import BaseModel

from crosscontract._pydantic_helpers import OptionalNonEmptyList


class _Model(BaseModel):
    items: OptionalNonEmptyList[str] = None


class TestOptionalNonEmptyList:
    def test_unset_defaults_to_none_and_is_omitted(self):
        model = _Model()
        assert model.items is None
        assert model.model_dump(exclude_none=True) == {}

    def test_empty_list_collapses_to_none(self):
        model = _Model(items=[])
        assert model.items is None
        assert model.model_dump(exclude_none=True) == {}

    def test_populated_list_passes_through(self):
        model = _Model(items=["a", "b"])
        assert model.items == ["a", "b"]
        assert model.model_dump(exclude_none=True) == {"items": ["a", "b"]}

    def test_explicit_none_stays_none(self):
        model = _Model(items=None)
        assert model.items is None

    def test_roundtrip_omits_empty_under_exclude_none(self):
        dumped = _Model(items=[]).model_dump(exclude_none=True)
        assert "items" not in dumped
        assert _Model.model_validate(dumped).items is None

    @pytest.mark.parametrize("bad", [0, "", {}, "abc"])
    def test_non_list_values_pass_through_to_validation(self, bad):
        # The before-validator only collapses empty lists; anything else is left
        # for pydantic's normal validation to accept or reject.
        with pytest.raises(ValueError):
            _Model(items=bad)
