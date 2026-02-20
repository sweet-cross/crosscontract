from typing import TYPE_CHECKING

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
)
from sqlalchemy.types import TypeEngine

from crosscontract.contracts.schema.fields import (
    DateTimeField,
    IntegerField,
    ListField,
    NumberField,
    StringField,
)

from .abstract_adapter import AbstractAdapter

if TYPE_CHECKING:  # pragma: no cover
    from crosscontract.contracts.schema import TableSchema

FieldUnion = DateTimeField | IntegerField | ListField | NumberField | StringField


def convert_schema_to_sqlalchemy(
    schema: "TableSchema",
    table_name: str,
    metadata: MetaData | None = None,
    extend_existing: bool = True,
) -> Table:
    """Convert the TableSchema to a SQLAlchemy Table.

    Args:
        schema ("TableSchema"): The Schema instance to convert.
        table_name (str): The name of the table to create.
        metadata (MetaData | None): SQLAlchemy MetaData instance to use for the table.
            If None, a new/dummy MetaData instance will be created.
        extend_existing (bool): Whether to extend an existing table if it exists.

    Returns:
        Table: The SQLAlchemy table representation of the TableSchema.
    """
    return SQLAlchemyPostgresAdapter.convert_schema(
        schema,
        table_name=table_name,
        metadata=metadata,
        extend_existing=extend_existing,
    )


class SQLAlchemyPostgresAdapter(AbstractAdapter):
    """Adapter to convert a schema into a SQLAlchemy table. Currently,
    only supports the postgres dialect"""

    def __init__(self, schema: "TableSchema"):
        """Initialize the adapter with the given schema."""
        super().__init__(schema)

    def convert(
        self,
        table_name: str,
        metadata: MetaData | None = None,
        extend_existing: bool = True,
    ) -> Table:
        """Convert the TableSchema to a SQLAlchemy Table.

        Args:
            table_name (str): The name of the table to create.
            metadata (MetaData | None): SQLAlchemy MetaData instance to use for the
                table. If None, a new/dummy MetaData instance will be created.
            extend_existing (bool): Whether to extend an existing table if it exists.

        Returns:
            Table: The SQLAlchemy table representation of the TableSchema.
        """
        # if no metadata is provided, create a new/dummy one (required by SQLAlchemy)
        if metadata is None:
            metadata = MetaData()

        # always add a primary key field and check for conflicts with existing
        # field names
        if "_id" in self.schema.field_names:
            raise ValueError(
                "Schema cannot have a field named '_id' as it uses it as primary key."
            )
        columns: list[Column] = [Column("_id", Integer, primary_key=True)]

        # add the columns for the fields defined in the schema
        columns.extend(
            [self._create_column(field) for field in self.schema.field_iterator()]
        )

        # create and return the table
        return Table(table_name, metadata, *columns, extend_existing=extend_existing)

    @classmethod
    def convert_schema(
        cls,
        schema: "TableSchema",
        table_name: str,
        metadata: MetaData | None = None,
        extend_existing: bool = True,
    ) -> Table:
        """Convert the TableSchema to a SQLAlchemy Table.

        Args:
            schema ("TableSchema"): The Schema instance to convert.
            table_name (str): The name of the table to create.
            metadata (MetaData | None): SQLAlchemy MetaData instance to use for the
                table. If None, a new/dummy MetaData instance will be created.
            extend_existing (bool): Whether to extend an existing table if it exists.

        Returns:
            Table: The SQLAlchemy table representation of the TableSchema.
        """
        return super().convert_schema(
            schema,
            table_name=table_name,
            metadata=metadata,
            extend_existing=extend_existing,
        )

    def _create_column(self, field: FieldUnion) -> Column:
        """Create a SQLAlchemy Column for the given field."""
        # determine sql type
        sql_type: TypeEngine | None = None
        if isinstance(field, ListField):
            # for lists check the item type and use the appropriate SQLAlchemy type
            map_item_types: dict[str, TypeEngine] = {
                "string": String(),
                "integer": Integer(),
                "number": Float(),
                "boolean": Boolean(),
            }
            item_type = map_item_types.get(field.itemType)
            if item_type is None:
                raise NotImplementedError(
                    f"List of type '{field.itemType}' not yet supported"
                )
            sql_type = ARRAY(item_type)
        else:
            # else use the appropriate SQLAlchemy type based on the field type
            map_types: dict[type, TypeEngine] = {
                IntegerField: Integer(),
                NumberField: Float(),
                StringField: String(),
                DateTimeField: DateTime(timezone=True),
            }
            sql_type = map_types.get(type(field))

        if sql_type is None:  # pragma: no cover
            # this should never happen as checked in the schema validation
            # but leave it here for safety and to satisfy mypy
            raise NotImplementedError(f"Field type '{field.type}' not yet supported")

        # create and return the column
        return Column(
            field.name,
            sql_type,
            nullable=not field.constraints.required,
        )
