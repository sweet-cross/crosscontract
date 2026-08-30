# Hierarchical Dimensions are strict trees with mandatory `other` entries

Every hierarchical **Dimension** is modelled as a strict tree: each member references
exactly one parent at the level above (level 0 has none), and each level carries a
catch-all `other` / `<parent_id>_other` member to absorb uncategorised data. We chose
this so the **Sum invariant** holds — summing leaf values always equals the totals at any
level, with no double-counting and no leakage — which lets consumers aggregate freely
across any combination of dimensions without reasoning about overlap.

## Consequences

- Dimensions cannot reference other dimensions; many-to-many or cross-dimension
  relationships would need a separate bridging-table (factless-fact) concept, not yet in
  the codebase.
- The mandatory `other` entries are not optional cosmetics — they are what makes the
  invariant total rather than approximate.
