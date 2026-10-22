# WP4 — `CrossSubmitter.submit_file`

## Context
**Part of:** GitHub issue #119 (body, discussion summary, and the 2026-10-22 update comment)

A data provider submits a bundle straight from a file instead of reading it into a
DataFrame first, so the file is read the same way the platform reads it. The file is
read into the bundle and handed to `submit`, so it is always uploaded as parquet.

## Acceptance Criteria
- [ ] `CrossSubmitter.submit_file(name, path, ...)` chooses the reader by file extension,
      case-insensitively: `.csv` → the CSV path reader, `.parquet` → the parquet path
      reader, `.xls/.xlsx/.xlsm/.ods` → `read_excel_bundle` with the fetched submission
      contract.
- [ ] Any other extension raises `ValueError` naming the accepted extensions, before
      anything is read or fetched.
- [ ] It delegates to `submit`; it neither validates nor uploads anything itself.
- [ ] A `FileReadError` from a reader propagates, and nothing is uploaded.
- [ ] Docstring with `Args:`, `Returns:` and `Raises:` (including `FileReadError`,
      `FileNotFoundError`, and the `ValueError` for an unsupported extension, plus what
      `submit` raises).
- [ ] Tests mock `submit` and check that it receives each format's frame; an unsupported
      extension raises; a read failure uploads nothing.

## Implementation Details
- Files to modify:
  - `src/crosscontract/services/submitter/submitter.py`
  - `src/tests/services/submitter/test_submitter.py`
- Signature: mirror `submit` with `path: str | Path` in place of `df`; settle before
  implementing whether `filename` and `validate` pass through to `submit`.
- Excel needs the contract: `self._client.submissions.get(name).contract`. Decide before
  implementing whether the extra fetch (on top of the one in `submit`) is acceptable.
- Import the readers from `crosscontract.handlers`; `services/` may import `handlers/`.
- The extension dispatch stays local to `submit_file`; sharing it with cross_back is out
  of scope.
- Dependencies: after 02-csv-parquet-readers.md and 03-excel-file-read-error.md.
