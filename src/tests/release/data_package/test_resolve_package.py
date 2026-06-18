import io
import json
import zipfile

import pandas as pd
import pytest
import yaml

from crosscontract._standards.frictionless import DataPackage
from crosscontract.release.data_package._resolve_package import save_data_package
from crosscontract.release.data_package._resolve_resource import build_data_resource


@pytest.fixture
def make_resources(make_resource_spec, make_var_for_contract, contract_factory):
    """Factory for the resources mapping the orchestrator hands to the saver."""

    def _make(fmt: str = "csv") -> tuple[dict, pd.DataFrame]:
        df = pd.DataFrame({"id": ["a", "b"]})
        var = make_var_for_contract(contract_factory.build())
        resource = build_data_resource(make_resource_spec(fmt=fmt), var)
        mapping = {resource.name: {"data_resource": resource, "data": df}}
        return mapping, df

    return _make


class TestSaveDataPackage:
    def test_creates_zip_with_expected_members(
        self, tmp_path, make_resources, make_package_spec
    ):
        mapping, _ = make_resources()
        out = tmp_path / "pkg.zip"

        save_data_package(make_package_spec(), mapping, out)

        assert out.exists()
        with zipfile.ZipFile(out) as zf:
            names = set(zf.namelist())
        assert {"datapackage.json", "datapackage.yaml", "my_resource.csv"} <= names

    def test_data_file_matches(self, tmp_path, make_resources, make_package_spec):
        mapping, df = make_resources()
        out = tmp_path / "pkg.zip"

        save_data_package(make_package_spec(), mapping, out)

        with zipfile.ZipFile(out) as zf:
            written = pd.read_csv(io.BytesIO(zf.read("my_resource.csv")))
        pd.testing.assert_frame_equal(written, df)

    def test_descriptor_roundtrips_as_frictionless(
        self, tmp_path, make_resources, make_package_spec
    ):
        mapping, _ = make_resources()
        out = tmp_path / "pkg.zip"

        save_data_package(make_package_spec(), mapping, out)

        with zipfile.ZipFile(out) as zf:
            descriptor = json.loads(zf.read("datapackage.json"))
        pkg = DataPackage.model_validate(descriptor)
        assert pkg.name == "test-package"
        assert pkg.resources[0].name == "my_resource"

    def test_json_and_yaml_descriptors_match(
        self, tmp_path, make_resources, make_package_spec
    ):
        mapping, _ = make_resources()
        out = tmp_path / "pkg.zip"

        save_data_package(make_package_spec(), mapping, out)

        with zipfile.ZipFile(out) as zf:
            from_json = json.loads(zf.read("datapackage.json"))
            from_yaml = yaml.safe_load(zf.read("datapackage.yaml"))
        assert from_json == from_yaml

    def test_no_suffix_appends_zip(self, tmp_path, make_resources, make_package_spec):
        mapping, _ = make_resources()

        save_data_package(make_package_spec(), mapping, tmp_path / "pkg")

        assert (tmp_path / "pkg.zip").exists()

    def test_wrong_suffix_raises(self, tmp_path, make_resources, make_package_spec):
        mapping, _ = make_resources()

        with pytest.raises(ValueError, match="zip extension"):
            save_data_package(make_package_spec(), mapping, tmp_path / "pkg.tar")

    def test_unsupported_format_raises(
        self, tmp_path, make_resources, make_package_spec
    ):
        mapping, _ = make_resources()
        # Mutate the built resource to an unsupported format to reach the
        # defensive branch (DataResource.format is an unconstrained str).
        next(iter(mapping.values()))["data_resource"].format = "xml"

        with pytest.raises(ValueError, match="Unsupported data format"):
            save_data_package(make_package_spec(), mapping, tmp_path / "pkg.zip")

    def test_parquet_resource_written(
        self, tmp_path, make_resources, make_package_spec
    ):
        pytest.importorskip("pyarrow")
        mapping, df = make_resources(fmt="parquet")
        out = tmp_path / "pkg.zip"

        save_data_package(make_package_spec(), mapping, out)

        with zipfile.ZipFile(out) as zf:
            written = pd.read_parquet(io.BytesIO(zf.read("my_resource.parquet")))
        pd.testing.assert_frame_equal(written, df)
