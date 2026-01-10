import io
from unittest.mock import Mock, patch

import pandas as pd
import pytest
import respx
from polyfactory.factories.pydantic_factory import ModelFactory

from crosscontract import CrossContract
from crosscontract.crossclient.exceptions import ResourceNotFoundError, ServerError
from crosscontract.crossclient.services.contract_resource import ContractResource
from crosscontract.crossclient.services.contract_service import ContractService

CONTRACTS_URL = "https://api.example.com/api/v1/contract/"


@pytest.fixture
def valid_contracts(
    contract_factory: type[ModelFactory],
) -> list[CrossContract]:
    """Fixture to provide list of valid CrossContract objects."""
    contract1 = contract_factory.build(name="contract1")
    contract2 = contract_factory.build(name="contract2")
    return [contract1, contract2]


class TestCreate:
    @respx.mock
    def test_create_contract_success(
        self, service: ContractService, valid_contracts: list[CrossContract]
    ):
        """Test creating a contract successfully."""
        # Mock the create endpoint
        # The service calls: client.post(self._route, json=json_payload)
        # It expects a JSON response with "contract" and "status"
        valid_contract = valid_contracts[0]
        expected_response = {
            "contract": valid_contract.model_dump(mode="json"),
            "status": "Draft",
        }

        mock_route = respx.post(CONTRACTS_URL).respond(201, json=expected_response)

        result = service.create(valid_contract)

        assert mock_route.called
        assert isinstance(result, ContractResource)
        assert result.name == valid_contract.name
        assert result.status == "Draft"
        # Verify payload sent matches
        request = mock_route.calls.last.request
        assert request.headers["Authorization"] == "Bearer token_123"

    @respx.mock
    def test_create_contract_activation(
        self, service: ContractService, valid_contracts: list[CrossContract]
    ):
        """Test creating a contract with activation."""
        valid_contract: CrossContract = valid_contracts[0]
        # 1. Create response
        create_response = {
            "contract": valid_contract.model_dump(mode="json"),
            "status": "Draft",
        }
        create_route = respx.post(CONTRACTS_URL).respond(201, json=create_response)

        # 2. Activation response
        activate_url = f"{CONTRACTS_URL}{valid_contract.name}/state"
        activate_route = respx.patch(activate_url).respond(200, json="Active")

        result = service.create(valid_contract, activate=True)

        assert create_route.called
        assert activate_route.called
        assert result.status == "Active"

    @respx.mock
    def test_create_contract_http_error(
        self, service: ContractService, valid_contracts: list[CrossContract]
    ):
        """Test that HTTP errors are raised."""
        respx.post(CONTRACTS_URL).respond(500, json={"detail": "Server Error"})

        with pytest.raises(ServerError):
            service.create(valid_contracts[0])


class TestGet:
    def test_get_contract_success(
        self, service: ContractService, valid_contracts: list[CrossContract]
    ):
        """Test retrieving a contract successfully."""
        valid_contract = valid_contracts[0]
        # Mock the get endpoint
        contract_name = valid_contract.name
        get_url = f"{CONTRACTS_URL}{contract_name}"
        expected_response = {
            "contract": valid_contract.model_dump(mode="json"),
        }

        with respx.mock as respx_mock:
            respx_mock.get(get_url).respond(200, json=expected_response)

            result = service.get(contract_name)

            assert isinstance(result, ContractResource)
            assert result.name == valid_contract.name

    def test_list_contracts(
        self, service: ContractService, valid_contracts: list[CrossContract]
    ):
        """Test retrieving a contract successfully."""
        # Mock the get endpoint
        get_url = f"{CONTRACTS_URL}"
        expected_response = [
            {
                "name": contract.name,
                "contract": contract.model_dump(mode="json"),
                "status": "Active",
            }
            for contract in valid_contracts
        ]

        with respx.mock as respx_mock:
            respx_mock.get(get_url).respond(200, json=expected_response)

            result = service.get_list()

            assert isinstance(result, dict)
            assert all(isinstance(v, ContractResource) for v in result.values())
            assert set(result.keys()) == {"contract1", "contract2"}

    def test_overview_contracts(
        self, service: ContractService, valid_contracts: list[CrossContract]
    ):
        """Test retrieving contract overview successfully."""
        # Mock the get endpoint
        get_url = f"{CONTRACTS_URL}metadata"
        expected_response = [
            contract.model_dump(mode="json", exclude=["schema"])
            for contract in valid_contracts
        ]

        with respx.mock as respx_mock:
            respx_mock.get(get_url).respond(200, json=expected_response)

            result = service.overview()

            assert isinstance(result, pd.DataFrame)
            assert set(result["name"]) == {"contract1", "contract2"}


