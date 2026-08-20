from typing import Literal

from pydantic import Field

from ..schema import TableSchema


class SubmissionSchema(TableSchema):
    table_type: Literal["Submission"] = Field(  # type: ignore[assignment]
        default="Submission",
        description="Type of the table determines the structure of the schema.",
        exclude=True,
        repr=False,
    )
    pass
