"""Submission contracts and the instructions for extracting variables from them.

The ingress mirror of `release/`: that package turns contracts into a published
data package, this one describes a delivered bundle and how it is split back
into per-variable contracts. Both own their spec models and the code that
executes them, so the concept lives in one place.
"""

from .exceptions import TargetValidationError
from .submission_contract import SubmissionContract
from .submission_handler import SubmissionHandler

__all__ = ["SubmissionContract", "SubmissionHandler", "TargetValidationError"]
