import crosscontract.handlers as handlers
import crosscontract.handlers.submission as submission


def test_exported_from_handlers_package():
    assert handlers.SubmissionHandler is submission.SubmissionHandler
    assert handlers.read_excel_bundle is submission.read_excel_bundle
    assert handlers.read_excel_bundle_bytes is submission.read_excel_bundle_bytes
    assert "SubmissionHandler" in handlers.__all__
    assert "read_excel_bundle" in handlers.__all__
    assert "read_excel_bundle_bytes" in handlers.__all__
