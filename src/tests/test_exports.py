import crosscontract


def test_root_exports_only_entry_points_and_contracts():
    assert set(crosscontract.__all__) == {
        "CrossClient",
        "CrossContract",
        "CrossReader",
        "CrossRegistry",
        "CrossSubmitter",
        "SubmissionContract",
    }
