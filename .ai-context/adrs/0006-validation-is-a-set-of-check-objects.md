# Validation is a set of check objects, derived in one place

A **Check** is an object: a pydantic model holding what it needs, callable on a
DataFrame, able to render itself as one or more `pa.Check`s. `PanderaAdapter._derive_checks`
is the only place that turns a **Schema** into checks, and it takes the **Existing values**
as optional arguments, so the same derivation serves a bare conversion and a full
**Data validation**. See the *Validation* section of [CONTEXT.md](../CONTEXT.md) for the
terms.

This replaces three differently-shaped, differently-gated blocks in the old adapter, each
building a `pa.Check` around a closure that delegated back to a module-level helper.

## Why base checks name mechanics, not meanings

`IsUnique(columns)`, `IsIn(columns, existing)` — not `PrimaryKeyUniqueness`. The evidence
is in the schema: `fields/base.py` carries a `unique: bool` constraint, so a single-column
unique constraint and a multi-column primary key are the same rule at different arities. A
name like `PrimaryKeyUniqueness` would either duplicate that logic or lie about half its
uses. What a rule *means* on a particular schema is a `label` supplied at derivation.

Negation is a second class, not a flag: `IsIn` and `IsNotIn` rather than
`IsIn(expected=False)`. The two are not exact complements once nulls are in play, and a
flag would leave two opposite rules sharing one `name` — which is the discriminator when
checks are read from a specification, so it has to name the rule.

## Why composites may name a meaning, and a foreign key is not one

`IsValidPrimaryKey` is `IsNotNull` and `IsUnique` and `IsNotIn` taken together, and it is
allowed to say so. The test is whether the sub-rules produce distinct, actionable
messages: for a primary key they do — "not unique" and "already exists" are different
problems, fixed differently — and `to_pandera()` returns a *list* precisely so each is
reported as itself rather than as one opaque `PrimaryKeyError`.

A foreign key fails that test. "Value not in the referenced set" is one message, and a
null row passing is not a failure to report, so it is a single base check,
`IsSubsetOf(columns, allowed, within)`, carrying the SQL `MATCH SIMPLE` semantics itself.
It is a sibling of `IsIn` rather than an extension: a general-purpose membership check
where nulls silently pass is a trap for whoever reaches for one next.

## Why one derivation, and why it sits in the adapter

An earlier design had two lists — checks the schema requires, and checks the caller
supplies carrying existing values — merged by rule so the informed one replaced the
uninformed one. It needed an identity function to recognise "the same rule", and getting
that wrong was silently harmful: a self-reference whose parent was already stored failed
the schema-derived check while passing the caller's, because "parent is in this frame" is
*unsound* once data arrives in batches, not merely weaker.

One derivation taking optional values removes the problem rather than solving it. There is
one check per schema construct, carrying whatever information reached it, so nothing needs
reconciling and no identity is required. A caller supplies **values, never checks**.

It lives in the adapter rather than on `TableSchema` because that leaves one dependency
edge (`schema → adapter → checks`) instead of two, keeps `TableSchema` a description of a
table, and puts all pandera knowledge behind one door. Deriving *a primary key implies a
uniqueness check* is conversion, not deciding.

For the same reason there is no `IsSubsetOf.from_foreign_key`: it would make `checks/`
import from `contracts/schema/reference/`, and that package depends on nothing but pandas,
pandera and pydantic. `checks/` knows *how* to check; the adapter knows *which* checks and
*which values*.

## Why the key checks are opt-in

`None` for a group of values means "do not check this"; an empty collection means "check
it, with nothing to compare against". So `validate_dataframe(df)` checks column
constraints and, for a **Dimension**, the hierarchy — but not the primary key and not the
foreign keys.

This **reverses** the goal the design started from, which was that checks needing nothing
from outside the data should be impossible to switch off. What survives is narrower: the
caller can no longer *weaken* a check it has asked for — supplying values adds strictness
and never removes any — but it can decline to ask.

The cost is real and worth stating: `to_pandera_schema()` called bare returns a schema
that permits duplicate keys, and `BaseContract.validate_data(df)` with no resolver
validates types and dimension structure only. Whoever wants the key checked must say so,
including when there is nothing stored to compare against.

## Why a check is identified by its failure message

Pandera puts exactly one string per check into `failure_cases`: the `error` if one is set,
the check's name otherwise. There is no room for a human message *and* a machine-readable
tag, so `failure_message()` carries the identification, and `SchemaValidationError` parses
the columns back out of it to collapse a violation into one row. That coupling is
acknowledged rather than liked — see
[validation-reporting.md](../prds/validation-reporting.md).

## Consequences

- **An unchecked external reference is silent.** With no supplied values a foreign key
  naming another contract yields no check, and the frame validates exactly like one where
  the reference held. This retires the `ValueError` that
  [ADR 0005](0005-one-contract-resolver-supplies-definitions-and-values.md) kept.
- **One mistake, one message.** Where two rules could both fire on one defect, the rule
  that does not own it stays silent: a dimension row naming no parent is in no sibling
  group, so the catch-all rule has nothing to ask of it and `NonRootElementHasParent`
  reports the missing parent alone.
- **The ported dimension rule changed behaviour once.** `_check_other_entries` wrote its
  grouped answer back over every non-root row and raised `ValueError` on a parentless
  child. It now passes those rows, per the point above.
- **`checks/` is reusable beyond pandera.** The predicate is `__call__(df) -> pd.Series`;
  `to_pandera()` is one rendering of it.
