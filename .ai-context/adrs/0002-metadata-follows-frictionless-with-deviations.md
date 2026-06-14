# Contract metadata follows Frictionless, with deliberate deviations

The `CrossMetaData` provenance/licensing fields (`contributors`, `sources`,
`licenses` — defined in `metadata_models.py` as `Contributor`, `DataSource`,
`License`) follow the [Frictionless Data](https://specs.frictionlessdata.io/)
vocabulary so the schema interops with the wider ecosystem, but depart from it
on a few points by design. A DCAT-CH / DCAT-AP adapter is planned for a later
release; until then Frictionless is the reference vocabulary.

These deviations are intentional — do not "fix" them back toward strict
Frictionless:

- **Resource-level scope.** Frictionless puts `contributors` at the *data
  package* level (and `sources`/`licenses` at both package and resource level).
  CrossContract attaches all three at the **contract (resource) level** so each
  contract carries its own provenance and licensing.
- **`licenses` describes the data, not the contract.** The license applies to
  the data associated with the contract, not to the contract document itself.
  As in Frictionless, this metadata is informational and not legally binding.
- **Narrower `role` set.** `ContributorRoles` is restricted to `author`,
  `maintainer`, `contributor` (Frictionless also allows `publisher`,
  `wrangler`).
- **No extra fields.** `Contributor`, `DataSource`, and `License` are
  `extra="forbid"` — a misspelled key fails validation rather than being
  silently dropped.

## Two layers: curated CROSS models vs. the faithful mirror

The deviations above belong to the **curated CROSS models** in `metadata_models.py`
— the strict surface a `CrossContract` actually uses. Separately, the internal
`_standards/frictionless/` package provides a **faithful, permissive mirror** of
the upstream standard: `Source`, `License`, `Contributor`, and the
`Data Resource` / `Data Package` descriptors, all `extra="allow"` and with the
full Frictionless `role` set. The two coexist on purpose:

- The **mirror** exists for interop — validating or round-tripping arbitrary
  Frictionless descriptors without losing unknown keys. It does *not* impose the
  CROSS deviations.
- The **curated models** stay the strict, CROSS-facing types; the deviations
  listed above are theirs alone.

Keep them separate — do not collapse the curated models onto the mirror (that
would re-admit extra fields and the wider `role` set), and do not push CROSS
deviations into the mirror (that would make it an unfaithful copy of the
standard). Wiring the two together (e.g. the curated models as narrowed views of
the mirror) is deferred.
