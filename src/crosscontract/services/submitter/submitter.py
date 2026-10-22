from pathlib import Path

import pandas as pd

from crosscontract.crossclient import CrossClient, Submission
from crosscontract.handlers import read_csv_file, read_excel_bundle, read_parquet_file

_EXCEL_EXTENSIONS = (".xls", ".xlsx", ".xlsm", ".ods")


class CrossSubmitter:
    """The data provider's entry point to the CROSS platform.

    The write-side counterpart of `CrossReader`, constructed the same way.
    Every method takes the name of a submission contract stored on the
    platform. To validate a local `SubmissionContract`, use
    `SubmissionHandler(contract, df).validate_submission(resolver)`; before
    creating it on the platform, `contract.validate_references(resolver)` also
    checks that every target's contract declares the `replace_key` columns.

    Validation performed here is advisory: it sees only what the calling user
    may read, and the platform re-validates on ingest.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        client: CrossClient | None = None,
    ):
        """Initialize the submitter from either a client or username/password.

        Args:
            username (str | None, optional): The username or email to connect to
                the CROSS platform. Ignored when `client` is given. Defaults to
                `None`.
            password (str | None, optional): The password to connect to the CROSS
                platform. Ignored when `client` is given. Defaults to `None`.
            client (CrossClient | None, optional): An existing client. When given
                it is used as-is, otherwise a new one is built from `username`
                and `password`. Defaults to `None`.

        Raises:
            ValueError: If no `client` is given and `username` or `password` is
                missing.
        """
        if client is None:
            if username is None or password is None:
                raise ValueError(
                    "Either a CrossClient instance or both username and password must "
                    "be provided."
                )
            client = CrossClient(username=username, password=password)

        self._client = client

    def submit(
        self,
        name: str,
        df: pd.DataFrame,
        filename: str | None = None,
        validate: bool = True,
    ) -> Submission:
        """Validate a delivered bundle, then submit it to the CROSS platform.

        Fetches the submission contract by `name` and uploads the bundle as a
        parquet file, exactly as handed in. With `validate=True` the bundle is
        first checked as by `validate_submission` with its defaults, and
        nothing is uploaded if any check fails. To validate with other
        settings, call `validate_submission` with the flags you need and then
        `submit(name, df, validate=False)`.

        Validation here is advisory: the platform validates the submission
        again on ingest and can still reject it. Processing on the platform is
        asynchronous; follow the returned submission's state with
        `client.submissions.get_submission(submission.uuid)`.

        Args:
            name (str): The name of the stored submission contract.
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
            KeyError: A column named by a target's `filters` is absent from the
                bundle. Only with `validate=True`.
            pyarrow.ArrowException: The bundle cannot be written as parquet,
                e.g. `ArrowTypeError` or `ArrowInvalid` for a column mixing
                strings and integers. Can occur even when validation passes;
                cast the column to one type before submitting.
            CrossClientError: A request to the platform failed, e.g.
                `ResourceNotFoundError` if no submission contract is stored
                under `name`, or `PermissionDeniedError` if the caller may not
                submit to the contract's project.
        """
        return self._client.submissions.get(name).submit(
            df, filename=filename, validate=validate
        )

    def submit_file(
        self,
        name: str,
        path: str | Path,
        filename: str | None = None,
        validate: bool = True,
    ) -> Submission:
        """Read a bundle from a file, then submit it to the CROSS platform.

        Reads the file with the reader for its extension, compared
        case-insensitively: `.csv`, `.parquet`, or `.xls`, `.xlsx`, `.xlsm` and
        `.ods` for an Excel workbook, which is read as the submission contract
        stored under `name` describes. The frame is then handed to `submit`, so
        it is always uploaded as parquet, whatever the format of the file. Also
        raises what `submit` raises.

        Args:
            name (str): The name of the stored submission contract.
            path (str | Path): The path of the file to read.
            filename (str | None, optional): The stem of the uploaded file, as in
                `submit`. Defaults to `None`.
            validate (bool, optional): Whether to validate the bundle before
                uploading it. Defaults to `True`.

        Returns:
            Submission: The created submission, in state `received`.

        Raises:
            ValueError: The extension of `path` is not one of the accepted ones.
            FileNotFoundError: The file does not exist.
            FileReadError: The file cannot be read in its format. Nothing is
                uploaded.
            CrossClientError: A request to the platform failed, e.g.
                `ResourceNotFoundError` if no submission contract is stored
                under `name`.
        """
        path = Path(path)
        extension = path.suffix.lower()
        if extension == ".csv":
            df = read_csv_file(path)
        elif extension == ".parquet":
            df = read_parquet_file(path)
        elif extension in _EXCEL_EXTENSIONS:
            df = read_excel_bundle(self._client.submissions.get(name).contract, path)
        else:
            accepted = [".csv", ".parquet", *_EXCEL_EXTENSIONS]
            raise ValueError(
                f"Unsupported file extension '{path.suffix}'. "
                f"Accepted extensions: {', '.join(accepted)}."
            )
        return self.submit(name, df, filename=filename, validate=validate)

    def validate_submission(
        self,
        name: str,
        df: pd.DataFrame,
        check_existing_primary_key: bool = False,
        check_existing_foreign_key: bool = True,
        check_dimension_granularity: bool = True,
        lazy: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """Validate a delivered bundle against a stored submission contract.

        Fetches the submission contract by `name` and runs
        `SubmissionHandler.validate_submission` on it, reading the target
        contracts and their stored values from the CROSS platform. The steps
        stop at the first failure; see that method for what each check covers.
        By default the stored primary keys are not checked, because a
        submission replaces the rows stored under its `replace_key`.

        Args:
            name (str): The name of the stored submission contract.
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
            CrossClientError: A read from the CROSS platform failed, e.g.
                `ResourceNotFoundError` if no submission contract is stored
                under `name`.
        """
        return self._client.submissions.get(name).validate_submission(
            df=df,
            check_existing_primary_key=check_existing_primary_key,
            check_existing_foreign_key=check_existing_foreign_key,
            check_dimension_granularity=check_dimension_granularity,
            lazy=lazy,
        )
