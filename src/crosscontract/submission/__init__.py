"""Executing submission contracts.

Reads a delivered bundle, splits it into the rows of each target, and validates
those rows against the contracts the targets name. The submission contract and
its extraction instructions are defined in `crosscontract.contracts.submission`;
`SubmissionContract` is re-exported here.

The readers and `SubmissionHandler` run offline. `CrossSubmitter` is the
exception: it holds a connection to the CROSS platform and composes the others
into a single validation of a delivered bundle.
"""

from crosscontract.contracts.submission import SubmissionContract
from crosscontract.exceptions import TargetValidationError, UnclaimedRowsError
from crosscontract.handlers import (
    SubmissionHandler,
    read_excel_bundle,
    read_excel_bundle_bytes,
)

from .submitter import CrossSubmitter

__all__ = [
    "CrossSubmitter",
    "SubmissionContract",
    "SubmissionHandler",
    "TargetValidationError",
    "UnclaimedRowsError",
    "read_excel_bundle",
    "read_excel_bundle_bytes",
]
