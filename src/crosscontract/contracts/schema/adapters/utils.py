from datetime import UTC, datetime


def parse_datetime(value: str | datetime | None, format: str) -> datetime | None:
    """Parses a datetime string into a datetime object. That is
    timezone aware.

    Args:
        value: The datetime string or datetime object to parse.
        format: The format string to use for parsing.

    Returns:
        A timezone-aware datetime object or None if parsing fails.
    """
    if value is None:
        return None
    # convert to datetime
    if isinstance(value, str):
        val = datetime.strptime(value, format)
    elif isinstance(value, datetime):
        val = value
    else:
        raise ValueError("Value must be a string or datetime object.")

    # check the time zone
    if val.tzinfo is None:
        val = val.replace(tzinfo=UTC)
    else:
        val = val.astimezone(UTC)
    return val
