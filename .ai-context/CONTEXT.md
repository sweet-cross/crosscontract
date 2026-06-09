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
constraints, and the primary/foreign keys. Frictionless-table-standard based, extended
with **Field descriptors**. Describes logical content only, independent of file format.

**BaseContract** vs **CrossContract**:
A **BaseContract** is the minimal contract (name + schema) for use *outside* the CROSS
platform — bilateral exchange or another platform. A **CrossContract** is the full
CROSS-platform contract, adding the CROSS metadata. "Contract" unqualified means the
concept; reach for these names only when the platform boundary matters.

**Field descriptor**:
Extra semantic information attached to a **Schema** field beyond its type and
constraints — e.g. unit information — enriching the Frictionless standard.

**Contract type**:
The kind of a **Contract**, fixing the shape of its **Schema**: **ValueVariable**,
**Dimension**, **FlexibleDimension**, or **General**.

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

## Relationships

- A **Contract** is **Metadata** + **Schema**, and has exactly one **Contract type**.
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
