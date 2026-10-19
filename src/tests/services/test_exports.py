import crosscontract
import crosscontract.services


def test_cross_reader_exported():
    assert "CrossReader" in crosscontract.__all__
    assert crosscontract.CrossReader is crosscontract.services.CrossReader


def test_create_data_package_only_in_services():
    assert "create_data_package" in crosscontract.services.__all__
    assert "create_data_package" not in crosscontract.__all__
