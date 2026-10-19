from .base_dimension import CrossBaseDimension


class CrossFlexibleDimension(CrossBaseDimension):
    """Flexible (non-hierarchical) dimension obtained from the CROSS data platform.

    Backed by a ``FlexibleDimensionSchema`` contract: user-defined fields plus
    mandatory ``label`` and ``description``. Inherits ``label_map`` from
    ``CrossBaseDimension`` and intentionally exposes no hierarchy machinery.
    """

    def __str__(self):
        return f"FlexibleDimension(name={self.name})"
