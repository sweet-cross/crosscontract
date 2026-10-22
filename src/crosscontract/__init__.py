"""crosscontract package for data contracts and related utilities."""

from .contracts import (
    BaseContract,
    CrossContract,
    CrossDataPackageReleaseSpec,
    CrossDataResourceReleaseSpec,
    SchemaValidationError,
    TableSchema,
)
from .contracts.submission import SubmissionContract
from .crossclient import CrossClient, Submission
from .exceptions import TargetValidationError, UnclaimedRowsError
from .handlers import SubmissionHandler
from .services import CrossReader, CrossRegistry, CrossSubmitter

__version__ = "0.36.0"

__all__ = [
    "CrossClient",
    "CrossContract",
    "CrossDataPackageReleaseSpec",
    "CrossDataResourceReleaseSpec",
    "TableSchema",
    "BaseContract",
    "SchemaValidationError",
    "CrossReader",
    "CrossRegistry",
    "CrossSubmitter",
    "Submission",
    "SubmissionContract",
    "SubmissionHandler",
    "TargetValidationError",
    "UnclaimedRowsError",
]
