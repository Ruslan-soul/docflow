"""Automated browser-free end-to-end checks of the Streamlit workflow."""

import io
from pathlib import Path

from docx import Document
from streamlit.testing.v1 import AppTest


def make_template() -> bytes:
    document = Document()
    document.add_paragraph("Hello {{ name }}")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_streamlit_workflow_generates_downloadable_archive():
    app = AppTest.from_file(
        Path(__file__).resolve().parents[1] / "app.py",
        default_timeout=15,
    ).run()
    assert not app.exception

    app.file_uploader[0].set_value(("clients.csv", b"name\nAda\n", "text/csv"))
    app.file_uploader[1].set_value(
        (
            "template.docx",
            make_template(),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    )
    app.run()

    assert not app.exception
    assert any("Все переменные шаблона найдены" in item.value for item in app.success)
    app.button[0].click().run()

    assert not app.exception
    assert any("Создано документов: 1" in item.value for item in app.success)
    downloads = app.get("download_button")
    assert len(downloads) == 1
    assert downloads[0].proto.url.startswith("/mock/media/")
    assert downloads[0].proto.url.endswith(".zip")
