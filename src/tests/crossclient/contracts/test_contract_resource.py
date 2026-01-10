from unittest.mock import Mock, patch

import pandas as pd
import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from crosscontract import CrossContract
from crosscontract.contracts.schema import SchemaValidationError
from crosscontract.crossclient.exceptions.exceptions import ValidationError
from crosscontract.crossclient.services.contract_resource import ContractResource
from crosscontract.crossclient.services.contract_service import ContractService

CONTRACTS_URL = "https://api.example.com/api/v1/contract/"


@pytest.fixture
def contract_resource(
    service: ContractService, contract_factory: type[ModelFactory]
) -> ContractResource:
    """Fixture to provide a ContractResource instance."""
    contract: CrossContract = contract_factory.build(name="contract")
    return ContractResource(
        service=service, name=contract.name, contract=contract, status="Draft"
    )


class TestInitialize:
    def test_initialize_with_name_and_contract(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """Test initializing ContractResource with both name and contract."""
        contract: CrossContract = contract_factory.build(name="test_contract")
        resource = ContractResource(
            service=service, name="test_contract", contract=contract, status="Draft"
        )
        assert resource.name == "test_contract"

    def test_initialize_with_name_only(self, service: ContractService):
        """Test initializing ContractResource with name only."""
        resource = ContractResource(
            service=service, name="test_contract", status="Draft"
        )
        assert resource.name == "test_contract"
        assert resource._contract is None

    def test_initialize_with_contract_only(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """Test initializing ContractResource with contract only."""
        contract: CrossContract = contract_factory.build(name="test_contract")
        resource = ContractResource(service=service, contract=contract, status="Draft")
        assert resource.name == "test_contract"

    def test_initialize_name_mismatch(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """Test initializing ContractResource with mismatched name and contract."""
        contract: CrossContract = contract_factory.build(name="actual_name")
        with pytest.raises(ValueError, match="does not match contract name"):
            ContractResource(
                service=service,
                name="different_name",
                contract=contract,
                status="Draft",
            )

    def test_initialize_missing_parameters(self, service: ContractService):
        """Test initializing ContractResource with missing parameters."""
        with pytest.raises(
            ValueError, match="Either name or contract must be provided."
        ):
            ContractResource(service=service, status="Draft")

    def test_representation(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """Test the string representation of ContractResource."""
        contract: CrossContract = contract_factory.build(name="test_contract")
        resource = ContractResource(
            service=service, name="test_contract", contract=contract, status="Draft"
        )
        repr_str = repr(resource)
        assert "ContractResource" in repr_str
        assert "test_contract" in repr_str
        assert "Draft" in repr_str


class TestRefresh:
    def test_refresh_success(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """Test refreshing contract details successfully."""
        # initialize resource only with name and status
        resource = ContractResource(
            service=service, name="test_contract", status="Draft"
        )
        assert resource._contract is None
        resource._service.get = Mock(
            return_value=contract_factory.build(name="test_contract")
        )
        # calling the contract property should trigger refresh
        assert resource.contract.name == "test_contract"

    def test_refresh_name_mismatch(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """Test refreshing contract details with name mismatch."""
        # initialize resource only with name and status
        resource = ContractResource(
            service=service, name="test_contract", status="Draft"
        )
        assert resource._contract is None
        resource._service.get = Mock(return_value=contract_factory.build(name="test"))
        with pytest.raises(ValueError, match="does not match resource name"):
            resource.refresh()


class TestChangeStatus:
    def test_change_status_success(self, contract_resource: ContractResource):
        """Test changing contract status successfully."""
        contract_resource._service.change_status = Mock(return_value=None)
        contract_resource.change_status("Retired")
        contract_resource._service.change_status.assert_called_once_with(
            contract_resource.name, "Retired"
        )
        assert contract_resource.status == "Retired"


class TestAddData:
    data = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})

    def test_add_data_success(self, contract_resource: ContractResource):
        """Test adding data successfully."""

        contract_resource._service._add_data = Mock(return_value=None)
        contract_resource.add_data(self.data, validate=False)
        contract_resource._service._add_data.assert_called_once_with(
            contract_resource.name, self.data
        )

    def test_add_data_success_validation(self, contract_resource: ContractResource):
        """Test adding data successfully."""

        contract_resource._service._add_data = Mock(return_value=None)
        # Use object.__setattr__ to bypass Pydantic's immutability/field checks
        # when mocking a method on an instance
        object.__setattr__(
            contract_resource.contract.schema,
            "validate_dataframe",
            Mock(return_value=None),
        )
        contract_resource.add_data(self.data, validate=True)
        contract_resource._service._add_data.assert_called_once_with(
            contract_resource.name, self.data
        )

    def test_add_data_failed_validation(self, contract_resource: ContractResource):
        """Test adding data successfully."""

        contract_resource._service._add_data = Mock(return_value=None)
        # Use object.__setattr__ to bypass Pydantic's immutability/field checks
        # when mocking a method on an instance
        my_validation_error = ValidationError(
            "Validation failed",
            validation_errors=[{"field": "col1", "error": "Invalid value"}],
        )
        object.__setattr__(
            contract_resource.contract.schema,
            "validate_dataframe",
            Mock(side_effect=my_validation_error),
        )
        with pytest.raises(
            ValidationError,
            match="Validation failed",
        ):
            contract_resource.add_data(self.data, validate=True)


class TestImmutability:
    def test_immutable_name(self, contract_resource: ContractResource):
        """Test that the name attribute is immutable."""
        with pytest.raises(AttributeError):
            contract_resource.name = "new_name"

    def test_immutable_status(self, contract_resource: ContractResource):
        """Test that the status attribute is immutable."""
        with pytest.raises(AttributeError):
            contract_resource.status = "Active"

    def test_immutable_contract(self, contract_resource: ContractResource):
        """Test that the contract attribute is immutable."""
        with pytest.raises(AttributeError):
            contract_resource.contract = "3"


class TestValidation:
    def test_validate_dataframe_defaults_success(
        self, contract_resource: ContractResource
    ):
        """Test validate_dataframe with defaults (skipping PK and FK validation)."""
        df = pd.DataFrame({"col1": [1, 2]})

        # Mock schema.validate_dataframe
        validate_mock = Mock(return_value=None)
        object.__setattr__(
            contract_resource.contract.schema, "validate_dataframe", validate_mock
        )

        # Mock internal methods to ensure they are NOT called
        with (
            patch.object(contract_resource, "get_primary_key_values") as pk_mock,
            patch.object(contract_resource, "get_foreign_key_values") as fk_mock,
        ):
            contract_resource.validate_dataframe(df)

            pk_mock.assert_not_called()
            fk_mock.assert_not_called()

            validate_mock.assert_called_once_with(
                df=df,
                primary_key_values=None,
                foreign_key_values=None,
                skip_primary_key_validation=True,
                skip_foreign_key_validation=True,
                lazy=True,
            )

    def test_validate_dataframe_with_pk_success(
        self, contract_resource: ContractResource
    ):
        """Test validate_dataframe with primary key validation enabled."""
        df = pd.DataFrame({"col1": [1, 2]})
        pk_values = [(1,), (2,)]

        validate_mock = Mock(return_value=None)
        object.__setattr__(
            contract_resource.contract.schema, "validate_dataframe", validate_mock
        )

        with (
            patch.object(
                contract_resource, "get_primary_key_values", return_value=pk_values
            ) as pk_mock,
            patch.object(contract_resource, "get_foreign_key_values") as fk_mock,
        ):
            contract_resource.validate_dataframe(df, skip_primary_key_validation=False)

            pk_mock.assert_called_once()
            fk_mock.assert_not_called()

            validate_mock.assert_called_once_with(
                df=df,
                primary_key_values=pk_values,
                foreign_key_values=None,
                skip_primary_key_validation=False,
                skip_foreign_key_validation=True,
                lazy=True,
            )

    def test_validate_dataframe_with_fk_success(
        self, contract_resource: ContractResource
    ):
        """Test validate_dataframe with foreign key validation enabled."""
        df = pd.DataFrame({"col1": [1, 2]})
        fk_values = {("col1",): [(1,), (2,)]}

        validate_mock = Mock(return_value=None)
        object.__setattr__(
            contract_resource.contract.schema, "validate_dataframe", validate_mock
        )

        with (
            patch.object(contract_resource, "get_primary_key_values") as pk_mock,
            patch.object(
                contract_resource, "get_foreign_key_values", return_value=fk_values
            ) as fk_mock,
        ):
            contract_resource.validate_dataframe(df, skip_foreign_key_validation=False)

            pk_mock.assert_not_called()
            fk_mock.assert_called_once()

            validate_mock.assert_called_once_with(
                df=df,
                primary_key_values=None,
                foreign_key_values=fk_values,
                skip_primary_key_validation=True,
                skip_foreign_key_validation=False,
                lazy=True,
            )

    def test_validate_dataframe_validation_error(
        self, contract_resource: ContractResource
    ):
        """Test validate_dataframe raises ValidationError correctly."""
        df = pd.DataFrame({"col1": [1, 2]})

        schema_error = SchemaValidationError(message="Schema invalid")
        schema_error.to_list = Mock(return_value=[{"field": "col1", "error": "bad"}])

        validate_mock = Mock(side_effect=schema_error)
        object.__setattr__(
            contract_resource.contract.schema, "validate_dataframe", validate_mock
        )

        with pytest.raises(ValidationError) as exc:
            contract_resource.validate_dataframe(df)

        assert (
            f"DataFrame validation against contract '{contract_resource.name}'"
            in str(exc.value)
        )
        assert exc.value.validation_errors == [{"field": "col1", "error": "bad"}]


class TestGetKeyValues:
    def test_get_primary_key_values_no_pk(self, contract_resource: ContractResource):
        """Test get_primary_key_values when no primary key is defined."""
        # Mock schema.primaryKey as None
        object.__setattr__(contract_resource.contract.schema, "primaryKey", None)

        assert contract_resource.get_primary_key_values() is None

    def test_get_primary_key_values_empty_result(
        self, contract_resource: ContractResource
    ):
        """Test get_primary_key_values when no existing values found."""
        # Mock schema.primaryKey
        pk_mock = Mock()
        pk_mock.root = ["id"]
        object.__setattr__(contract_resource.contract.schema, "primaryKey", pk_mock)

        # Mock get_data to return empty DataFrame
        with patch.object(
            contract_resource, "get_data", return_value=pd.DataFrame()
        ) as get_data_mock:
            assert contract_resource.get_primary_key_values() is None
            get_data_mock.assert_called_once_with(columns=["id"], unique=True)

    def test_get_primary_key_values_success(self, contract_resource: ContractResource):
        """Test get_primary_key_values success."""
        # Mock schema.primaryKey
        pk_mock = Mock()
        pk_mock.root = ["id", "version"]
        object.__setattr__(contract_resource.contract.schema, "primaryKey", pk_mock)

        # Mock get_data
        df = pd.DataFrame({"id": [1, 2], "version": [1, 1]})
        with patch.object(
            contract_resource, "get_data", return_value=df
        ) as get_data_mock:
            expected = [(1, 1), (2, 1)]
            assert contract_resource.get_primary_key_values() == expected
            get_data_mock.assert_called_once_with(
                columns=["id", "version"], unique=True
            )

    def test_get_foreign_key_values_no_fk(self, contract_resource: ContractResource):
        """Test get_foreign_key_values when no foreign keys are defined."""
        # Mock schema.foreignKeys as None
        object.__setattr__(contract_resource.contract.schema, "foreignKeys", None)

        assert contract_resource.get_foreign_key_values() is None

    def test_get_foreign_key_values_success(self, contract_resource: ContractResource):
        """Test get_foreign_key_values success."""
        # Define mock Foreign Object
        fk1 = Mock()
        fk1.fields = ["user_id"]
        fk1.reference.resource = "UserContract"
        fk1.reference.fields = ["id"]

        fk2 = Mock()
        fk2.fields = ["parent_id"]
        fk2.reference.resource = None  # Self Reference
        fk2.reference.fields = ["id"]

        # Mock schema.foreignKeys
        fks_mock = Mock()
        fks_mock.root = [fk1, fk2]
        object.__setattr__(contract_resource.contract.schema, "foreignKeys", fks_mock)

        # Mock get_data
        df1 = pd.DataFrame({"id": [101, 102]})
        df2 = pd.DataFrame({"id": [1, 2]})

        with patch.object(
            contract_resource._service, "_get_data", side_effect=[df1, df2]
        ) as get_data_mock:
            result = contract_resource.get_foreign_key_values()

            # Since dictionary usage order depends on execution, but here it's
            # list order. The order corresponds to schema.foreignKeys.root order
            expected = {
                ("user_id",): [(101,), (102,)],
                ("parent_id",): [(1,), (2,)],
            }
            assert result == expected

            assert get_data_mock.call_count == 2
            # 1st call
            get_data_mock.assert_any_call(
                name="UserContract", columns=["id"], unique=True
            )
            # 2nd call - resource or self.name. fk2.reference.resource is "None"
            # so it uses self.name
            get_data_mock.assert_any_call(
                name=contract_resource.name, columns=["id"], unique=True
            )


class TestPassThrough:
    def test_get_data_success(self, contract_resource: ContractResource):
        """Test retrieving data successfully."""
        expected_df = pd.DataFrame({"col1": [1, 2], "col2": [3, 4]})
        contract_resource._service._get_data = Mock(return_value=expected_df)

        result = contract_resource.get_data(
            columns=["col1"], filters={"col1": "1"}, unique=True
        )

        assert result.equals(expected_df)
        contract_resource._service._get_data.assert_called_once_with(
            name=contract_resource.name,
            columns=["col1"],
            filters={"col1": "1"},
            unique=True,
        )

    def test_drop_data_success(self, contract_resource: ContractResource):
        """Test dropping data successfully."""
        contract_resource._service._drop_data_table = Mock(return_value=None)

        contract_resource.drop_data()

        contract_resource._service._drop_data_table.assert_called_once_with(
            contract_resource.name
        )
