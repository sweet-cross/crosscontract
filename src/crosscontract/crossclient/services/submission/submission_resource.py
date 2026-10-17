from datetime import UTC, datetime
from io import BytesIO
from typing import TYPE_CHECKING, Any

import pandas as pd

from crosscontract.contracts.submission import SubmissionContract
from crosscontract.handlers.submission import SubmissionHandler

from ..contract import CrossContractResolver
from .schemas import Submission, SubmissionContractEntryPayload

if TYPE_CHECKING:  # pragma: no cover
    from .submission_service import SubmissionContractService


class SubmissionContractResource:
    """A handle to a submission contract that exists on the CROSS platform.

    Produced by the service's `create` and `get`; not constructed directly.
    Its properties are read-only and change only through its methods.
    `validate_submission` checks a delivered bundle against the stored
    submission contract.

    Attributes:
        name (str): The name of the submission contract.
        project_name (str): The name of the project owning the submission
            contract.
        title (str): The title of the submission contract.
        description (str): The description of the submission contract.
        tags (list[str]): The tags of the submission contract.
        allow_submissions (bool): Whether the owning project may currently
            upload submissions.
        contract (SubmissionContract): The stored submission contract.
    """

    def __init__(
        self,
        service: "SubmissionContractService",
        payload: SubmissionContractEntryPayload,
    ):
        """Initialize from a parsed server payload.

        Use `from_response` to build a resource from a raw response dict.

        Args:
            service (SubmissionContractService): The service the resource
                delegates its methods to.
            payload (SubmissionContractEntryPayload): The parsed server response.

        Raises:
            pydantic.ValidationError: If `payload.contract` is not a valid
                `SubmissionContract`.
        """
        self._service = service
        self._name = payload.name
        self._project_name = payload.project_name
        self._allow_submissions = payload.allow_submissions
        self._contract = SubmissionContract.model_validate(payload.contract)

    @classmethod
    def from_response(
        cls,
        service: "SubmissionContractService",
        response_json: dict[str, Any],
    ) -> "SubmissionContractResource":
        """Build a resource from a raw server response dict.

        Args:
            service (SubmissionContractService): The service the resource
                delegates its methods to.
            response_json (dict[str, Any]): The response body of a read of one
                submission contract.

        Returns:
            SubmissionContractResource: The resource.

        Raises:
            pydantic.ValidationError: If the response or its `contract` is
                malformed.
        """
        payload = SubmissionContractEntryPayload.model_validate(response_json)
        return cls(service, payload)

    @property
    def name(self) -> str:
        """Return the name of the submission contract.

        Returns:
            str: The name of the submission contract.
        """
        return self._name

    @property
    def project_name(self) -> str:
        """
        Returns:
            str: The name of the project owning the submission contract.
        """
        return self._project_name

    @property
    def title(self) -> str:
        """
        Returns:
            str: The title of the submission contract.
        """
        return self._contract.title

    @property
    def description(self) -> str:
        """
        Returns:
            str: The description of the submission contract.
        """
        return self._contract.description

    @property
    def tags(self) -> list[str]:
        """
        Returns:
            list[str]: The tags of the submission contract.
        """
        return self._contract.tags

    @property
    def allow_submissions(self) -> bool:
        """
        Returns:
            bool: Whether the owning project may currently upload submissions.
        """
        return self._allow_submissions

    @property
    def contract(self) -> SubmissionContract:
        """
        Returns:
            SubmissionContract: The stored submission contract.
        """
        return self._contract

    def __setattr__(self, name, value):
        # 1. Access the class to find the attribute definition
        # We use type(self) to avoid triggering infinite recursion or property getters
        attr = getattr(type(self), name, None)

        # 2. Check if the attribute is a property and if it has no setter
        if isinstance(attr, property) and attr.fset is None:
            raise AttributeError(
                "SubmissionContractResource is read-only. Use the methods to "
                "update properties."
            )

        # 3. If it's not a read-only property, allow the default behavior
        # This allows setting private variables like self._x = 10
        super().__setattr__(name, value)

    def __repr__(self) -> str:
        return (
            f"SubmissionContractResource(name={self.name}, "
            f"allow_submissions={self.allow_submissions})"
        )

    def set_allow_submissions(self, allow: bool) -> None:
        """Open or close the submission contract for submissions.

        Closing it stops new uploads; submissions already received are still
        processed. Setting the value it already has changes nothing.

        Args:
            allow (bool): `True` to open the submission contract, `False` to
                close it.

        Raises:
            CrossClientError: If the request fails, e.g. `PermissionDeniedError`
                if the caller is not a manager of the contract's project.
        """
        self._service.set_allow_submissions(self.name, allow)
        self._allow_submissions = allow

    def delete(self) -> None:
        """Delete the submission contract from the CROSS platform.

        The data contracts its targets name are not affected.

        Raises:
            CrossClientError: If the request fails, e.g. `ResourceNotFoundError`
                if the submission contract no longer exists.
        """
        self._service.delete(self.name)

    def refresh(self) -> None:
        """Reload the submission contract from the CROSS platform.

        Raises:
            CrossClientError: If the request fails, e.g. `ResourceNotFoundError`
                if the submission contract no longer exists.
            ValueError: If the CROSS platform returns a submission contract of a
                different name.
        """
        remote = self._service.get(self.name)
        if remote.name != self.name:
            raise ValueError(
                f"Fetched contract name '{remote.name}' does not match "
                f"resource name '{self.name}'."
            )
        self._project_name = remote.project_name
        self._allow_submissions = remote.allow_submissions
        self._contract = remote.contract

    def submissions(self) -> list[Submission]:
        """Fetch every submission of this submission contract, oldest first.

        Returns:
            list[Submission]: The submissions.

        Raises:
            CrossClientError: If the request fails, e.g. `ResourceNotFoundError`
                if the submission contract no longer exists.
        """
        return self._service.list_submissions(self.name)

    def validate_submission(
        self,
        df: pd.DataFrame,
        check_existing_primary_key: bool = False,
        check_existing_foreign_key: bool = True,
        check_dimension_granularity: bool = True,
        lazy: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """Validate a delivered bundle against this submission contract.

        Runs `SubmissionHandler.validate_submission` on the stored contract,
        reading the target contracts and their stored values from the CROSS
        platform. The steps stop at the first failure; see that method for what
        each check covers. By default the stored primary keys are not checked,
        because a submission replaces the rows stored under its `replace_key`.
        Validation here is advisory: the platform validates a submission again
        on ingest and can still reject it.

        Args:
            df (pd.DataFrame): The bundle as delivered.
            check_existing_primary_key (bool): If True, also check each target's
                primary key against the values already stored for the contract
                it names, including the rows this submission would replace.
                Defaults to False.
            check_existing_foreign_key (bool): If True, also check each target's
                foreign keys against the values already stored for the contracts
                they reference. Defaults to True.
            check_dimension_granularity (bool): If True, also check that no
                ValueVariable target reports a dimension member alongside one of
                its descendants. Defaults to True.
            lazy (bool): If True, collect all of a step's validation errors and
                raise them together. If False, raise the first error
                encountered. Defaults to True.

        Returns:
            dict[str, pd.DataFrame]: The validated, coerced target data, keyed
                by target name.

        Raises:
            SchemaValidationError: The bundle does not satisfy the submission
                contract's own schema.
            UnclaimedRowsError: The bundle holds rows no target claims.
            TargetValidationError: At least one target's data failed, holding
                one entry per failing target.
            ValueError: A target names a contract that cannot be read.
            KeyError: A column named by a target's `filters` is absent from the
                bundle.
            CrossClientError: A read from the CROSS platform failed.
        """
        resolver = CrossContractResolver(self._service._client.contracts)
        return SubmissionHandler(self.contract, df).validate_submission(
            resolver=resolver,
            check_existing_primary_key=check_existing_primary_key,
            check_existing_foreign_key=check_existing_foreign_key,
            check_dimension_granularity=check_dimension_granularity,
            lazy=lazy,
        )

    def submit(
        self, df: pd.DataFrame, filename: str | None = None, validate: bool = True
    ) -> Submission:
        """Validate a delivered bundle, then upload it under this submission contract.

        The bundle is uploaded as a parquet file, exactly as handed in. With
        `validate=True` it is first checked by `validate_submission` with its
        defaults, and nothing is uploaded if any check fails. To validate with
        other settings, call `validate_submission` with the flags you need and
        then `submit(df, validate=False)`.

        Validation here is advisory: the CROSS platform validates the
        submission again on ingest and can still reject it. Processing on the
        platform is asynchronous; follow the returned submission's state with
        `SubmissionContractService.get_submission`.

        Args:
            df (pd.DataFrame): The bundle as delivered.
            filename (str | None, optional): The stem of the uploaded file;
                `.parquet` is appended. Defaults to `None`, which names the file
                after the submission contract and the UTC time of the upload,
                e.g. `my_contract_20261017124301.parquet`.
            validate (bool, optional): Whether to validate the bundle before
                uploading it. Defaults to `True`.

        Returns:
            Submission: The created submission, in state `received`.

        Raises:
            SchemaValidationError: The bundle does not satisfy the submission
                contract's own schema. Only with `validate=True`.
            UnclaimedRowsError: The bundle holds rows no target claims. Only
                with `validate=True`.
            TargetValidationError: At least one target's data failed. Only with
                `validate=True`.
            ValueError: A target names a contract that cannot be read. Only
                with `validate=True`.
            CrossClientError: A request to the CROSS platform failed, e.g.
                `PermissionDeniedError` if the caller may not submit to the
                contract's project.
        """
        filename = (
            f"{filename}.parquet"
            if filename is not None
            else (
                f"{self.contract.name}_{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}.parquet"
            )
        )
        if validate:
            self.validate_submission(df)
        buffer = BytesIO()
        df.to_parquet(buffer, index=False)
        buffer.seek(0)
        return self._service._upload_submission(self.contract.name, buffer, filename)
