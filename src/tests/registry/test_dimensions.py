import pandas as pd
import pytest

from crosscontract.registry import CrossDimension

# ---------------------------------------------------------------------------
# Test contract & data
# ---------------------------------------------------------------------------
# A simple 3-level hierarchy:
#
#   level 0:  total
#   level 1:  ├── cat_a
#             └── cat_b
#   level 2:  ├── leaf_1  (under cat_a)
#             ├── leaf_2  (under cat_a)
#             └── leaf_3  (under cat_b)
#
dim_contract = {
    "name": "dim_region",
    "description": "A hierarchical dimension",
    "title": "Region",
    "tableschema": {
        "fields": [
            {"name": "id", "type": "string"},
            {"name": "label", "type": "string"},
            {"name": "level", "type": "integer"},
            {"name": "id_parent", "type": "string"},
        ],
    },
}

dim_data = pd.DataFrame(
    {
        "id": ["total", "cat_a", "cat_b", "leaf_1", "leaf_2", "leaf_3"],
        "label": ["Total", "Category A", "Category B", "Leaf 1", "Leaf 2", "Leaf 3"],
        "level": [0, 1, 1, 2, 2, 2],
        "id_parent": [None, "total", "total", "cat_a", "cat_a", "cat_b"],
    }
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def dimension(make_contract_resource) -> CrossDimension:
    cr = make_contract_resource(data=dim_data, contract_dict=dim_contract)
    return CrossDimension(contract_resource=cr)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestInit:
    def test_filters_rejected(self, make_contract_resource):
        cr = make_contract_resource(data=dim_data, contract_dict=dim_contract)
        with pytest.raises(TypeError):
            CrossDimension(contract_resource=cr, filters={"id": "total"})

    def test_str(self, dimension: CrossDimension):
        assert str(dimension) == "Dimension(name=dim_region)"


class TestLabelMap:
    def test_all_ids_mapped(self, dimension: CrossDimension):
        label_map = dimension.label_map
        assert label_map == {
            "total": "Total",
            "cat_a": "Category A",
            "cat_b": "Category B",
            "leaf_1": "Leaf 1",
            "leaf_2": "Leaf 2",
            "leaf_3": "Leaf 3",
        }

    def test_label_map_cached(self, dimension: CrossDimension):
        map1 = dimension.label_map
        map2 = dimension.label_map
        assert map1 == map2
        assert map1 is not map2  # copies returned


class TestAncestorMaps:
    def test_levels_present(self, dimension: CrossDimension):
        """Ancestor maps should have keys for levels 0 and 1 (range(max_level=2))."""
        assert set(dimension.ancestor_maps.keys()) == {0, 1}

    def test_level_0_maps_everything_to_root(self, dimension: CrossDimension):
        level_0 = dimension.ancestor_maps[0]
        for node_id in dim_data["id"]:
            assert level_0[node_id] == "total"

    def test_level_1_maps_leaves_to_categories(self, dimension: CrossDimension):
        level_1 = dimension.ancestor_maps[1]
        # leaves map to their parent category
        assert level_1["leaf_1"] == "cat_a"
        assert level_1["leaf_2"] == "cat_a"
        assert level_1["leaf_3"] == "cat_b"
        # categories and root map to themselves (already at level >= 1)
        assert level_1["cat_a"] == "cat_a"
        assert level_1["cat_b"] == "cat_b"
        assert level_1["total"] == "total"

    def test_ancestor_maps_cached(self, dimension: CrossDimension):
        maps1 = dimension.ancestor_maps
        maps2 = dimension.ancestor_maps
        assert maps1 == maps2
        assert maps1 is not maps2  # copies returned


class TestFlatDimension:
    """Edge case: a dimension with only one level (all at level 0)."""

    flat_contract = {
        "name": "dim_flat",
        "description": "A flat dimension",
        "title": "Flat",
        "tableschema": {
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "label", "type": "string"},
                {"name": "level", "type": "integer"},
                {"name": "id_parent", "type": "string"},
            ],
        },
    }

    flat_data = pd.DataFrame(
        {
            "id": ["a", "b", "c"],
            "label": ["A", "B", "C"],
            "level": [0, 0, 0],
            "id_parent": [None, None, None],
        }
    )

    def test_no_ancestor_maps(self, make_contract_resource):
        cr = make_contract_resource(
            data=self.flat_data, contract_dict=self.flat_contract
        )
        dim = CrossDimension(contract_resource=cr)
        # range(0) produces nothing
        assert dim.ancestor_maps == {}

    def test_label_map_still_works(self, make_contract_resource):
        cr = make_contract_resource(
            data=self.flat_data, contract_dict=self.flat_contract
        )
        dim = CrossDimension(contract_resource=cr)
        assert dim.label_map == {"a": "A", "b": "B", "c": "C"}


class TestDataCaching:
    def test_data_cached(self, dimension: CrossDimension):
        df1 = dimension.data
        df2 = dimension.data
        assert df1.equals(df2)
        assert df1 is not df2  # copies returned

    def test_data_cache_independent(self, dimension: CrossDimension):
        df1 = dimension.data
        # Modifying the returned DataFrame should not affect the cached version
        df1["new_col"] = "test"
        df2 = dimension.data
        assert "new_col" not in df2.columns

    def test_clear_data_cache(self, dimension: CrossDimension):
        _ = dimension.data
        dimension.clear_data_cache()
        assert dimension._data is None
        assert dimension._ancestor_maps is None
        assert dimension._label_map is None
        _ = dimension.data
        assert dimension.contract_resource.get_data.call_count == 2
