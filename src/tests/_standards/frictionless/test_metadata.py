import pytest
from pydantic import ValidationError

from crosscontract._standards.frictionless import (
    Contributor,
    FileMetaData,
    License,
    PackageMetaData,
    ResourceMetaData,
    Source,
    TableSchema,
)


class TestSource:
    """The `sources[]` leaf model."""

    def test_title_is_required(self):
        with pytest.raises(ValidationError):
            Source()

    def test_optional_fields_default_to_none(self):
        source = Source(title="World Bank")
        assert source.path is None
        assert source.email is None


class TestLicense:
    """A license requires at least `name` or `path`."""

    def test_name_only_is_valid(self):
        assert License(name="CC-BY-4.0").path is None

    def test_path_only_is_valid(self):
        assert License(path="http://example.com/license").name is None

    def test_neither_is_rejected(self):
        with pytest.raises(ValidationError):
            License(title="just a title")

    def test_name_pattern_is_enforced(self):
        with pytest.raises(ValidationError):
            License(name="not a license id")


class TestContributor:
    """The permissive contributor keeps `role` free-form."""

    def test_role_defaults_to_contributor(self):
        assert Contributor(title="Joe Bloggs").role == "contributor"

    def test_role_accepts_arbitrary_string(self):
        assert Contributor(title="Joe", role="wrangler").role == "wrangler"

    def test_title_is_required(self):
        with pytest.raises(ValidationError):
            Contributor()


class TestFileMetaData:
    """The physical data binding, usable on its own."""

    def test_path_string_becomes_one_element_list(self):
        assert FileMetaData(path="file.csv").path == ["file.csv"]

    def test_path_list_is_unchanged(self):
        assert FileMetaData(path=["a.csv", "b.csv"]).path == ["a.csv", "b.csv"]

    def test_single_path_serializes_as_scalar(self):
        assert FileMetaData(path="file.csv").model_dump()["path"] == "file.csv"

    def test_multipart_path_serializes_as_list(self):
        dumped = FileMetaData(path=["a.csv", "b.csv"]).model_dump()
        assert dumped["path"] == ["a.csv", "b.csv"]

    def test_string_path_roundtrips_as_string(self):
        original = FileMetaData(path="file.csv")
        assert FileMetaData.model_validate(original.model_dump()).path == ["file.csv"]

    def test_data_only_is_valid(self):
        binding = FileMetaData(data=[{"x": 1}])
        assert binding.path == []

    def test_neither_data_nor_path_is_rejected(self):
        with pytest.raises(ValidationError):
            FileMetaData()

    def test_mediatype_pattern_is_enforced(self):
        with pytest.raises(ValidationError):
            FileMetaData(path="file.csv", mediatype="notamediatype")

    def test_encoding_defaults_to_utf8(self):
        assert FileMetaData(path="file.csv").encoding == "utf-8"

    def test_extra_key_is_preserved(self):
        binding = FileMetaData(path="file.csv", custom="x")
        assert binding.model_dump()["custom"] == "x"


class TestResourceMetaData:
    """The descriptive metadata of a resource (no file binding)."""

    def test_name_is_required(self):
        with pytest.raises(ValidationError):
            ResourceMetaData()

    def test_name_pattern_is_enforced(self):
        with pytest.raises(ValidationError):
            ResourceMetaData(name="Not Valid")

    def test_profile_defaults_to_data_resource(self):
        assert ResourceMetaData(name="my-data").profile == "data-resource"

    def test_schema_alias_accepts_a_table_schema(self):
        meta = ResourceMetaData(name="my-data", schema={"fields": [{"name": "id"}]})
        assert isinstance(meta.table_schema, TableSchema)
        assert meta.table_schema.fields[0].name == "id"

    def test_schema_alias_accepts_a_path_string(self):
        meta = ResourceMetaData(name="my-data", schema="schema.json")
        assert meta.table_schema == "schema.json"

    def test_populate_by_name_accepts_python_name(self):
        meta = ResourceMetaData(
            name="my-data", table_schema={"fields": [{"name": "id"}]}
        )
        assert isinstance(meta.table_schema, TableSchema)

    def test_serializes_under_schema_alias(self):
        meta = ResourceMetaData(name="my-data", schema={"fields": [{"name": "id"}]})
        dumped = meta.model_dump(exclude_none=True)
        assert "schema" in dumped
        assert "table_schema" not in dumped


class TestPackageMetaData:
    """The descriptive metadata of a package (no `resources` array)."""

    def test_minimal_is_valid(self):
        meta = PackageMetaData()
        assert meta.name is None
        assert meta.profile == "data-package"

    def test_optional_lists_default_to_none_and_are_omitted(self):
        meta = PackageMetaData(name="my-package")
        assert meta.sources is None
        assert meta.licenses is None
        assert meta.contributors is None
        assert meta.keywords is None
        dumped = meta.model_dump(exclude_none=True)
        for key in ("sources", "licenses", "contributors", "keywords"):
            assert key not in dumped

    def test_name_pattern_is_enforced(self):
        with pytest.raises(ValidationError):
            PackageMetaData(name="Bad Name")

    def test_nested_models_are_parsed(self):
        meta = PackageMetaData(
            name="my-package",
            contributors=[{"title": "Joe Bloggs", "role": "author"}],
            licenses=[{"name": "CC-BY-4.0"}],
            sources=[{"title": "World Bank"}],
            keywords=["data", "fiscal"],
        )
        assert isinstance(meta.contributors[0], Contributor)
        assert isinstance(meta.licenses[0], License)
        assert isinstance(meta.sources[0], Source)
        assert meta.keywords == ["data", "fiscal"]
