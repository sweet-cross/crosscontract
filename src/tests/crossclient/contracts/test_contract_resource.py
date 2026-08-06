from unittest.mock import Mock, patch

import pandas as pd
import pytest
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import ValidationError as PydanticValidationError

from crosscontract import CrossContract
from crosscontract.contracts.schema import SchemaValidationError, TableSchema
from crosscontract.crossclient.exceptions.exceptions import ValidationError
from crosscontract.crossclient.services.contract_resource import ContractResource
from crosscontract.crossclient.services.contract_service import ContractService

CONTRACTS_URL = "https://api.example.com/api/v1/contract/"


def _response_dict(contract: CrossContract, status: str = "Draft") -> dict:
    """Build a server-style response dict for a given contract."""
    return {
        "name": contract.name,
        "status": status,
        "contract_type": contract.contract_type,
        "contract": contract.model_dump(mode="json"),
    }


def _make_resource(
    service: ContractService, contract: CrossContract, status: str = "Draft"
) -> ContractResource:
    return ContractResource.from_response(service, _response_dict(contract, status))


@pytest.fixture
def contract_resource(
    service: ContractService, contract_factory: type[ModelFactory]
) -> ContractResource:
    """Fixture to provide a ContractResource instance."""
    contract: CrossContract = contract_factory.build(name="contract")
    return _make_resource(service, contract)


