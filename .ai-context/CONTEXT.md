# CrossContract

The shared language of the `crosscontract` package: data **Contracts** that describe
tabular datasets for the CROSS data platform, and the read layer that consumes them.
This file is a glossary, not a spec — it defines what terms mean, not how they are
implemented.

## Language

### The contract

**Contract**:
A formal, documented agreement describing a tabular dataset — a blueprint shared between
a **Data provider** and a **Data consumer**. It is **Metadata** + **Schema**, and
carries no data itself. Every contract has a **contract type** (**ValueVariable**,
**Dimension**, **FlexibleDimension**, or **General**).
_Avoid_: spec, model, definition (when meaning the whole Contract)

**Metadata**:
The descriptive and operational half of a **Contract** — title, description, tags,
ownership, versioning. For CROSS contracts the entries are fixed by the CROSS team;
custom contracts may define their own set.

**Schema**:
The structural half of a **Contract** — field names, data types, mandatory/optional,
constraints, and the primary/foreign keys. *Is* a Frictionless Table Schema, more
strictly defined (typed **table types**, mandatory fields, dimension invariants) and
slightly extended (**Field descriptors**). Describes logical content only, independent of
file format. The correspondence is tight at this level only — a **Contract** above it is
*not* a Frictionless Data Resource, which would bind to a physical file.

**BaseContract** vs **CrossContract**:
A **BaseContract** is the minimal contract (name + schema) for use *outside* the CROSS
platform — bilateral exchange or another platform. A **CrossContract** is the full
CROSS-platform contract, adding the CROSS metadata. "Contract" unqualified means the
concept; reach for these names only when the platform boundary matters.

**Field descriptor**:
Extra semantic information attached to a **Schema** field beyond its type and
constraints — e.g. unit information — enriching the Frictionless standard.

**Contract type**:
The kind of a **Contract** — what the contract is *for*: **ValueVariable**,
**Dimension**, **FlexibleDimension**, or **General**. It selects, but is not the same
thing as, the **Table type** that shapes the contract's **Schema**.

**Table type**:
The kind of a **Schema** — which structural template the **Schema** follows. Each
**Contract type** maps to exactly one table type. The two vocabularies carry the same
four members today and the mapping is currently the identity, but they are deliberately
kept apart so that several contract types may later share one schema. Never assume the
two strings are equal — go through the mapping.

### The platform and its access layers

**CROSS platform**:
The central server that stores **Contracts** and their data, enforces the lifecycle, and
validates submitted data against its contract.
_Avoid_: server, backend, API (when meaning the platform as a whole)

**Registry**:
The consumer-facing, **read-only** access layer: name a **Contract** and get a
**Variable** back with its **Dimensions** resolved, labelled, and ready to aggregate.

**Client**:
The lower-level access layer to the **CROSS platform**, and currently the *only* write
path — creating contracts, changing status, and submitting data go through it. (The
**Registry** may gain write paths later; for now both are needed.)

**Project**:
The owner of submitted data on the **CROSS platform**. A caller acts *on behalf of* one
project when writing or deleting data — named explicitly, or inferred by the platform
when the caller belongs to exactly one. Reads are not narrowed this way: they span every
project the caller may read. A **Contract** itself belongs to no project; only the rows
stored under it do.
_Avoid_: workspace, tenant, organisation, group

### Roles and lifecycle

**Data provider**:
The party that delivers data conforming to a **Contract** and validates it against that
contract before submission.

**Data consumer**:
The party that reads data described by a **Contract**, relying on it to know the
structure and meaning without inspecting the data first.

**Draft / Active / Suspended / Retired**:
The four lifecycle statuses of a **Contract** on the platform.
- **Draft** — exists but not yet in force; not accepting data, freely editable.
- **Active** — in force; data may be submitted and read.
- **Suspended** — submissions stopped but the contract is not yet ready for deletion; a
  reversible pause that may later return to **Active**. Existing data stays readable.
- **Retired** — permanently decommissioned; terminal state and the only one from which
  the stored data may be dropped.

### Naming — name, label, title

These follow the Frictionless table standard.

**name**:
The unique, schema-defined machine identifier — of a **Contract**, a **Schema** field,
or (as `id`) a **Dimension** member. Stable, used in code and foreign keys; not a display
string.
_Avoid_: id (except the literal Dimension-member `id` field), key, slug

**label**:
The human-readable display string of a **Dimension** member, used in graphs and tables.
Exists only on Dimensions (`label_map` maps member name → label).
_Avoid_: title (at member level), caption

**title**:
The human-readable title of a **Contract** / **Variable** as a whole — never of an
individual member.
_Avoid_: label (at contract level), heading

### Datasets and what they hold

**Variable**:
A measured dataset — observations/numbers that reference one or more **Dimensions**.
The thing a data consumer actually wants.
_Avoid_: indicator, time series, fact, value (when meaning the whole dataset)

**ValueVariable**:
The **contract type** that declares a **Variable** — rows that are *measurements*, with
a numeric value meant to be aggregated across **Dimensions**. Names the schema flavour,
not the data itself.

