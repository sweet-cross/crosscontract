"""Submission contracts and the instructions for extracting variables from them.

The ingress mirror of `release/`: that package turns contracts into a published
data package, this one describes a delivered bundle and how it is split back
into per-variable contracts. Both own their spec models and the code that
executes them, so the concept lives in one place.

The contracts, the extraction instructions and the handler that carries them
out all run offline. `CrossSubmitter` is the exception: it holds a connection
to the CROSS platform and composes the others into a single validation of a
delivered bundle.
"""

from .exceptions import TargetValidationError, UnclaimedRowsError
from .submission_contract import SubmissionContract
from .submission_handler import SubmissionHandler
from .submitter import CrossSubmitter

__all__ = [
    "CrossSubmitter",
    "SubmissionContract",
    "SubmissionHandler",
    "TargetValidationError",
    "UnclaimedRowsError",
]
