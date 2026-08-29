# One Contract resolver supplies both definitions and stored values

Validating data against a **Contract** needs things the contract cannot know by itself:
what the contracts it references look like, and which values are already stored. Both
are supplied by a single `ContractResolver` protocol carrying `resolve` and `get_data`,
and `BaseContract.validate_data` owns the derivation of *what* to ask for. See the
*Validation* section of [CONTEXT.md](../CONTEXT.md) for the terms.

## Why one protocol and not two

Splitting it — a `resolve`-only protocol for **Reference validation**, a `get_data`-only
one for **Data validation** — was considered and rejected. The two lookups are one job
seen twice: a contract cannot answer anything about the world outside itself, and these
are the two things it needs to ask. Two protocols would name the split rather than the
concept, and every real implementor carries both members anyway.

The cost is accepted and visible: `validate_references` now asks for a `get_data` it
never calls, and test doubles grow a stub. In exchange there is one name for one idea,
and one class per environment to implement it.

## Why the derivation lives in the library

Building the values to check against takes three lines of schema knowledge — the target
is `fk.reference.resource or self.name`, the columns to read are `fk.reference.fields`,
and the result is keyed by `tuple(fk.fields)`. Confusing the referring fields with the
referenced ones is **silently wrong rather than a crash**, so this knowledge must not be
copy-pasted into every consumer. It existed twice already and submission would have been
the third.

Two consequences follow:

- **The library re-orders what it gets back.** Referring and referenced fields correspond
  by position, but a returned frame's column order is whatever the supplier chose, so
  `validate_data` reindexes by the requested columns before building tuples. Without it a
  composite foreign key can compare `(a, b)` against `(b, a)` and reject every row —
  silently, and only for composite keys.
- **`validate_data` sits on the contract, not the schema.** The primary key lookup targets
  the contract's own table, and a self-referencing foreign key does too. A schema has no
  name, so only a contract can drive a resolver.

## Why the protocol says nothing about access control

`get_data` places no obligation on how an implementation resolves permissions, and the
protocol docstring makes no claim about it either.

An earlier draft required implementations to return the stored rows *irrespective of the
caller's read permissions*, on the grounds that a key occupies its name whoever owns it.
The observation is true, but it is not an obligation this package can state. Access
control is not the resolver's subject: each implementation reads through whatever its
environment allows — `ClientContractResolver` issues an HTTP read and the CROSS platform
answers it or returns a permission error, a server-side resolver reads its database
directly — and this package has no notion of the access model behind either, nor should
it acquire one. Requiring something it cannot express, enforce, or test would have put a
promise in the docstring that one of its two implementations does not keep.

The consequence is accepted: a **Data validation** run through the client sees what the
caller can read, so it is advisory. The platform re-validates on ingest, which is where
the guarantee lives.

## Why the flags name the stored-value half

`validate_data` takes `check_existing_primary_key` and `check_existing_foreign_key`,
both defaulting to `False`, rather than the `skip_primary_key_validation` /
`skip_foreign_key_validation` pair used one layer down.

An earlier draft kept the negative names with `False` defaults, and the two defaults
contradicted each other: "do not skip foreign keys" with no resolver raises for every
contract with an external reference — that is, for **ValueVariable**, the main contract
type in the model. The positive polarity fixes that at the name instead of at the
exception. A caller reading their own call site can see what they did *not* ask for, so
a weaker validation is no longer a silent one.

`cross_back` already named it this way and inverted at the boundary; that inversion goes
away.

## Why the resolver is optional

`BaseContract` exists for use outside the CROSS platform, where there is nothing to pass.
Requiring a resolver would make the method unusable for the audience the class exists to
serve. Requesting a check without one raises, naming the contract and both remedies.

A null-object resolver returning empty frames is **not** a substitute: an empty result
means the referenced table exists and holds no rows, which fails every referring row.
`None` is the only safe way to say "I have no source".

## Why `None` and `[]` differ, for external foreign keys only

Three states, and only one combination is an error:

| supplied values | meaning |
|---|---|
| absent, external reference | cannot validate — raises |
| absent, self-reference | validate against the data's own rows |
| empty list | the referenced table exists and is empty — every non-null row fails |

An empty referenced table is a *validation result*, not an inability. For a primary key
the distinction does not arise: no stored keys and an empty set of them both leave
uniqueness to be checked within the data.

## Why a Protocol with `@abstractmethod`, not an ABC

Real implementors inherit the protocol, so a missed method fails when the class is
constructed rather than as an `AttributeError` deep inside validation at
data-submission time. Test doubles satisfy it structurally and skip the base class. An
ABC would force the doubles to inherit too; a plain Protocol would let a stale subclass
inherit an empty body and return `None`. Only the combination gives both.

## Consequences

- **`ContractResolver` is public API**, exported from `crosscontract.contracts`. It was
  reachable only by full module path before, which is what made adding `get_data` cheap.
  Changing it again is a breaking change for implementors outside this repository.
- **Real implementors inherit.** `ClientContractResolver` and `cross_back`'s
  `DbContractResolver` both subclass the protocol; this is the convention, not an
  accident of history.
- **The client fetches nothing by default.** `ContractResource.validate_dataframe` passes
  both flags as `False`, so the ordinary path makes no network call. The platform
  re-validates on ingest. Its parameters carry the same names as the library's, so the
  two speak one vocabulary.
- **Bridging async to a synchronous `get_data` is the implementor's problem.** This
  package has no `async def` and stays that way; how a server reaches its database from
  a synchronous method is not this protocol's concern.
- **Internal consistency is not yet unconditional.** A `False` flag currently suppresses
  the whole check rather than only its stored-value half, so uniqueness within the data
  and self-referencing foreign keys go unchecked on the default path. This matches the
  client's previous behaviour, so nothing regressed — but the flag *names* promise more
  than the validator delivers. Closing that gap is a change to the validator and is
  planned separately; see the handoff notes in
  [validation-architecture.md](../prds/validation-architecture.md).
