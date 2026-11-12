import io
import zipfile

import pandas as pd
import pytest
from docx import Document

import app.generator as generator_module
from app.generator import (
    DocumentGenerationError,
    generate_documents,
    sanitize_filename,
)


def create_word_template():
    document = Document()
    document.add_paragraph("Здравствуйте, {{ name }}!")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_generate_documents():
    dataframe = pd.DataFrame({"name": ["Ivan", "Petr"]})
    archive_bytes, filenames = generate_documents(
        template_bytes=create_word_template(),
        dataframe=dataframe,
        filename_column="name",
    )

    assert filenames == ["Ivan.docx", "Petr.docx"]
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        assert len(archive.namelist()) == 2
        first_document = Document(io.BytesIO(archive.read("Ivan.docx")))
        text = "\n".join(paragraph.text for paragraph in first_document.paragraphs)
        assert "Ivan" in text
        assert "{{ name }}" not in text


def test_duplicate_filenames_are_unique():
    dataframe = pd.DataFrame({"name": ["Ivan", "Ivan"]})
    archive_bytes, filenames = generate_documents(
        template_bytes=create_word_template(),
        dataframe=dataframe,
        filename_column="name",
    )

    assert filenames == ["Ivan.docx", "Ivan_2.docx"]
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        assert len(archive.namelist()) == 2


def test_reject_empty_dataframe():
    with pytest.raises(DocumentGenerationError, match="Нет данных"):
        generate_documents(
            template_bytes=create_word_template(),
            dataframe=pd.DataFrame(columns=["name"]),
        )


def test_reject_dataframe_over_row_limit():
    dataframe = pd.DataFrame({"name": ["Ivan"] * 501})
    with pytest.raises(DocumentGenerationError, match="не более 500"):
        generate_documents(create_word_template(), dataframe)


def test_reject_archive_over_size_limit(monkeypatch):
    monkeypatch.setattr(generator_module, "MAX_ARCHIVE_BYTES", 1)
    with pytest.raises(DocumentGenerationError, match="ZIP-архива"):
        generate_documents(
            create_word_template(),
            pd.DataFrame({"name": ["Ivan"]}),
        )


def test_reject_invalid_docx():
    with pytest.raises(DocumentGenerationError, match="корректный DOCX"):
        generate_documents(b"not a docx", pd.DataFrame({"name": ["Ivan"]}))


def test_reserved_windows_names_are_safe():
    assert sanitize_filename("CON") == "_CON"


def test_generated_docx_escapes_xml_sensitive_values():
    dataframe = pd.DataFrame({"name": ["A & B <C>"]})
    archive_bytes, filenames = generate_documents(
        create_word_template(), dataframe, filename_column="name"
    )

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        document = Document(io.BytesIO(archive.read(filenames[0])))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "A & B <C>" in text


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("../folder/name", "_folder_name.docx"),
        (" report. ", "report.docx"),
        ("", "document.docx"),
        ("con.txt", "_con.txt.docx"),
    ],
)
def test_generated_filenames_are_sanitized(value, expected):
    archive_bytes, filenames = generate_documents(
        create_word_template(),
        pd.DataFrame({"name": [value]}),
        filename_column="name",
    )

    assert filenames == [expected]
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        assert archive.namelist() == [expected]
