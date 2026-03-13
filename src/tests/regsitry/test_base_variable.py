# test_base_variable.py

import pandas as pd
import pytest

from crosscontract.crossclient import ContractResource
from crosscontract.registry import CrossBaseVariable


class ConcreteVariable(CrossBaseVariable):
    """Minimal concrete subclass for testing the ABC."""

    pass


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame({"id": ["a", "b"], "value": [1, 2]})


@pytest.fixture
def base_variable(make_contract_resource, sample_df) -> ConcreteVariable:
    cr = make_contract_resource(data=sample_df, name="my_var", title="My Variable")
    return ConcreteVariable(contract_resource=cr)


class TestProperties:
    def test_name(self, base_variable: ConcreteVariable):
        assert base_variable.name == "my_var"

    def test_title(self, base_variable: ConcreteVariable):
        assert base_variable.title == "My Variable"

    def test_description(self, base_variable: ConcreteVariable):
        assert base_variable.description == "A test contract"

    def test_field_names(self, base_variable: ConcreteVariable):
        assert base_variable.field_names == ["id", "value"]

    def test_contract_resource_accessible(
        self, base_variable: ConcreteVariable, make_contract_resource
    ):
        assert base_variable.contract_resource is not None


class TestLazyData:
    def test_data_not_fetched_on_init(self, base_variable: ConcreteVariable):
        base_variable.contract_resource.get_data.assert_not_called()

    def test_data_fetched_on_first_access(
        self, base_variable: ConcreteVariable, sample_df: pd.DataFrame
    ):
        result = base_variable.data
        base_variable.contract_resource.get_data.assert_called_once()
        pd.testing.assert_frame_equal(result, sample_df)

    def test_data_cached_on_second_access(self, base_variable: ConcreteVariable):
        _ = base_variable.data
        _ = base_variable.data
        base_variable.contract_resource.get_data.assert_called_once()

    def test_data_returns_copy(self, base_variable: ConcreteVariable):
        df1 = base_variable.data
        df2 = base_variable.data
        assert df1 is not df2


class TestFromClient:
    def test_from_client(self, make_contract_resource, sample_df):
        from unittest.mock import MagicMock

        cr: ContractResource = make_contract_resource(
            data=sample_df, name="from_client_var"
        )
        client = MagicMock()
        client.contracts.get.return_value = cr

        var = ConcreteVariable.from_client(client, "from_client_var")

        client.contracts.get.assert_called_once_with("from_client_var")
        assert var.name == "from_client_var"
