import io
import zipfile
from pathlib import Path

from docx import Document
from docxtpl import DocxTemplate

from app.generator import generate_documents
from app.reader import read_table


class DemoUpload:
    def __init__(self, name: str, content: bytes):
        self.name = name
        self._content = content

    def read(self) -> bytes:
        return self._content


def test_bundled_demo_files_generate_documents():
    project_root = Path(__file__).resolve().parents[1]
    table_bytes = (project_root / "demo_clients.csv").read_bytes()
    template_bytes = (project_root / "demo_template.docx").read_bytes()

    dataframe = read_table(DemoUpload("demo_clients.csv", table_bytes))
    template_variables = DocxTemplate(io.BytesIO(template_bytes)).get_undeclared_template_variables()
    assert template_variables <= set(dataframe.columns)

    archive_bytes, filenames = generate_documents(
        template_bytes,
        dataframe,
        filename_column="name",
    )

    assert len(filenames) == len(dataframe) == 2
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        assert set(archive.namelist()) == set(filenames)
        document = Document(io.BytesIO(archive.read(filenames[0])))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        assert "Тестовый клиент 1" in text