class TestInitialize:
    def test_from_response_success(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """from_response builds a fully populated resource from a response dict."""
        contract: CrossContract = contract_factory.build(name="test_contract")
        resource = ContractResource.from_response(
            service, _response_dict(contract, "Draft")
        )
        assert resource.name == "test_contract"
        assert resource.status == "Draft"
        assert resource.contract_type == contract.contract_type
        assert resource.contract.name == "test_contract"

    def test_from_response_missing_field(self, service: ContractService):
        """from_response surfaces a validation error if the payload is malformed."""
        with pytest.raises(PydanticValidationError):
            ContractResource.from_response(
                service,
                {"name": "x", "status": "Draft", "contract_type": "General"},
            )

    def test_from_response_invalid_status(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """Status outside the allowed literal values is rejected."""
        contract: CrossContract = contract_factory.build(name="test_contract")
        payload = _response_dict(contract, status="Bogus")
        with pytest.raises(PydanticValidationError):
            ContractResource.from_response(service, payload)

    def test_representation(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """Test the string representation of ContractResource."""
        contract: CrossContract = contract_factory.build(name="test_contract")
        resource = _make_resource(service, contract, status="Draft")
        repr_str = repr(resource)
        assert "ContractResource" in repr_str
        assert "test_contract" in repr_str
        assert "Draft" in repr_str


class TestRefresh:
    def test_refresh_updates_fields(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """refresh() pulls fresh fields via the service and replaces local state."""
        initial = contract_factory.build(name="test_contract", title="old")
        resource = _make_resource(service, initial, status="Draft")

        updated = _make_resource(
            service,
            contract_factory.build(name="test_contract", title="new"),
            status="Active",
        )
        resource._service.get = Mock(return_value=updated)

        resource.refresh()
        assert resource.contract.title == "new"
        assert resource.status == "Active"

    def test_refresh_name_mismatch(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """refresh() guards against the server returning a different contract."""
        resource = _make_resource(service, contract_factory.build(name="test_contract"))

        bogus = _make_resource(service, contract_factory.build(name="something_else"))
        resource._service.get = Mock(return_value=bogus)

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
            contract_resource.name,
            self.data,
            project_name=None,
        )

    def test_add_data_success_validation(self, contract_resource: ContractResource):
        """Test adding data successfully."""

        contract_resource._service._add_data = Mock(return_value=None)
        # Use object.__setattr__ to bypass Pydantic's immutability/field checks
        # when mocking a method on an instance
        object.__setattr__(
            contract_resource.contract.tableschema,
            "validate_dataframe",
            Mock(return_value=None),
        )
        contract_resource.add_data(self.data, validate=True)
        contract_resource._service._add_data.assert_called_once_with(
            contract_resource.name,
            self.data,
            project_name=None,
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
            contract_resource.contract.tableschema,
            "validate_dataframe",
            Mock(side_effect=my_validation_error),
        )
        with pytest.raises(
            ValidationError,
            match="Validation failed",
        ):
            contract_resource.add_data(self.data, validate=True)

    def test_prepare_csv_data_success(
        self, contract_factory: type[ModelFactory], service: ContractService
    ):
        """Test preparing CSV data successfully."""
        contract: CrossContract = contract_factory.build(
            name="contract",
            tableschema=TableSchema(
                fields=[
                    {"name": "timestamp", "type": "datetime"},
                ],
                foreignKeys=[],
            ),
        )
        resource = _make_resource(service, contract)
        data = pd.DataFrame({"timestamp": pd.to_datetime(["2021-01-01", "2021-01-02"])})

        result = resource._prepare_dataframe_csv_upload(data)
        for org, val in zip(data["timestamp"], result["timestamp"], strict=True):
            assert val == org.strftime(
                resource.contract.tableschema.get("timestamp").format
            )

    def test_prepare_csv_data_no_datetime_fields(
        self, contract_factory: type[ModelFactory], service: ContractService
    ):
        """Test preparing CSV data when there are no datetime fields."""
        contract: CrossContract = contract_factory.build(
            name="contract",
            tableschema=TableSchema(
                fields=[
                    {"name": "timestamp", "type": "string"},
                ],
                foreignKeys=[],
            ),
        )
        resource = _make_resource(service, contract)
        data = pd.DataFrame({"timestamp": ["a", "b"]})

        result = resource._prepare_dataframe_csv_upload(data)
        pd.testing.assert_frame_equal(data, result)

    def test_prepare_csv_data_success_as_strings(
        self, contract_factory: type[ModelFactory], service: ContractService
    ):
        """Test preparing CSV data successfully."""
        contract: CrossContract = contract_factory.build(
            name="contract",
            tableschema=TableSchema(
                fields=[
                    {"name": "timestamp", "type": "datetime"},
                ],
                foreignKeys=[],
            ),
        )
        resource = _make_resource(service, contract)
        org = ["2021-01-01 00:00", "2021-01-02 01:00"]
        data = pd.DataFrame({"timestamp": org})

        result = resource._prepare_dataframe_csv_upload(data)
        for i, val in enumerate(result["timestamp"]):
            assert val == org[i]


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
            contract_resource.contract.tableschema, "validate_dataframe", validate_mock
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
            contract_resource.contract.tableschema, "validate_dataframe", validate_mock
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
            contract_resource.contract.tableschema, "validate_dataframe", validate_mock
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
            contract_resource.contract.tableschema, "validate_dataframe", validate_mock
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
        object.__setattr__(contract_resource.contract.tableschema, "primaryKey", None)

        assert contract_resource.get_primary_key_values() is None

    def test_get_primary_key_values_empty_result(
        self, contract_resource: ContractResource
    ):
        """Test get_primary_key_values when no existing values found."""
        # Mock schema.primaryKey
        pk_mock = Mock()
        pk_mock.root = ["id"]
        object.__setattr__(
            contract_resource.contract.tableschema, "primaryKey", pk_mock
        )

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
        object.__setattr__(
            contract_resource.contract.tableschema, "primaryKey", pk_mock
        )

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
        object.__setattr__(contract_resource.contract.tableschema, "foreignKeys", None)

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
        object.__setattr__(
            contract_resource.contract.tableschema, "foreignKeys", fks_mock
        )

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


class TestIsDimension:
    def test_is_dimension_true_for_dimension(self, service: ContractService):
        """Dimension contracts (rigid template) are dimensions."""
        contract = CrossContract(
            name="dim",
            title="t",
            description="d",
            contract_type="Dimension",
        )
        assert _make_resource(service, contract).is_dimension is True

    def test_is_dimension_true_for_flexible_dimension(self, service: ContractService):
        """FlexibleDimension contracts are dimensions."""
        contract = CrossContract(
            name="flex_dim",
            title="t",
            description="d",
            contract_type="FlexibleDimension",
            tableschema={
                "primaryKey": ["id"],
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "label", "type": "string"},
                    {"name": "description", "type": "string"},
                ],
            },
        )
        assert _make_resource(service, contract).is_dimension is True

    @pytest.mark.parametrize("contract_type", ["General", "ValueVariable"])
    def test_is_dimension_false(self, service: ContractService, contract_type: str):
        """is_dimension is False for non-dimension contract types."""
        contract = CrossContract(
            name="not_dim",
            title="t",
            description="d",
            contract_type=contract_type,
            tableschema={
                "fields": [{"name": "id", "type": "string"}],
                "foreignKeys": [],
            },
        )
        assert _make_resource(service, contract).is_dimension is False


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


class TestDeleteData:
    def test_delete_data_success(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """delete_data delegates to the service when the contract is Active."""
        contract: CrossContract = contract_factory.build(name="contract")
        resource = _make_resource(service, contract, status="Active")
        resource._service._delete_data = Mock(return_value=None)

        filters = {"region": "DE"}
        result = resource.delete_data(filters)

        assert result is None
        resource._service._delete_data.assert_called_once_with(
            resource.name, filters, project_name=None, confirm_delete_all=False
        )

    @pytest.mark.parametrize("status", ["Draft", "Suspended", "Retired"])
    def test_delete_data_non_active_status_raises(
        self,
        service: ContractService,
        contract_factory: type[ModelFactory],
        status: str,
    ):
        """delete_data raises locally when the cached status is not Active."""
        contract: CrossContract = contract_factory.build(name="contract")
        resource = _make_resource(service, contract, status=status)
        resource._service._delete_data = Mock(return_value=None)

        with pytest.raises(ValueError, match="must be 'Active'"):
            resource.delete_data({"region": "DE"})

        resource._service._delete_data.assert_not_called()
