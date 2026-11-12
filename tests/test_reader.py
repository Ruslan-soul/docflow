import io

import pytest
from openpyxl import Workbook

from app.config import MAX_UPLOAD_BYTES
from app.reader import TableReadError, read_table


class FakeUpload:
    """Small stand-in for Streamlit's uploaded-file object."""

    def __init__(self, name, content):
        self.name = name
        self.content = content

    def read(self):
        return self.content


def test_read_csv():
    content = b"name,company\nIvan,Company A\nPetr,Company B\n"
    dataframe = read_table(FakeUpload("clients.csv", content))

    assert len(dataframe) == 2
    assert list(dataframe.columns) == ["name", "company"]
    assert dataframe.iloc[0]["name"] == "Ivan"


def test_read_semicolon_csv_with_cp1251_encoding():
    content = "name;company\nИван;Пример\n".encode("cp1251")
    dataframe = read_table(FakeUpload("clients.csv", content))

    assert dataframe.iloc[0]["name"] == "Иван"
    assert dataframe.iloc[0]["company"] == "Пример"


def test_read_xlsx():
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["name", "company"])
    sheet.append(["  Ivan  ", "Example LLC"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    dataframe = read_table(FakeUpload("clients.xlsx", buffer.getvalue()))

    assert dataframe.iloc[0]["name"] == "Ivan"
    assert dataframe.iloc[0]["company"] == "Example LLC"


def test_reject_unsupported_file():
    with pytest.raises(TableReadError, match="Поддерживаются"):
        read_table(FakeUpload("clients.txt", b"some data"))


def test_reject_empty_file():
    with pytest.raises(TableReadError, match="пуст"):
        read_table(FakeUpload("clients.csv", b""))


def test_reject_file_over_upload_limit():
    content = b"x" * (MAX_UPLOAD_BYTES + 1)
    with pytest.raises(TableReadError, match="20 МБ"):
        read_table(FakeUpload("clients.csv", content))


def test_reject_duplicate_headers_after_trimming():
    with pytest.raises(TableReadError, match="повторяющиеся"):
        read_table(FakeUpload("clients.csv", b"name, name\nIvan,Petr\n"))


def test_reject_exact_duplicate_headers():
    with pytest.raises(TableReadError, match="повторяющиеся"):
        read_table(FakeUpload("clients.csv", b"name,name\nIvan,Petr\n"))


def test_reject_table_over_row_limit():
    content = ("name\n" + "Ivan\n" * 501).encode()
    with pytest.raises(TableReadError, match="Максимум"):
        read_table(FakeUpload("clients.csv", content))


def test_whitespace_only_rows_are_ignored():
    content = b"name,company\n  , \t\nAda,Example\n   ,   \n"
    dataframe = read_table(FakeUpload("clients.csv", content))

    assert len(dataframe) == 1
    assert dataframe.iloc[0]["name"] == "Ada"


def test_reject_table_with_only_whitespace_rows():
    with pytest.raises(TableReadError, match="не содержит заполненных строк"):
        read_table(FakeUpload("clients.csv", b"name,company\n  , \t\n"))
