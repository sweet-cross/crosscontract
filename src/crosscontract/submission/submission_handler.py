"""Execution of a submission contract against a delivered bundle.

The counterpart to the spec models in this package: a `SubmissionContract`
describes how a bundle splits into per-variable datasets, and a
`SubmissionHandler` carries that description out against actual data.
"""

import pandas as pd

from crosscontract.contracts import BaseContract, ContractResolver
from crosscontract.contracts.schema import SchemaValidationError
from crosscontract.submission.extraction import Target
from crosscontract.transformations import BaseTransformation

from .exceptions import TargetValidationError
from .submission_contract import SubmissionContract


class SubmissionHandler:
    """Apply a submission contract's extraction instructions to a bundle.

    The handler's scope is targets and nothing else. For one target,
    `extract_target_data` selects the rows it claims, `transform_target_data`
    applies its transformation profile and then its own transformations,
    `get_target_data` composes the two, and `validate_target` checks the result
    against the contract that target names. `validate_targets` answers for every
    target, or for a named selection of them, and across targets it collects
    every failure rather than stopping at the first.

    A target's contract arrives from the caller, either handed over directly or
    through a `ContractResolver`; the handler never constructs one. With a
    contract in hand it loads and runs with no platform connection.
    `CrossSubmitter` is the connected composition: it supplies a resolver that
    reads from the platform, and runs the bundle's own validation around this.

    Attributes:
        contract (SubmissionContract): The contract describing the bundle and how
            it is split into targets.
        bundle (pd.DataFrame): A copy of the submitted data the instructions are
            applied to.
    """

    def __init__(self, contract: SubmissionContract, bundle: pd.DataFrame):
        """Bind a submission contract to the bundle it describes.

        The bundle is copied, so later changes to the frame handed in do not
        alter the handler's answers.

        Args:
            contract (SubmissionContract): The contract describing the bundle and
                how it is split into targets.
            bundle (pd.DataFrame): The submitted data, conforming to the
                contract's `tableschema`. Every column named by a target's
                `filters` must be present.
        """
        self.contract = contract
        self.bundle = bundle.copy()

    def _mask_target(self, target: Target) -> pd.Series:
        """Return a boolean mask selecting the bundle rows a target claims.

        A row is claimed when it satisfies every entry of the target's `filters`.
        Values are compared against the column's string form, so a filter on a
        typed column matches `str(value)`.

        Args:
            target (Target): The target whose filters select the rows.

        Returns:
            pd.Series: A boolean mask over the bundle's index.

        Raises:
            KeyError: If a column named by the target's `filters` is absent from
                the bundle.
        """
        mask = pd.Series(True, index=self.bundle.index)
        for column, value in target.filters.items():
            mask &= self.bundle[column].astype(str) == value
        return mask

    def get_target_data(self, target_name: str) -> pd.DataFrame:
        """Extract the target variable from the submission bundle and apply all
        transformations specified in the submission contract.

        Args:
            target_name (str): The name of the target to extract rows for.

        Returns:
            pd.DataFrame: A DataFrame containing the rows claimed by the target,
                after applying the target's transformation profile and transformations.

        Raises:
            KeyError: If no target with the given name exists, or if a column
                named by the target's `filters` is absent from the bundle.
        """
        df = self.extract_target_data(target_name)
        df = self.transform_target_data(df, target_name)
        return df

    def extract_target_data(self, target_name: str) -> pd.DataFrame:
        """Load the rows of a submission bundle that a target claims.

        Args:
            target_name (str): The name of the target to load rows for.

        Returns:
            pd.DataFrame: A DataFrame containing the rows claimed by the target.

        Raises:
            KeyError: If no target with the given name exists, or if a column
                named by the target's `filters` is absent from the bundle.
        """
        target = self.contract.extraction.get_target(target_name)
        return self.bundle[self._mask_target(target)]

    def transform_target_data(self, df: pd.DataFrame, target_name: str) -> pd.DataFrame:
        """Apply all transformations specified in the submission contract to the
        target variable.

        `df` is not checked against `target_name`: passing one target's rows
        under another target's name returns a plausible-looking wrong answer
        rather than raising. Pair them yourself, or use `get_target_data`.

        Args:
            df (pd.DataFrame): The DataFrame containing the rows claimed by the
                target. Not mutated; a new DataFrame is returned.
            target_name (str): The name of the target to transform.

        Returns:
            pd.DataFrame: A DataFrame containing the transformed rows of the
                target variable.

        Raises:
            KeyError: If no target with the given name exists.
        """
        target = self.contract.extraction.get_target(target_name)
        steps_to_apply: list[BaseTransformation] = []
        if target.transformation_profile:
            steps_to_apply.extend(
                self.contract.extraction.transformation_profiles[
                    target.transformation_profile
                ]
            )

        steps_to_apply.extend(target.transformations)
        df = df.copy()
        for step in steps_to_apply:
            df = step.apply(df)

        return df

    def unclaimed_rows(self) -> pd.DataFrame:
        """Return the rows of a submission bundle that no target claims.

        A row is claimed by a target when it satisfies every entry of that
        target's `filters`. Filter values are matched against the string form
        of the column, so a filter on a typed column compares against
        `str(value)` rather than against the typed value.

        Rows that no target claims are the rows extraction would silently drop.
        This method reports them and nothing more — whether an unclaimed row is
        an error or a warning is the caller's decision.

        Returns:
            pd.DataFrame: The unclaimed rows, keeping their index labels. Empty
                when every row is claimed.

        Raises:
            KeyError: If a column named by any target's `filters` is absent from
                the bundle.
        """

        claimed = pd.Series(False, index=self.bundle.index)
        for target in self.contract.extraction.targets:
            claimed |= self._mask_target(target)
        return self.bundle[~claimed]

    def validate_target(
        self,
        target_name: str,
        contract: BaseContract | None = None,
        resolver: ContractResolver | None = None,
        check_existing_primary_key: bool = False,
        check_existing_foreign_key: bool = False,
        lazy: bool = True,
    ) -> pd.DataFrame:
        """Extract a target's rows, transform them, and validate the result.

        Composes `get_target_data` with the target contract's `validate_data`.
        The contract is either handed in or resolved by name through `resolver`;
        an explicit `contract` wins, and the resolver is then never asked to
        resolve.

        Args:
            target_name (str): The name of the target to validate.
            contract (BaseContract | None, optional): The contract to validate
                against. Its `name` must match the target's `contract`. If
                `None`, a `resolver` must be given to supply it.
                Defaults to `None`.
            resolver (ContractResolver | None, optional): Supplier of the target
                contract and of the stored values. Required when `contract` is
                not given, or when one of the check flags is set.
                Defaults to `None`.
            check_existing_primary_key (bool): If True, also check the primary
                key against the values already stored for this contract.
                Defaults to False.
            check_existing_foreign_key (bool): If True, also check the foreign
                keys against the values already stored for the contracts they
                reference. Defaults to False.
            lazy (bool): If True, collect all validation errors and raise them
                together. If False, raise the first error encountered. Note that
                a non-lazy failure yields a degraded report: pandera does not
                attach the validated frame to the error, so the offending key
                values cannot be recovered from it. Defaults to True.

        Returns:
            pd.DataFrame: The validated data, with the schema's coercions
                applied. Empty when the target claims no rows.

        Raises:
            ValueError: If neither a contract nor a resolver is provided, if the
                contract cannot be resolved, if the provided contract's name
                does not match the target's contract, or if the check flags are
                set but no resolver is provided.
            KeyError: If no target with the given name exists, or if a column
                named by the target's `filters` is absent from the bundle.
            SchemaValidationError: If the target's data fails schema validation
                against the contract.
        """
        target = self.contract.extraction.get_target(target_name)
        contract_name = target.contract

        if contract is None:
            if resolver is None:
                raise ValueError("Either a contract or a resolver must be provided.")
            contract = resolver.resolve(contract_name)
            if contract is None:
                raise ValueError(
                    f"Target '{target_name}' names contract '{contract_name}', "
                    "which could not be resolved."
                )
        else:
            if contract.name != contract_name:
                raise ValueError(
                    f"The provided contract '{contract.name}' does not match the "
                    f"target's contract '{contract_name}'."
                )

        target_data = self.get_target_data(target_name)

        return contract.validate_data(
            target_data,
            resolver=resolver,
            check_existing_primary_key=check_existing_primary_key,
            check_existing_foreign_key=check_existing_foreign_key,
            lazy=lazy,
        )

    def validate_targets(
        self,
        resolver: ContractResolver,
        targets: list[str] | None = None,
        check_existing_primary_key: bool = False,
        check_existing_foreign_key: bool = False,
        lazy: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """Validate every target of the submission bundle, or a selection of them.

        Delegates to `validate_target` per target, resolving each target's
        contract by name through `resolver`. Every target is attempted before
        anything is raised, so one broken target does not hide the others.

        The result is all-or-nothing: if any target's data fails validation, the
        frames of the targets that passed are discarded along with the failures.
        Data failures are collected; a *wiring* failure — an unknown target name,
        or a contract the resolver cannot supply — escapes immediately, because
        it says the run itself was set up wrongly rather than that the data is
        bad.

        Args:
            resolver (ContractResolver): Supplier of the target contracts and of
                the stored values.
            targets (list[str] | None, optional): The names of the targets to
                validate. `None` means all of them — every target of the
                extraction instructions; an empty list means none of them, and
                returns an empty result. Defaults to `None`.
            check_existing_primary_key (bool): If True, also check each target's
                primary key against the values already stored for its contract.
                Defaults to False.
            check_existing_foreign_key (bool): If True, also check each target's
                foreign keys against the values already stored for the contracts
                they reference. Defaults to False.
            lazy (bool): If True, collect all of a target's validation errors and
                raise them together. If False, raise on the first error that
                target hits — one `SchemaValidationError` per failing target
                either way, but a non-lazy one carries a degraded report.
                Defaults to True.

        Returns:
            dict[str, pd.DataFrame]: The validated data, coerced, keyed by target
                name.

        Raises:
            TargetValidationError: If any target's data fails validation, holding
                one entry per failing target.
            ValueError: If a target's contract cannot be resolved. Raised for the
                first target that hits it, rather than collected.
            KeyError: If a named target does not exist, or if a column named by a
                target's `filters` is absent from the bundle.
        """
        targets = (
            targets
            if targets is not None
            else [t.name for t in self.contract.extraction.targets]
        )

        validated_data: dict[str, pd.DataFrame] = {}
        errors: dict[str, SchemaValidationError] = {}
        for target_name in targets:
            try:
                validated_data[target_name] = self.validate_target(
                    target_name,
                    resolver=resolver,
                    check_existing_primary_key=check_existing_primary_key,
                    check_existing_foreign_key=check_existing_foreign_key,
                    lazy=lazy,
                )
            except SchemaValidationError as e:
                errors[target_name] = e

        if errors:
            raise TargetValidationError(errors)
        return validated_data
