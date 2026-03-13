import numpy as np

from crosscontract.crossclient.services import ContractResource

from .base_variable import CrossBaseVariable


class CrossDimension(CrossBaseVariable):
    """Dimension variable obtained from the CROSS data platform.

    Dimensions have additional methods for handling hierarchical relationships
    and aggregations.
    """

    def __init__(
        self,
        contract_resource: ContractResource,
    ):
        super().__init__(contract_resource)
        self._ancestor_maps = None
        self._label_map = None

    def __str__(self):
        return f"Dimension(name={self.name})"

    @property
    def ancestor_maps(self) -> dict[int, dict[str, str]]:
        """Precompute and return ancestor maps for all aggregation levels.

        Returns:
            dict[int, dict[str, str]]: A dictionary where keys are aggregation levels
                and values are dictionaries mapping dimension IDs to their ancestor
                IDs at that level.

        """
        if self._ancestor_maps is None:
            self._ancestor_maps = self._build_ancestor_maps()
        # return copy
        return {level: mapping.copy() for level, mapping in self._ancestor_maps.items()}

    @property
    def label_map(self) -> dict[str, str]:
        """Return a mapping from id to label for the dimension.

        Returns:
            dict[str, str]: A dictionary mapping dimension IDs to their labels.
        """
        if self._label_map is None:
            self._label_map = dict(
                zip(self.data["id"], self.data["label"], strict=True)
            )
        return self._label_map.copy()

    def clear_data_cache(self):
        super().clear_data_cache()
        self._ancestor_maps = None
        self._label_map = None

    def _build_ancestor_maps(self) -> dict[int, dict[str, str]]:
        """Precompute ancestor mappings for all aggregation levels.

        Returns:
            dict[int, dict[str, str]]: A dictionary where keys are aggregation levels
                and values are dictionaries mapping dimension IDs to their ancestor
                IDs at that level.
        """
        dim = self.data.set_index("id")
        max_level = int(dim["level"].max())

        ids = dim.index.values
        levels = dim["level"].values
        parents = dim["id_parent"].values

        # Map each id to a positional index for fast numpy lookups
        id_to_pos = {id_val: pos for pos, id_val in enumerate(ids)}
        parent_pos = np.array([id_to_pos.get(p, i) for i, p in enumerate(parents)])

        ancestor_maps = {}
        for agg_level in range(max_level):
            # Start with each node as its own ancestor (by position)
            anc = np.arange(len(ids))

            # Walk one level at a time, low → high.
            # Nodes at level <= agg_level keep themselves.
            # At each higher level, inherit the (already-resolved) parent's ancestor.
            for lvl in range(agg_level + 1, max_level + 1):
                mask = levels == lvl
                anc[mask] = anc[parent_pos[mask]]

            ancestor_maps[agg_level] = dict(zip(ids, ids[anc], strict=True))

        return ancestor_maps
