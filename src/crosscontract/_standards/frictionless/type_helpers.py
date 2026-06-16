from typing import Annotated, Any, TypeVar

from pydantic import BeforeValidator

T = TypeVar("T")


def _drop_empty_list(v: Any) -> Any:
    return None if isinstance(v, list) and not v else v


OptionalNonEmptyList = Annotated[list[T] | None, BeforeValidator(_drop_empty_list)]
