# The Submitter is the provider-side mirror of the Registry

`CrossSubmitter` is the **Data provider**'s entry point to the CROSS platform, the mirror
of `CrossRegistry` on the write side: constructed from credentials (or a `CrossClient`),
it builds its own `CrossContractResolver` and turns a **Submission contract** plus a
delivered bundle into a complete **Submission validation** in one call — and, once the
platform offers the endpoint, into a submission. It lives in `submission/`, not in
`crossclient/`. See the *platform and its access layers* and *Submission and extraction*
sections of [CONTEXT.md](../CONTEXT.md) for the terms.

## Why it is not on the Client, and not on the Registry

The **Registry** is read-only, so the write path does not belong there. The **Client** is
the layer *beneath* this one: `CrossSubmitter` consumes a `CrossClient` exactly as
`CrossRegistry` does, and a `crossclient/services/` home would have inverted that. What
the two high-level layers have in common is that each serves one role over one Client —
**Data consumer** and **Data provider**.

This is also why it is not called `SubmissionClient`, the name it was proposed under:
CONTEXT.md fixes **Client** as the lower-level access layer, and the `Submission*` prefix
already names the *offline* concepts — `SubmissionContract`, `SubmissionHandler` — every
one of which runs with no platform connection. `CrossSubmitter` groups it with
`CrossClient` and `CrossRegistry`, which is where the connected things live.

## Why it lives in submission/ anyway

The obvious symmetry pointed the other way. On the egress side `registry/` is connected
and `release/` is offline and takes a registry as an argument; the ingress mirror of that
would be a top-level `submitter/` package beside an untouched, offline `submission/`.
That was rejected as a package existing for one slim class, when `submission/` already
names the concept.

The cost is accepted and worth stating, because it is invisible from the code: every
other domain package (`contracts/`, `release/`, `transformations/`) is free of
`crossclient`, and `submission/` is now the one that is not. Importing it pulls in
`httpx`. Renaming the package to `submitter/` was considered and judged not worth the
churn. `SubmissionHandler` remains offline as a *class*, and its tests must stay free of
HTTP — that property is now a convention rather than something the package layout
enforces.

## Consequences worth knowing

- **The submitter validates nothing itself.** Step 1 of a **Submission validation** is an
  ordinary `validate_data` on the **Submission contract**; step 3 is
  `SubmissionHandler.validate_targets`. The submitter sequences them and owns the policy
  between: a failed bundle stops the run, and step 2 — **Unclaimed rows** — raises
  `UnclaimedRowsError`. The handler continues to report and never act, which is what
  keeps the still-open contested-rows question answerable on the same principle.
- **Extraction runs on the bundle as delivered, never on the coerced frame** returned by
  step 1. `submit` uploads the original bundle and the platform re-runs extraction on it,
  so a local pass over a locally-coerced frame would answer a question about data the
  platform never sees. Coercion can also change routing, since **Target** filters match a
  column's string form.
- **`check_existing_primary_key` and `check_existing_foreign_key` default to `True`
  here**, against the `False` used everywhere else in the package. Those defaults exist
  because a **Contract resolver** is optional elsewhere; on the submitter one always
  exists, so the justifying condition is absent. It matters: a `False`
  `check_existing_primary_key` suppresses primary-key uniqueness *entirely*, not merely
  its stored-value half, and a one-call "is my bundle OK?" that skips key checks does not
  keep the promise the class makes.
