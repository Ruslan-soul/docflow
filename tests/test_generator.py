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
        assert archive.testzip() is None
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


def test_reject_template_over_unpacked_size_limit(monkeypatch):
    monkeypatch.setattr(generator_module, "MAX_UNPACKED_ARCHIVE_BYTES", 1)
    with pytest.raises(DocumentGenerationError, match="Распакованный размер шаблона"):
        generate_documents(create_word_template(), pd.DataFrame({"name": ["Ada"]}))


def test_reject_docx_with_corrupt_zip_member():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("[Content_Types].xml", b"types")
        archive.writestr("word/document.xml", b"document")
    corrupt = bytearray(buffer.getvalue())
    with zipfile.ZipFile(io.BytesIO(corrupt)) as archive:
        offset = archive.getinfo("word/document.xml").header_offset
    name_size = int.from_bytes(corrupt[offset + 26 : offset + 28], "little")
    extra_size = int.from_bytes(corrupt[offset + 28 : offset + 30], "little")
    payload_offset = offset + 30 + name_size + extra_size
    corrupt[payload_offset] = ord("D")

    with pytest.raises(DocumentGenerationError, match="DOCX-шаблон повреждён"):
        generate_documents(bytes(corrupt), pd.DataFrame({"name": ["Ada"]}))


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


def test_filename_collisions_ignore_case():
    _, filenames = generate_documents(
        create_word_template(),
        pd.DataFrame({"name": ["Ada", "ada"]}),
        filename_column="name",
    )

    assert filenames == ["Ada.docx", "ada_2.docx"]


def test_duplicate_sanitized_names_get_unique_names():
    _, filenames = generate_documents(
        create_word_template(),
        pd.DataFrame({"name": ["../Ada", "..\\Ada"]}),
        filename_column="name",
    )
    assert filenames == ["_Ada.docx", "_Ada_2.docx"]


def test_generated_filename_stem_is_limited_to_100_characters():
    _, filenames = generate_documents(
        create_word_template(),
        pd.DataFrame({"name": ["x" * 120]}),
        filename_column="name",
    )

    assert len(filenames[0].removesuffix(".docx")) == 100
