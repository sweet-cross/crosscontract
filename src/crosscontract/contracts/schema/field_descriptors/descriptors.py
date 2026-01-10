from abc import ABC
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# --- Enums for better governance ---
class Frequency(str, Enum):
    YEARLY = "yearly"
    MONTHLY = "monthly"
    DAILY = "daily"
    HOURLY = "hourly"


class LocationType(str, Enum):
    COUNTRY = "country"
    REGION = "region"
    STATE = "state"
    POINT = "point"
    CITY = "city"


# --- Base Class (Now an ABC) ---
class FieldReference(BaseModel, ABC):
    """
    Abstract Base Class for field references.
    Cannot be instantiated directly.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )
    # Enforce that subclasses must have a 'type' field.
    type: str = Field(description="The discriminator type of the descriptor.")

    # Renamed 'field' to 'name' for better readability (descriptor.name)
    field: str = Field(description="The name of the field/column in the schema.")


# --- Descriptors ---
class ValueFieldDescriptor(FieldReference):
    """Descriptor for value fields (Measures)."""

    type: Literal["value"] = "value"

    unit: str | None = Field(
        default=None, description="The unit of measurement (e.g., 'MWh', 'USD')."
    )


class TimeFieldDescriptor(FieldReference):
    """Descriptor for time fields (Temporal Dimensions)."""

    type: Literal["time"] = "time"

    frequency: Frequency = Field(description="The frequency of the time field.")


class LocationFieldDescriptor(FieldReference):
    """Descriptor for location fields (Spatial Dimensions)."""

    type: Literal["location"] = "location"

    locationType: LocationType = Field(description="The type of location granularity.")
