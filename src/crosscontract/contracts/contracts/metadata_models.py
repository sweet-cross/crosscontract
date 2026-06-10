from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, model_validator

ContributorRoles = Literal["author", "maintainer", "contributor"]


class Contributor(BaseModel):
    """
    A contributor to the data contract.

    Attributes:
        title (str): The name of the contributor.
        email (str | None): The email address of the contributor.
        path (str | None): A URL to the contributor's profile or homepage.
        role (str | None): The role of the contributor ("author", "maintainer",
            "contributor").
            Defaults to "contributor" if not specified.
        organization (str | None): The organization the contributor is affiliated with.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(description="The name of the contributor.")
    email: EmailStr | None = Field(
        default=None, description="The email of the contributor."
    )
    path: HttpUrl | str | None = Field(
        default=None, description="A URL to the contributor's profile or homepage."
    )
    role: ContributorRoles = Field(
        default="contributor",
        description=(
            "The role of the contributor. Possible values: "
            "author, maintainer, contributor."
        ),
    )
    organization: str | None = Field(
        default=None, description="The organization the contributor is affiliated with."
    )


class DataSource(BaseModel):
    """
    A data source for the data contract.

    Attributes:
        title (str): The name of the data source.
        path (str | None): A URL or file path to the data source.
        email (str | None): The email address of the data source contact.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(description="The name of the data source.")
    path: HttpUrl | str | None = Field(
        default=None, description="A URL or file path to the data source."
    )
    email: EmailStr | None = Field(
        default=None, description="The email of the data source contact."
    )


class License(BaseModel):
    """
    A license for the data package or resource.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(
        default=None,
        description=(
            "MUST be an Open Definition license identifier (e.g., 'CC-BY-4.0')."
        ),
        pattern=r"^([-a-zA-Z0-9._])+$",
    )

    path: HttpUrl | str | None = Field(
        default=None,
        description=(
            "A fully qualified URL, or a POSIX file path to the license text."
        ),
    )

    title: str | None = Field(
        default=None, description="A human-readable title for the license."
    )

    @model_validator(mode="after")
    def check_name_or_path(self) -> Self:
        if not self.name and not self.path:
            raise ValueError(
                "A License object must contain at least a 'name' or a 'path' property."
            )
        return self
