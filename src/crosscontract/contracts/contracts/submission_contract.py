"""A submission contract is a CrossContract that describes a file with
several variables included and holds the respective extraction information
as well as information how to validate the variables"""

from typing import Literal

from pydantic import Field

from . import BaseContract, CrossMetaData


class SubmissionContract(BaseContract, CrossMetaData):
    contract_type: Literal["Submission"] = Field(
        default="Submission", description="Type of the contract."
    )

    project_name: str = Field(
        ...,
        description="The name of the project associated with the submission.",
    )

    extraction: ExtractionInstructions
