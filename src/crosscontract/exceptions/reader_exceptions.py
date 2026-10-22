"""The failure the file readers raise."""


class FileReadError(Exception):
    """Raised when a file's content cannot be read.

    Met when a file's content cannot be read as the expected format, or when a
    workbook does not match the contract's Excel layout. The message is the
    user-facing explanation.
    """
