"""Validating and submitting delivered bundles on the CROSS platform.

`CrossSubmitter` is the data provider's entry point: name a submission contract
stored on the platform, and it validates a delivered bundle against it or
submits the bundle. `Submission` is what a submission returns.

Everything needed to work offline is re-exported here as well:
`SubmissionContract`, `SubmissionHandler` (validate a bundle against a local
contract with `SubmissionHandler(contract, df).validate_submission(resolver)`),
the Excel bundle readers, and the exceptions a validation raises.
"""

from crosscontract.contracts.submission import SubmissionContract
from crosscontract.crossclient import Submission
from crosscontract.exceptions import TargetValidationError, UnclaimedRowsError
from crosscontract.handlers import (
    SubmissionHandler,
    read_excel_bundle,
    read_excel_bundle_bytes,
)

from .submitter import CrossSubmitter

__all__ = [
    "CrossSubmitter",
    "Submission",
    "SubmissionContract",
    "SubmissionHandler",
    "TargetValidationError",
    "UnclaimedRowsError",
    "read_excel_bundle",
    "read_excel_bundle_bytes",
]
