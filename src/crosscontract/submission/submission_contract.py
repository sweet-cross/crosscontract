"""Contract type for submission bundles.

A submission bundle is a single file carrying several variables at once. The
contract describes that file, records how each variable is extracted from it,
and states how the extracted variables are validated.
"""

from typing import Literal

from pydantic import Field

from crosscontract.contracts.contracts import BaseContract, CrossMetaData


class SubmissionContract(BaseContract, CrossMetaData):
    """A contract describing a submitted file that bundles several variables.

    Unlike a variable contract, which describes one table, a submission contract
    describes the delivered file as a whole: the table it lands as, the project
    it belongs to, and (once implemented) the instructions for extracting each
    variable out of it.

    The submission bundle is a standard flat table, so `"Submission"` maps onto
    the `"General"` table type in `CONTRACT_TYPE_TO_TABLE_TYPE` rather than
    binding a schema class of its own.

    Attributes:
        name (str): A unique identifier for the contract. Inherited from
            `BaseContract`.
        title (str): A human-readable title for the submission.
        description (str): A human-readable description of the submission.
        tags (list[str]): Tags used for categorization and filtering.
        tableschema (TableSchema): The Frictionless Table Schema describing the
            submitted table.
        contract_type (Literal["Submission"]): Fixed discriminator identifying
            this contract type.
        project_name (str): The name of the project the submission belongs to.
    """

    contract_type: Literal["Submission"] = Field(
        default="Submission", description="Type of the contract."
    )

    project_name: str = Field(
        ...,
        description="The name of the project associated with the submission.",
    )

    # todo: inject the ExtractionInstructions model here once it is implemented
    # extraction: ExtractionInstructions