class TestDelete:
    @respx.mock
    def test_delete_contract_success(self, service: ContractService):
        """Test deleting a contract successfully."""
        contract_name = "contract_to_delete"
        delete_url = f"{CONTRACTS_URL}{contract_name}"

        respx.delete(delete_url).respond(204)

        # Call delete method
        service.delete(contract_name, hard=False)

        # Verify that the delete route was called
        assert respx.calls.last.request.method == "DELETE"
        assert respx.calls.last.request.url == delete_url

    @respx.mock
    def test_delete_contract_hard(self, service: ContractService):
        """Test deleting a contract successfully."""
        contract_name = "contract_to_delete"
        delete_url = f"{CONTRACTS_URL}{contract_name}"

        # Patch change_status and drop_data_table to raise Exception
        service.change_status = Mock(side_effect=Exception("Status change failed"))
        service._drop_data_table = Mock(side_effect=Exception("Drop table failed"))

        respx.delete(delete_url).respond(204)

        # Call delete method
        service.delete(contract_name, hard=True)

        # Verify that the delete route was called
        assert respx.calls.last.request.method == "DELETE"
        assert respx.calls.last.request.url == delete_url

    @respx.mock
    def test_delete_contract_not_exists(self, service: ContractService):
        """Test deleting a contract that does not exist."""
        contract_name = "contract_to_delete"
        delete_url = f"{CONTRACTS_URL}{contract_name}"

        respx.delete(delete_url).respond(404)

        with patch(
            "crosscontract.crossclient.services.contract_service.raise_from_response",
            side_effect=ResourceNotFoundError,
        ) as mock_raise:
            service.delete(contract_name)
            assert mock_raise.called

    @respx.mock
    def test_delete_contract_raise(self, service: ContractService):
        """Test deleting a contract that does not exist."""
        contract_name = "contract_to_delete"
        delete_url = f"{CONTRACTS_URL}{contract_name}"

        respx.delete(delete_url).respond(404)

        with patch(
            "crosscontract.crossclient.services.contract_service.raise_from_response",
            side_effect=ServerError,
        ) as mock_raise:
            with pytest.raises(ServerError):
                service.delete(contract_name)
            assert mock_raise.called

    @respx.mock
    def test_delete_data_table(self, service: ContractService):
        """Test dropping data table for a contract."""
        contract_name = "contract_with_data"
        drop_url = f"{CONTRACTS_URL}{contract_name}/storage"

        respx.delete(drop_url).respond(204)

        service._drop_data_table(contract_name)

        assert respx.calls.last.request.method == "DELETE"
        assert respx.calls.last.request.url == drop_url


class TestChangeStatus:
    @respx.mock
    def test_change_status_success(self, service: ContractService):
        """Test changing contract status successfully."""
        contract_name = "contract_to_change"
        new_status = "Active"
        status_url = f"{CONTRACTS_URL}{contract_name}/state"

        respx.patch(status_url).respond(200, json=new_status)

        result = service.change_status(contract_name, new_status)

        assert respx.calls.last.request.method == "PATCH"
        assert respx.calls.last.request.url == status_url
        assert result == new_status


class TestAddData:
    @respx.mock
    def test_add_data_success(self, service: ContractService):
        """Test adding data to a contract successfully."""
        contract_name = "contract_with_data"
        add_data_url = f"{CONTRACTS_URL}{contract_name}/data"

        respx.post(add_data_url).respond(200)

        # Create sample DataFrame
        data = pd.DataFrame({"column1": [1, 2], "column2": ["a", "b"]})

        service._add_data(contract_name, data)

        assert respx.calls.last.request.method == "POST"
        assert respx.calls.last.request.url == add_data_url


class TestGetData:
    @respx.mock
    def test_get_data_with_all_parameters(self, service: ContractService):
        """Test getting data with all parameters specified."""
        contract_name = "contract_with_data"
        get_data_url = f"{CONTRACTS_URL}{contract_name}/data"

        # Create sample DataFrame that will be returned
        expected_df = pd.DataFrame({"column1": [1, 2], "column2": ["a", "b"]})

        # Convert to parquet bytes for mock response
        parquet_buffer = io.BytesIO()
        expected_df.to_parquet(parquet_buffer)
        parquet_content = parquet_buffer.getvalue()

        # Mock the GET request
        respx.get(get_data_url).respond(200, content=parquet_content)

        # Call _get_data with all parameters
        result = service._get_data(
            name=contract_name,
            columns=["column1", "column2"],
            filters={"column1": "1"},
            unique=True,
        )

        # Verify the request was made correctly
        assert respx.calls.last.request.method == "GET"
        assert (
            respx.calls.last.request.url.path
            == f"/api/v1/contract/{contract_name}/data"
        )

        # Verify query parameters
        params = dict(respx.calls.last.request.url.params)
        assert params["columns"] == "column1,column2"
        assert params["column1"] == "1"
        assert params["unique"] == "true"
        assert params["format"] == "parquet"

        # Verify the result is a DataFrame
        assert isinstance(result, pd.DataFrame)
        pd.testing.assert_frame_equal(result, expected_df)

    @respx.mock
    def test_get_data_with_no_parameters(self, service: ContractService):
        """Test getting data with no parameters specified."""
        contract_name = "contract_with_data"
        get_data_url = f"{CONTRACTS_URL}{contract_name}/data"

        # Create sample DataFrame that will be returned
        expected_df = pd.DataFrame({"column1": [1, 2], "column2": ["a", "b"]})

        # Convert to parquet bytes for mock response
        parquet_buffer = io.BytesIO()
        expected_df.to_parquet(parquet_buffer)
        parquet_content = parquet_buffer.getvalue()

        # Mock the GET request
        respx.get(get_data_url).respond(200, content=parquet_content)

        # Call _get_data with all parameters
        result = service._get_data(name=contract_name)

        # Verify the request was made correctly
        assert respx.calls.last.request.method == "GET"
        assert (
            respx.calls.last.request.url.path
            == f"/api/v1/contract/{contract_name}/data"
        )

        # Verify the result is a DataFrame
        assert isinstance(result, pd.DataFrame)
        pd.testing.assert_frame_equal(result, expected_df)
