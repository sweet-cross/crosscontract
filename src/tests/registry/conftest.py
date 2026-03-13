from unittest.mock import MagicMock

import pandas as pd
import pytest

from crosscontract.contracts.schema.reference import ForeignKeys


@pytest.fixture
def make_contract_resource():
    """Factory fixture that creates a mocked ContractResource.

    Args:
        data: DataFrame returned by get_data()
        name: contract name
        description: contract description
        title: contract title (optional)
        fields: list of field mocks (optional)
        foreign_keys: ForeignKeys instance (optional)
    """

    def _factory(
        data: pd.DataFrame,
        name: str = "test_contract",
        description: str = "A test contract",
        title: str | None = "Test Contract",
        fields: list | None = None,
        foreign_keys: ForeignKeys | None = None,
    ) -> MagicMock:
        if fields is None:
            # Build minimal field mocks from DataFrame columns
            fields = []
            for col in data.columns:
                field = MagicMock()
                field.name = col
                fields.append(field)

        contract = MagicMock()
        contract.name = name
        contract.description = description
        contract.title = title
        contract.tableschema.fields = fields
        contract.tableschema.foreignKeys = foreign_keys or ForeignKeys([])

        cr = MagicMock()
        cr.contract = contract
        cr.get_data.return_value = data.copy()

        return cr

    return _factory
