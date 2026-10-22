import crosscontract.handlers as handlers
import crosscontract.handlers.readers as readers
import crosscontract.handlers.submission as submission


def test_exported_from_handlers_package():
    assert handlers.SubmissionHandler is submission.SubmissionHandler
    assert handlers.read_excel_bundle is submission.read_excel_bundle
    assert handlers.read_excel_bundle_bytes is submission.read_excel_bundle_bytes
    assert "SubmissionHandler" in handlers.__all__
    assert "read_excel_bundle" in handlers.__all__
    assert "read_excel_bundle_bytes" in handlers.__all__


def test_readers_exported_from_handlers_package():
    for name in (
        "read_csv_file",
        "read_csv_file_bytes",
        "read_parquet_file",
        "read_parquet_file_bytes",
    ):
        assert getattr(handlers, name) is getattr(readers, name)
        assert name in handlers.__all__
