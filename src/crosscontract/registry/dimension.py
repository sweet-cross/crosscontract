from typing import Any

import numpy as np
import pandas as pd

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
        self._ancestry_chains = None

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

    def _build_ancestry_chains(self) -> dict[Any, list[Any]]:
        """Precompute the full ancestry chain for every node in the dimension.

        Each chain is an ordered list starting from the node itself and
        walking up through parents to the root.  For example, in a
        three-level hierarchy, ``leaf_1``'s chain would be
        ``["leaf_1", "cat_a", "total"]``.

        The result is cached and reused by ``get_ancestor_map_by_ids``
        to avoid repeated tree walks.

        Returns:
            A dictionary mapping each dimension ID to its ancestry chain
            (a list from self to root, inclusive).
        """
        df_dim = self.data.set_index("id")
        chains: dict[Any, list[Any]] = {}
        for node_id in df_dim.index:
            chain = []
            current = node_id
            seen = set()
            while current is not None and not pd.isna(current):
                if current in seen:
                    break
                chain.append(current)
                seen.add(current)
                current = (
                    df_dim.at[current, "id_parent"] if current in df_dim.index else None
                )
            chains[node_id] = chain
        return chains

    def get_ancestor_map_by_ids(self, target_ids: list[Any]) -> dict[Any, Any]:
        """Build a mapping from every node to its nearest ancestor in the
        target set.

        For each node, walks its precomputed ancestry chain until it finds
        an ID present in *target_ids*.  Nodes already in the set map to
        themselves.  Nodes whose ancestry chain does not intersect the
        target set are omitted from the returned mapping (and will be
        kept as-is by ``_aggregate`` via ``fillna``).

        Args:
            target_ids: The dimension IDs defining the aggregation targets.
                Must be a subset of the IDs in the dimension data.

        Returns:
            A dictionary mapping dimension IDs to their nearest ancestor
            in the target set.
        """
        if self._ancestry_chains is None:
            self._ancestry_chains = self._build_ancestry_chains()

        target_set = set(target_ids)
        dim_map: dict[Any, Any] = {}
        for node_id, chain in self._ancestry_chains.items():
            for ancestor in chain:
                if ancestor in target_set:
                    dim_map[node_id] = ancestor
                    break
        return dim_map

    def clear_data_cache(self):
        super().clear_data_cache()
        self._ancestor_maps = None
        self._label_map = None
        self._ancestry_chains = None
