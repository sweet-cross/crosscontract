from unittest.mock import MagicMock

import pandas as pd
import pytest

from crosscontract.contracts import CrossContract
from crosscontract.contracts.schema.subschemas import BaseDimensionSchema


@pytest.fixture
def make_contract_resource():
    """Factory fixture that creates a mocked ContractResource with a real contract.

    Args:
        data: DataFrame returned by get_data()
        contract_dict: dictionary to build the CrossContract from
    """

    def _factory(
        data: pd.DataFrame,
        contract_dict: dict,
    ) -> MagicMock:
        contract = CrossContract.model_validate(contract_dict)

        cr = MagicMock()
        cr.contract = contract
        cr.is_dimension = isinstance(contract.tableschema, BaseDimensionSchema)
        cr.get_data.return_value = data.copy()

        return cr

    return _factory
