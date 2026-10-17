import pandas as pd

from crosscontract.crossclient import CrossClient
from crosscontract.crossclient.services.submission.schemas import Submission


class CrossSubmitter:
    """The data provider's entry point to the CROSS platform.

    The write-side counterpart of `CrossRegistry`, constructed the same way.
    Every method takes the name of a submission contract stored on the
    platform. To validate a local `SubmissionContract`, use
    `SubmissionHandler(contract, df).validate_submission(resolver)`.

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
        first checked as by `validate_submission` with every check on, and
        nothing is uploaded if any check fails. To validate with other
        settings, e.g. without the stored primary keys for a corrected
        resubmission, call `validate_submission` with the flags you need and
        then `submit(name, df, validate=False)`.

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
            ValueError: A target names a contract that cannot be read or that
                does not declare every `replace_key` column. Only with
                `validate=True`.
            CrossClientError: A request to the platform failed, e.g.
                `ResourceNotFoundError` if no submission contract is stored
                under `name`, or `PermissionDeniedError` if the caller may not
                submit to the contract's project.
        """
        return self._client.submissions.get(name).submit(
            df, filename=filename, validate=validate
        )

    def validate_submission(
        self,
        name: str,
        df: pd.DataFrame,
        check_existing_primary_key: bool = True,
        check_existing_foreign_key: bool = True,
        check_dimension_granularity: bool = True,
        lazy: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """Validate a delivered bundle against a stored submission contract.

        Fetches the submission contract by `name`, then first checks every target's
        contract — that it resolves, and that it
        declares the submission contract's `replace_key` — then runs three steps
        in order, stopping at the first failure:

        1. the bundle against the submission contract's own `tableschema`,
        2. the bundle for rows that no target claims,
        3. each target's extracted data against the contract it names.

        The contract check and step 3 read the contracts a target names, and
        the values already stored under them, live from the platform. Step 1
        does not: a submission contract declares no keys, so it has nothing to
        look up.

        Extraction runs on the bundle exactly as delivered: the coerced frame
        step 1 returns is discarded, because target filters match a column's
        string form and a coerced value can change which target claims a row.

        Args:
            name (str): The name of the stored submission contract describing
                the bundle and how it is split into targets.
            df (pd.DataFrame): The bundle as delivered.
            check_existing_primary_key (bool): If True, also check each target's
                primary key against the values already stored for the contract
                it names. Applies to step 3 only — a submission contract
                declares no primary key, so step 1 has none to check. Each
                target's rows are checked for duplicated or missing key values
                either way. Defaults to True.
            check_existing_foreign_key (bool): If True, also check each target's
                foreign keys against the values already stored for the contracts
                they reference. Applies to step 3 only — a submission contract
                declares no foreign keys. A False value suppresses the
                foreign-key check entirely, self-references included. Defaults to
                True.
            check_dimension_granularity (bool): If True, also check that no group
                of otherwise-identical rows reports a member of a hierarchical
                dimension alongside one of its descendants, which would count
                that member twice when the data is summed. Only a ValueVariable
                is checked, and only its references to a `Dimension`; a
                `FlexibleDimension` is flat and has nothing to check. Applies to
                step 3 only — a submission contract is not a ValueVariable.
                Defaults to True.
            lazy (bool): If True, collect all of a step's validation errors and
                raise them together. If False, raise the first error
                encountered. Note that a non-lazy failure yields a degraded
                report: pandera does not attach the validated frame to the
                error, so the offending key values cannot be recovered from it.
                Defaults to True.

        Returns:
            dict[str, pd.DataFrame]: Step 3's result — the validated, coerced
                target data, keyed by target name. Empty frames are legitimate:
                a target that claims no rows is not an error.

        Raises:
            SchemaValidationError: Step 1. The bundle does not satisfy the
                submission contract's own schema. No target is attempted.
            UnclaimedRowsError: Step 2. The bundle holds rows no target claims,
                which extraction would silently drop. Carries the rows. No
                target is attempted.
            TargetValidationError: Step 3. At least one target's data failed,
                holding one entry per failing target. Every target is attempted
                first, and the frames of those that passed are discarded along
                with the failures.
            ValueError: One or more targets name a contract the resolver cannot
                supply, or name one that does not declare every `replace_key`
                column. Raised before step 1 and listing every such target.
                Also raised in step 3 when the granularity check meets a
                referenced dimension the resolver cannot supply.
            KeyError: A column named by a target's `filters` is absent from the
                bundle. Step 1 only enforces the presence of columns whose field
                is `required`, so an optional filter column can be missing by
                the time step 2 reads it.
            CrossClientError: A read against the platform failed, e.g.
                `ResourceNotFoundError` if no submission contract is stored
                under `name`. A contract or its stored data being unreadable
                surfaces here rather than as a validation failure.
        """
        return self._client.submissions.get(name).validate_submission(
            df=df,
            check_existing_primary_key=check_existing_primary_key,
            check_existing_foreign_key=check_existing_foreign_key,
            check_dimension_granularity=check_dimension_granularity,
            lazy=lazy,
        )
