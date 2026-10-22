import io

import pandas as pd
import pytest

from crosscontract.exceptions import FileReadError
from crosscontract.handlers.readers import (
    read_csv_file,
    read_csv_file_bytes,
    read_parquet_file,
    read_parquet_file_bytes,
)


def parquet_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False, engine="pyarrow")
    return buffer.getvalue()


class TestReadCsv:
    def test_valid_csv(self):
        df = read_csv_file_bytes(b"col1,col2,col3\n1,2,3\n4,5,6")

        assert df.shape == (2, 3)
        assert list(df.columns) == ["col1", "col2", "col3"]
        assert df.iloc[0]["col1"] == 1

    def test_na_stays_a_string(self):
        df = read_csv_file_bytes(b"country,code\nNamibia,NA")

        assert df.loc[0, "code"] == "NA"

    def test_empty_cell_becomes_missing(self):
        df = read_csv_file_bytes(b"col1,col2\n1,\n2,3")

        assert pd.isna(df.loc[0, "col2"])
        assert pd.api.types.is_numeric_dtype(df["col2"])

    @pytest.mark.parametrize(
        "token",
        [
            "#N/A N/A",
            "#NA",
            "-1.#IND",
            "-1.#QNAN",
            "-NaN",
            "-nan",
            "1.#IND",
            "1.#QNAN",
            "<NA>",
            "N/A",
            "NULL",
            "NaN",
            "None",
            "n/a",
            "nan",
            "null",
            "undefined",
        ],
    )
    def test_former_na_tokens_stay_strings(self, token: str):
        df = read_csv_file_bytes(f"col1,col2\n1,{token}".encode())

        assert df.loc[0, "col2"] == token

    def test_invalid_encoding(self):
        with pytest.raises(FileReadError, match="Invalid file encoding"):
            read_csv_file_bytes(b"\xff\xfe\x00\x00")

    def test_bad_line(self):
        with pytest.raises(FileReadError, match="Invalid CSV format"):
            read_csv_file_bytes(b"col1,col2\n1,2\n1,2,3\n1,2")

    def test_empty_input(self):
        with pytest.raises(FileReadError, match="Could not parse file"):
            read_csv_file_bytes(b"")

    def test_file(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_bytes(b"col1\n1")

        assert read_csv_file(path).equals(read_csv_file_bytes(b"col1\n1"))

    def test_missing_file_propagates(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_csv_file(tmp_path / "missing.csv")


class TestReadParquet:
    def test_valid_parquet(self):
        source = pd.DataFrame({"col1": [1, 4], "col2": [2.5, 5.5], "col3": ["a", "b"]})

        pd.testing.assert_frame_equal(
            read_parquet_file_bytes(parquet_bytes(source)), source
        )

    @pytest.mark.parametrize("data", [b"this is not parquet", b""])
    def test_invalid_or_empty(self, data: bytes):
        with pytest.raises(FileReadError, match="Invalid Parquet format"):
            read_parquet_file_bytes(data)

    def test_corrupted_footer(self):
        data = parquet_bytes(pd.DataFrame({"a": range(100), "b": ["x"] * 100}))
        corrupted = data[:-12] + b"\x00" * 8 + data[-4:]

        with pytest.raises(FileReadError, match="Invalid Parquet format"):
            read_parquet_file_bytes(corrupted)

    def test_file(self, tmp_path):
        source = pd.DataFrame({"col1": [1, 4]})
        path = tmp_path / "data.parquet"
        path.write_bytes(parquet_bytes(source))

        pd.testing.assert_frame_equal(read_parquet_file(path), source)

    def test_missing_file_propagates(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_parquet_file(tmp_path / "missing.parquet")
