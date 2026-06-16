from typing import Literal

from pydantic import ConfigDict, EmailStr, Field

from ..._standards.frictionless import Contributor as FLContributor
from ..._standards.frictionless import License as FLLicense
from ..._standards.frictionless import Source as FLSource

ContributorRoles = Literal["author", "maintainer", "contributor"]


class Contributor(FLContributor):
    """
    A contributor to the data contract.

    Attributes:
        title (str): The name of the contributor.
        email (EmailStr | None): The email address of the contributor.
        path (str | None): A URL to the contributor's profile or homepage.
        role (ContributorRoles): The role of the contributor ("author",
            "maintainer", "contributor"). Defaults to "contributor" if not specified.
        organization (str | None): The organization the contributor is affiliated with.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    email: EmailStr | None = Field(
        default=None, description="The email of the contributor."
    )
    path: str | None = Field(
        default=None, description="A URL to the contributor's profile or homepage."
    )
    role: ContributorRoles = Field(
        default="contributor",
        description=(
            "The role of the contributor. Possible values: "
            "author, maintainer, contributor."
        ),
    )


class Source(FLSource):
    """
    A data source for the data contract.

    Attributes:
        title (str): The name of the data source.
        path (str | None): A URL or file path to the data source.
        email (EmailStr | None): The email address of the data source contact.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(description="The name of the data source.")
    path: str | None = Field(
        default=None, description="A URL or file path to the data source."
    )
    email: EmailStr | None = Field(
        default=None, description="The email of the data source contact."
    )


class License(FLLicense):
    """
    A license for the data package or resource.

    Attributes:
        name (str | None): An Open Definition license identifier (e.g., "CC-BY-4.0").
        path (str | None): A URL or file path to the license text.
        title (str | None): A human-readable title for the license.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    path: str | None = Field(
        default=None, description="A URL or file path to the license text."
    )
