import json
import zipfile
from unittest.mock import MagicMock, patch

import pandas as pd
import yaml

from crosscontract._standards.frictionless import DataPackage
from crosscontract.release.data_package.create_data_package import create_data_package
from crosscontract.release.data_package.release_specification import (
    CrossDataPackageReleaseSpec,
)

MODULE = "crosscontract.release.data_package.create_data_package"

_SPEC_DICT = {
    "name": "test-package",
    "title": "Test Package",
    "description": "A package for testing.",
    "resources": [{"data_instructions": {"fetch": {"contract": "my_resource"}}}],
}


class TestCreateDataPackage:
    @patch(f"{MODULE}.save_data_package")
    @patch(f"{MODULE}.resolve_resources")
    def test_spec_instance_passed_through(
        self, mock_resolve, mock_save, make_package_spec
    ):
        spec = make_package_spec()
        registry = MagicMock()
        mock_resolve.return_value = {"r": {}}

        create_data_package(registry=registry, release_spec=spec, fn_out="out.zip")

        # spec is used as-is (not reloaded) and delegation is wired correctly
        mock_resolve.assert_called_once_with(registry, spec, resolve_references=True)
        mock_save.assert_called_once_with(spec, {"r": {}}, "out.zip")

    @patch(f"{MODULE}.save_data_package")
    @patch(f"{MODULE}.resolve_resources")
    def test_resolve_references_flag_passed_through(
        self, mock_resolve, mock_save, make_package_spec
    ):
        spec = make_package_spec()
        registry = MagicMock()
        mock_resolve.return_value = {"r": {}}

        create_data_package(
            registry=registry,
            release_spec=spec,
            fn_out="out.zip",
            resolve_references=False,
        )

        mock_resolve.assert_called_once_with(registry, spec, resolve_references=False)

    @patch(f"{MODULE}.save_data_package")
    @patch(f"{MODULE}.resolve_resources")
    def test_loads_spec_from_yaml_path(self, mock_resolve, mock_save, tmp_path):
        mock_resolve.return_value = {}
        spec_file = tmp_path / "spec.yaml"
        spec_file.write_text(yaml.safe_dump(_SPEC_DICT))

        create_data_package(
            registry=MagicMock(), release_spec=spec_file, fn_out=tmp_path / "out.zip"
        )

        passed_spec = mock_resolve.call_args.args[1]
        assert isinstance(passed_spec, CrossDataPackageReleaseSpec)
        assert passed_spec.name == "test-package"
        # the same loaded spec instance flows on to the saver
        assert mock_save.call_args.args[0] is passed_spec

    @patch(f"{MODULE}.save_data_package")
    @patch(f"{MODULE}.resolve_resources")
    def test_loads_spec_from_json_str_path(self, mock_resolve, mock_save, tmp_path):
        mock_resolve.return_value = {}
        spec_file = tmp_path / "spec.json"
        spec_file.write_text(json.dumps(_SPEC_DICT))

        create_data_package(
            registry=MagicMock(),
            release_spec=str(spec_file),
            fn_out=str(tmp_path / "out.zip"),
        )

        passed_spec = mock_resolve.call_args.args[1]
        assert isinstance(passed_spec, CrossDataPackageReleaseSpec)
        assert passed_spec.name == "test-package"


class TestCreateDataPackageEndToEnd:
    """Full pipeline with real resolve/save, only the registry faked."""

    def test_produces_a_valid_package(
        self, tmp_path, make_package_spec, make_data_variable
    ):
        df = pd.DataFrame({"id": ["a", "b"]})
        registry = MagicMock()
        registry.__getitem__.side_effect = {
            "my_resource": make_data_variable(df)
        }.__getitem__
        out = tmp_path / "pkg.zip"

        create_data_package(
            registry=registry, release_spec=make_package_spec(), fn_out=out
        )

        assert out.exists()
        with zipfile.ZipFile(out) as zf:
            assert "my_resource.csv" in zf.namelist()
            descriptor = json.loads(zf.read("datapackage.json"))
        pkg = DataPackage.model_validate(descriptor)
        assert pkg.name == "test-package"
        assert pkg.resources[0].name == "my_resource"
