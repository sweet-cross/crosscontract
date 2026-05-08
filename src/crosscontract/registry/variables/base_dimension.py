from abc import ABC

from crosscontract.crossclient.services import ContractResource

from .base_variable import CrossBaseVariable


class CrossBaseDimension(CrossBaseVariable, ABC):
    """Abstract registry-side base for dimension wrappers.

    Mirrors the schema-side ``BaseDimensionSchema`` hierarchy: any contract
    whose tableschema is a dimension schema (rigid ``DimensionSchema`` or
    ``FlexibleDimensionSchema``) wraps to a subclass of this class. Provides
    the common ``label_map`` accessor that both flavors support, since both
    schemas mandate a ``label`` field and a primary key.
    """

    def __init__(self, contract_resource: ContractResource):
        super().__init__(contract_resource)
        self._label_map: dict[str, str] | None = None
        self._color_map: dict[str, str] | None = None

    @property
    def label_map(self) -> dict[str, str]:
        """Mapping from primary-key value to ``label`` for the dimension."""
        if self._label_map is None:
            id_field = self.contract_resource.contract.tableschema.primaryKey.root[0]
            df = self.data
            self._label_map = dict(zip(df[id_field], df["label"], strict=True))
        return self._label_map.copy()

    @property
    def color_map(self) -> dict[str, str]:
        """Mapping from primary-key value to ``color`` for the dimension.

        If the dimension doesn't have a color field, returns an empty dict.
        """
        df = self.data
        if "color" not in df.columns:
            return {}
        if self._color_map is None:
            id_field = self.contract_resource.contract.tableschema.primaryKey.root[0]
            self._color_map = dict(zip(df[id_field], df["color"], strict=True))
        return {
            k: v for k, v in self._color_map.items() if v
        }  # filter out empty/null colors

    def clear_data_cache(self):
        super().clear_data_cache()
        self._label_map = None
        self._color_map = None
