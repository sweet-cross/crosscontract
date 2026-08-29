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
from crosscontract.crossclient.services.resolver import ClientContractResolver

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

    def test_add_data_forwards_project_name(self, contract_resource: ContractResource):
        """A non-default project_name reaches the service.

        The default-valued assertions above still pass if the parameter is
        accepted and then dropped, so a non-default value is what pins the
        forwarding.
        """
        contract_resource._service._add_data = Mock(return_value=None)
        contract_resource.add_data(self.data, validate=False, project_name="my_project")
        contract_resource._service._add_data.assert_called_once_with(
            contract_resource.name,
            self.data,
            project_name="my_project",
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


def _keyed_contract() -> CrossContract:
    """A contract with a primary key, for exercising the resolver path."""
    return CrossContract(
        name="facts",
        title="t",
        description="d",
        contract_type="General",
        tableschema={
            "primaryKey": ["id"],
            "fields": [
                {"name": "id", "type": "integer"},
                {"name": "value", "type": "number"},
            ],
        },
    )


class TestValidation:
    def test_defaults_perform_no_fetch(self, service: ContractService):
        """The default call validates without reading anything from the platform."""
        resource = _make_resource(service, _keyed_contract())
        resource._service._get_data = Mock(
            side_effect=AssertionError("no data should be fetched")
        )

        resource.validate_dataframe(pd.DataFrame({"id": [1, 2], "value": [1.0, 2.0]}))

        resource._service._get_data.assert_not_called()

    def test_flags_are_forwarded_with_a_resolver(
        self, contract_resource: ContractResource
    ):
        """The flags reach `validate_data`, together with a client-backed resolver."""
        df = pd.DataFrame({"col1": [1, 2]})
        validate_mock = Mock(return_value=df)
        object.__setattr__(contract_resource.contract, "validate_data", validate_mock)

        contract_resource.validate_dataframe(
            df, check_existing_primary_key=True, check_existing_foreign_key=True
        )

        validate_mock.assert_called_once()
        args, kwargs = validate_mock.call_args
        assert args[0] is df
        assert kwargs["check_existing_primary_key"] is True
        assert kwargs["check_existing_foreign_key"] is True
        assert kwargs["lazy"] is True
        assert isinstance(kwargs["resolver"], ClientContractResolver)

    def test_checking_existing_keys_reads_own_contract(self, service: ContractService):
        """The resolver reads the contract's own stored primary keys."""
        resource = _make_resource(service, _keyed_contract())
        resource._service._get_data = Mock(return_value=pd.DataFrame({"id": [10]}))

        resource.validate_dataframe(
            pd.DataFrame({"id": [1, 2], "value": [1.0, 2.0]}),
            check_existing_primary_key=True,
        )

        resource._service._get_data.assert_called_once_with(
            "facts", columns=["id"], unique=True
        )

    def test_checking_existing_keys_reports_a_collision(self, service: ContractService):
        """A key already stored on the platform fails validation."""
        resource = _make_resource(service, _keyed_contract())
        resource._service._get_data = Mock(return_value=pd.DataFrame({"id": [1]}))

        with pytest.raises(ValidationError):
            resource.validate_dataframe(
                pd.DataFrame({"id": [1, 2], "value": [1.0, 2.0]}),
                check_existing_primary_key=True,
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

    def test_delete_data_forwards_project_name_and_confirmation(
        self, service: ContractService, contract_factory: type[ModelFactory]
    ):
        """Non-default values for both new parameters reach the service.

        The default-valued assertion above still passes if either parameter is
        accepted and then dropped, so non-default values are what pin the
        forwarding.
        """
        contract: CrossContract = contract_factory.build(name="contract")
        resource = _make_resource(service, contract, status="Active")
        resource._service._delete_data = Mock(return_value=None)

        resource.delete_data({}, project_name="my_project", confirm_delete_all=True)

        resource._service._delete_data.assert_called_once_with(
            resource.name,
            {},
            project_name="my_project",
            confirm_delete_all=True,
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

    @pytest.mark.parametrize("status", ["Draft", "Suspended", "Retired"])
    def test_delete_data_status_check_precedes_confirm_delete_all(
        self,
        service: ContractService,
        contract_factory: type[ModelFactory],
        status: str,
    ):
        """The status check fires ahead of the confirmation, not after it.

        An unfiltered delete on a non-Active contract must fail on the status,
        so the widest deletion the client offers stays behind the same local
        gate as a filtered one.
        """
        contract: CrossContract = contract_factory.build(name="contract")
        resource = _make_resource(service, contract, status=status)
        resource._service._delete_data = Mock(return_value=None)

        with pytest.raises(ValueError, match="must be 'Active'"):
            resource.delete_data({}, confirm_delete_all=True)

        resource._service._delete_data.assert_not_called()
