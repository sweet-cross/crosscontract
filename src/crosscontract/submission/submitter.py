import pandas as pd

from crosscontract import CrossClient
from crosscontract.crossclient.services import CrossContractResolver

from .exceptions import UnclaimedRowsError
from .submission_contract import SubmissionContract
from .submission_handler import SubmissionHandler


class CrossSubmitter:
    """The data provider's entry point to the CROSS platform.

    The write-side counterpart of `CrossRegistry`, constructed the same way and
    building its own contract resolver so a submission can be validated against
    the contracts it names.

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
        self._resolver = CrossContractResolver(client.contracts)

    def submit(self):
        """Submit a delivered bundle to the CROSS platform.

        Raises:
            NotImplementedError: Always. The CROSS platform does not yet expose
                a submission endpoint.
        """
        raise NotImplementedError("The submit method is not yet implemented.")

    def validate_submission(
        self,
        contract: SubmissionContract,
        df: pd.DataFrame,
        check_existing_primary_key: bool = True,
        check_existing_foreign_key: bool = True,
        lazy: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """Validate a delivered bundle and everything extracted from it.

        Runs three steps in order, stopping at the first failure:

        1. the bundle against the submission contract's own `tableschema`,
        2. the bundle for rows that no target claims,
        3. each target's extracted data against the contract it names.

        Every step is checked against the platform through this submitter's
        resolver, so the contracts a target names and the values already stored
        under them are read live.

        Extraction runs on the bundle exactly as delivered: the coerced frame
        step 1 returns is discarded, because target filters match a column's
        string form and a coerced value can change which target claims a row.

        Args:
            contract (SubmissionContract): The contract describing the bundle
                and how it is split into targets.
            df (pd.DataFrame): The bundle as delivered.
            check_existing_primary_key (bool): If True, also check primary keys
                against the values already stored for the contract they belong
                to — the submission contract in step 1, each target's contract
                in step 3. A False value suppresses the primary-key check
                entirely rather than only its stored-value half, so uniqueness
                within the bundle goes unchecked too. Defaults to True.
            check_existing_foreign_key (bool): If True, also check foreign keys
                against the values already stored for the contracts they
                reference. A False value suppresses the foreign-key check
                entirely, self-references included. Defaults to True.
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
            ValueError: A target names a contract the resolver cannot supply.
                Raised for the first target that hits it rather than collected,
                because it says the run was set up wrongly rather than that the
                data is bad.
            KeyError: A column named by a target's `filters` is absent from the
                bundle. Surfaces in step 2, which masks every target.
        """
        # validate the full bundle
        _ = contract.validate_data(
            df,
            resolver=self._resolver,
            check_existing_primary_key=check_existing_primary_key,
            check_existing_foreign_key=check_existing_foreign_key,
            lazy=lazy,
        )

        handler = SubmissionHandler(contract, df, resolver=self._resolver)

        # check whether there are unclaimed rows
        unclaimed_rows = handler.unclaimed_rows()
        if not unclaimed_rows.empty:
            raise UnclaimedRowsError(unclaimed_rows)

        # validate each target
        return handler.validate_targets(
            resolver=self._resolver,
            check_existing_primary_key=check_existing_primary_key,
            check_existing_foreign_key=check_existing_foreign_key,
            lazy=lazy,
        )
