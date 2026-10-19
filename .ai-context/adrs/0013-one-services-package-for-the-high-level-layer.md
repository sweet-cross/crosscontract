# One services/ package holds the high-level layer; the Registry becomes the Reader

The three top-level packages that present the CROSS platform to a user move into one
package, `crosscontract/services/`, with one subpackage per job:

| Before | After | Holds |
|---|---|---|
| `registry/` | `services/reader/` | `CrossReader` (formerly `CrossRegistry`) and its variables |
| `submission/` | `services/submitter/` | `CrossSubmitter` |
| `release/data_package/` | `services/package_creator/` | `create_data_package` |

The read layer is renamed: the class is `CrossReader`, and the domain term is **Reader**.
`CrossRegistry` stays as a plain subclass, `class CrossRegistry(CrossReader)`, with no
behaviour of its own. Its deprecation warning comes separately (#132).

The top level now reads `contracts/`, `transformations/`, `exceptions/`, `handlers/`,
`crossclient/` and `services/`, and the import graph ends `… ← crossclient ← services`.

## Why

After ADRs 0010–0012 the lower layers were clear, but the high-level layer was still spread
over three top-level packages that all do the same job: stand on a `CrossClient` and serve
one kind of work. Collapsing them keeps the top level small and puts every user-facing
entry point in one place.

**The name `services`.** It says "the things a user calls to get work done". It collides
with `crossclient/services/`, but users never import that path: they reach it as
`client.contracts` and `client.submissions`. The collision is documented in CLAUDE.md, and
code names the full path. Rejected: `access` (already means something else to the team),
`workers` (reads as concurrency), `workflows` (inaccurate), `managers` (a vague term that
also clashes with context managers), `api` / `client` (suggest HTTP), `platform` (already
means the server).

**Folders named after their role object.** `reader/`, `submitter/`, `package_creator/`.
Calling the submitter folder `submitter` rather than `submission` cuts the packages named
`submission` from four to three. `package_creator` leaves room for `create_data_package` to
become a class later.

**`CrossReader`, with `CrossRegistry` as its subclass.** "Registry" no longer fits once the
package holds more than the read side, and "reader" says what the class does: it returns
data frames. The new name holds the implementation, so removing the old name later only
deletes the subclass. Because `CrossRegistry` is a `CrossReader`, an old object still
satisfies a `CrossReader` hint. `CrossViewer`, after the backend's Viewer role, was rejected:
"viewer" suggests visualization, and the classes name jobs, not permissions.

## Consequences worth knowing

- **Deep import paths break, with no shims.** `crosscontract.registry`,
  `crosscontract.submission` and `crosscontract.release` are gone. The root keeps every
  name it exported before and adds `CrossReader`.
- **The re-exports are gone.** `crosscontract.submission` used to re-export
  `SubmissionContract`, `SubmissionHandler`, the Excel readers and the exceptions. The
  release packages used to re-export both release specs. Each `services/` subpackage now
  exports only its own names; the others come from their home packages
  (`contracts`, `handlers`, `exceptions`, `crossclient`) or from the root.
- **`create_data_package` is not exported from the root.** Import it from
  `crosscontract.services`. Its first parameter keeps the name `registry` and is typed
  `CrossReader`.
- **Nothing imports `services/`** except the root `__init__.py`. Inside it,
  `package_creator/` imports `reader/`.
- **Older ADRs keep the old paths.** ADRs 0003, 0007 and 0010–0012 name `registry/`,
  `submission/` and `release/` as they were when written.
