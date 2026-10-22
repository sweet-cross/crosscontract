import crosscontract.handlers as handlers
import crosscontract.handlers.readers as readers


def test_exported_from_handlers_package():
    assert "SubmissionHandler" in handlers.__all__


def test_readers_exported_from_handlers_package():
    for name in (
        "read_csv_file",
        "read_csv_file_bytes",
        "read_excel_bundle",
        "read_excel_bundle_bytes",
        "read_excel_workbook_bytes",
        "read_parquet_file",
        "read_parquet_file_bytes",
    ):
        assert getattr(handlers, name) is getattr(readers, name)
        assert name in handlers.__all__