**General**:
The legacy fallback **contract type**, predating the typed contracts. Any tabular
contract that isn't a **Variable** or a **Dimension** (e.g. a mapping/bridge or lookup
table). Should no longer be chosen for new contracts; its long-term fate (deprecate vs.
keep as a generic escape hatch) is undecided while existing contracts migrate to the
typed forms.

### Dimensions — the anchors of the model

**Dimension**:
A categorical axis that a **Variable** is measured against, and an anchor of the star
schema. Unqualified, "Dimension" means the strict **hierarchical** form: members carry a
`level` and a `parent_id`, so leaf values roll up to totals. A Dimension may only
reference itself (its own `parent_id`) — it cannot reference another Dimension.
_Avoid_: category, axis, lookup (when meaning a hierarchical Dimension)

**FlexibleDimension**:
The flat form of a **Dimension** — members with no parent/child hierarchy (e.g.
scenarios, model variants), so values are *not* aggregatable across it. Still carries
human-readable `label` and `description` so it behaves like a Dimension for labelling.

**Level**:
The depth of a member within a (hierarchical) **Dimension**, starting at 0 for the top.
A member at level N references a parent at level N−1.

**Aggregation**:
Collapsing a **Variable**'s rows by rolling its **Dimension** members up to a coarser
level, a target set of ids, or a custom grouping.

**Sum invariant**:
The load-bearing property of every hierarchical **Dimension**: each leaf rolls up to
exactly one parent and the **"other" entries** absorb the remainder, so summing leaf
values equals the totals with no double-counting and no loss — at any mix of levels.
(Our coined term; the property predates the name.)

**Member**:
A single entry (row) of a **Dimension** — one value of that categorical axis, identified
by its **name** (`id`) and shown by its **label**.
_Avoid_: entry, element, category value (pick "member")

**"other" entry**:
The catch-all sentinel **member** every hierarchical **Dimension** carries — `other` at
the root, `other_<parent_id>` at each sub-level — so uncategorised data has a home and the
**Sum invariant** still holds.

### Release and distribution

**Data Resource**:
A **Contract** bound to a physical data file — the contract's descriptive metadata *plus*
a **Data specification**, so it is self-contained and ships alongside its file. There is no
bespoke CROSS class for this: a Data Resource *is* a Frictionless resource descriptor,
emitted by the **Release adapter**.
_Avoid_: file descriptor, dataset (when meaning the bound resource)

**Data specification**:
The file-binding part a bare **Contract** lacks — `path`, `format` (`csv` | `parquet`),
`encoding`, and the derived `profile` — that turns a **Contract** into a **Data Resource**.
The **Release adapter** owns it: `format` is chosen, the rest derived (so the file
description is correct by construction).

**Data Package**:
A bundle of **Data Resources** plus package-level metadata, distributed as a single zip
archive. The realized output of the **Release adapter**: a Frictionless package descriptor
plus its data files, written to disk as a zip.

**Release adapter**:
The translation from CROSS **Contracts** to a Frictionless **Data Package**, parameterised
by how each resource's data is obtained. It fetches through the **Registry**, overlays the
**Release spec**, and emits Frictionless descriptors directly — there is no parallel CROSS
descriptor hierarchy. Resource descriptive metadata **overrides** the contract's defaults
field-by-field; package metadata is **authored** wholesale (a package has no contract to
default from).
_Avoid_: export, dump, builder (when meaning the whole adapter)

**Release spec**:
The **Build spec** for a release — a **CrossDataPackageReleaseSpec** (authored package metadata) plus a
list of **CrossDataResourceReleaseSpec** (per-resource metadata overrides, the chosen `format`, and the
**fetch** instructions). Names the resources to pull and how; the **Release adapter**
consumes it.
_Avoid_: release specification, descriptor (the spec is the recipe, not the output)

**Frictionless descriptor** (the permissive mirror):
A faithful, permissive model of the *upstream* Frictionless `Data Resource` / `Data
Package` — accepts unknown keys, imposes no CROSS rules. This *is* the **Release adapter**'s
output type (so the release is Frictionless-compliant by construction) and also serves
interop / round-tripping of arbitrary descriptors. The CROSS restriction lives upstream in
the **Contract** and in the adapter's file-binding guard, not in a separate strict
descriptor class.

### Transformations and build specs

**Transformation**:
A named, parameterised operation applied to a **Variable**'s tabular data — e.g.
renaming or dropping columns, or remapping values — declared rather than coded, and
applied in declared order. Schema-agnostic: it knows DataFrames, not **Contracts**,
**Schema**, or **Dimensions**.
_Avoid_: spec, block (for a single transformation — those name a **Build spec**)

**Build spec**:
A declarative description (YAML) of an artifact to assemble from platform data — which
**Variable**(s) to load and the ordered **Transformations** to apply to each. Concrete
forms (the **Release spec** for a data package, a plot spec, …) each admit their own
permitted set of **Transformations**. Distinct from a **Data specification**, which is the
file-binding part of a single **Data Resource**, not a build recipe.
_Avoid_: spec (unqualified — ambiguous with **Data specification**)

