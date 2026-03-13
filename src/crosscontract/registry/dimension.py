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
        return self._ancestor_maps

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
        return self._label_map

    def _build_ancestor_maps(self) -> dict[int, dict[str, str]]:
        """Precompute ancestor mappings for all aggregation levels.

        Returns:
            dict[int, dict[str, str]]: A dictionary where keys are aggregation levels
                and values are dictionaries mapping dimension IDs to their ancestor
                IDs at that level.
        """
        dim = self.data.set_index("id")
        max_level = dim["level"].max()

        # maps[agg_level] = {id: ancestor_at_that_level}
        ancestor_maps = {}
        for agg_level in range(max_level):
            mapping = {}
            for rid, _ in dim.iterrows():
                current = rid
                while dim.at[current, "level"] > agg_level:
                    current = dim.at[current, "id_parent"]
                mapping[rid] = current
            ancestor_maps[agg_level] = mapping
        return ancestor_maps