## Relationships

- A **Contract** is **Metadata** + **Schema**, and has exactly one **Contract type**.
- Each **Contract type** maps to exactly one **Table type**, which fixes the shape of
  the **Schema**. Several contract types may map to the same table type.
- A **ValueVariable** contract declares a **Variable**; a **Dimension** /
  **FlexibleDimension** contract declares a **Dimension**.
- A **Variable** references one or more **Dimensions** (star schema: Variable = fact,
  Dimensions = axes).
- A **Dimension** references only itself (member → parent member); it never references
  another Dimension.
- A hierarchical **Dimension** is a strict tree of **Members** across **Levels**, with an
  **"other" entry** per level — together these give the **Sum invariant**.
- The **CROSS platform** stores **Contracts** and data and runs the lifecycle
  (**Draft → Active ⇄ Suspended → Retired**).
- The **Registry** reads **Variables** from the platform; the **Client** is the write
  path. **Data providers** write, **Data consumers** read.
- A **Data Resource** is a **Contract** + a **Data specification**; a **Data Package**
  bundles many **Data Resources** for distribution.
- The **Release adapter** consumes a **Release spec** (a **CrossDataPackageReleaseSpec** + many
  **CrossDataResourceReleaseSpec**) and a **Registry**, fetches each **Variable**'s data and **Contract**
  through a **ContractResource**, and emits a Frictionless **Data Package** (zip) — overriding
  contract metadata per resource and authoring package metadata wholesale.
- A **Build spec** names one or more **Variables** and an ordered list of
  **Transformations** per variable; each kind of **Build spec** permits its own subset of
  **Transformations**. A **Transformation** touches tabular data only — never
  **Contracts**, **Schema**, or **Dimensions**.

## Example dialogue

> **Consumer:** "I pulled the emissions **Variable** and summed it by region — can I
> trust the national total if some rows are at city level and some at country level?"
> **Domain expert:** "Yes. Region is a hierarchical **Dimension**, so the **Sum
> invariant** holds — every leaf rolls up to exactly one parent, and anything
> uncategorised lands in the **`other` entry**. Mixed levels still sum correctly."
> **Consumer:** "And the scenario column?"
> **Domain expert:** "That's a **FlexibleDimension** — flat, no hierarchy. You can group
> by it but there's nothing to roll up, so don't sum *across* scenarios."

## Flagged ambiguities

- **`use_titles` is a misnomer.** The registry's `use_titles=True` swaps in **labels**
  (via `label_map`), not **titles**. In our language a **title** belongs to a
  **Contract**, a **label** to a **Dimension member** — the parameter crosses that line.
  Conceptually it is "use_labels"; renaming is a separate code decision.
- **"Variable" was overloaded.** Resolved: **Variable** = the dataset concept,
  **ValueVariable** = the contract type that declares it, and the registry's runtime
  object is just the in-memory handle to a Variable — not a third meaning.
- **"Dimension" — umbrella vs. strict.** Resolved: "Dimension" unqualified means the
  strict hierarchical form; **FlexibleDimension** is the flat sibling. Both share a
  common base, but the default meaning is the hierarchical one.
- **Dimension schema on release egress — resolved.** The **Release adapter** fetches every
  **Contract** through the **Registry**, i.e. through the trusted-source path
  (`from_server`), which strips and regenerates a **Dimension**'s rigid schema from its
  template. The adapter embeds *that* trusted schema directly, so the old `from_contract`
  round-trip — which fed a materialized dimension schema back through the constructor and
  tripped the rigidity guard — never happens on this path. The rigidity guard remains a
  **feature** on ingest; do not loosen it.
- **`ContractResource` vs `CrossDataResource` — resolved.** One word apart, two layers:
  **`ContractResource`** is the **Registry**/**Client** per-contract fetch handle (wraps a
  **Contract**, exposes `get_data()`) and is untouched by release work; `CrossDataResource`
  was the bespoke release descriptor and is **retired** (the **Release adapter** emits a
  **Frictionless descriptor** instead). When someone says "the release resource", they mean
  the Frictionless resource descriptor, never the fetch handle.
- **"spec" was overloaded.** Resolved: a single **Transformation** is *not* "a spec"; the
  declarative manifest that lists variables and transformations is a **Build spec**
  (data-package spec, plot spec). Unqualified "spec" is banned because it also collides
  with **Data specification** (the file-binding part of a **Data Resource**).
- **"registry" for transformation dispatch — not a Registry.** When transformations were
  proposed, "registry" was meant only in the dict/dispatch-pattern sense, not the domain
  **Registry** (`CrossRegistry`, the read layer). Resolved: there is no transformation
  "registry"; each **Build spec** holds a discriminated union of **Transformation** models
  that dispatch on a `type` tag (the same discriminator key as the `fields/` and `schema/`
  unions). The word **Registry** stays reserved for `CrossRegistry`.
