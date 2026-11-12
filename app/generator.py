"""Generate one Word document per row and return them in a ZIP archive."""

import io
import re
import zipfile

import pandas as pd
from docxtpl import DocxTemplate

from app.config import (
    MAX_ARCHIVE_BYTES,
    MAX_TABLE_ROWS,
    MAX_UNPACKED_ARCHIVE_BYTES,
    MAX_UPLOAD_BYTES,
)


class DocumentGenerationError(Exception):
    """Document generation failed or the request exceeded a limit."""


def sanitize_filename(value: str) -> str:
    """Return a safe, readable Windows-compatible file name stem."""
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value).strip())
    value = value.strip(" .")
    value = re.sub(r"\s+", " ", value)
    if not value:
        return "document"
    reserved_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if value.split(".")[0].upper() in reserved_names:
        value = f"_{value}"
    return value[:100]


def _validate_template(template_bytes: bytes) -> None:
    if not template_bytes:
        raise DocumentGenerationError("Word-шаблон пуст.")
    if len(template_bytes) > MAX_UPLOAD_BYTES:
        raise DocumentGenerationError("Размер Word-шаблона превышает лимит 20 МБ.")
    try:
        with zipfile.ZipFile(io.BytesIO(template_bytes)) as package:
            unpacked_size = sum(item.file_size for item in package.infolist())
            if unpacked_size > MAX_UNPACKED_ARCHIVE_BYTES:
                raise DocumentGenerationError(
                    "Распакованный размер шаблона превышает лимит 100 МБ."
                )
            parts = package.namelist()
            if "[Content_Types].xml" not in parts or "word/document.xml" not in parts:
                raise DocumentGenerationError(
                    "Файл не похож на корректный DOCX-шаблон."
                )
            corrupt_part = package.testzip()
            if corrupt_part is not None:
                raise DocumentGenerationError(
                    "DOCX-шаблон повреждён и не может быть прочитан."
                )
    except zipfile.BadZipFile as error:
        raise DocumentGenerationError("Файл не похож на корректный DOCX-шаблон.") from error


def generate_documents(
    template_bytes: bytes,
    dataframe: pd.DataFrame,
    filename_column: str | None = None,
) -> tuple[bytes, list[str]]:
    """Generate DOCX files for validated rows and return a ZIP archive."""
    _validate_template(template_bytes)
    if not isinstance(dataframe, pd.DataFrame):
        raise DocumentGenerationError("Некорректный формат таблицы.")
    if dataframe.empty:
        raise DocumentGenerationError("Нет данных для генерации.")
    if len(dataframe) > MAX_TABLE_ROWS:
        raise DocumentGenerationError(
            f"Можно создать не более {MAX_TABLE_ROWS} документов за один запуск."
        )
    if filename_column and filename_column not in dataframe.columns:
        raise DocumentGenerationError(f"Столбец '{filename_column}' не найден в таблице.")

    archive_buffer = io.BytesIO()
    generated_files: list[str] = []
    used_names: set[str] = set()
    generated_document_bytes = 0
    try:
        with zipfile.ZipFile(
            archive_buffer,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
        ) as archive:
            for index, row in dataframe.iterrows():
                try:
                    template = DocxTemplate(io.BytesIO(template_bytes))
                    context = {
                        str(column): ("" if pd.isna(value) else str(value))
                        for column, value in row.items()
                    }
                    # Cell values are data. Escape XML-sensitive characters so
                    # values such as "A & B" cannot corrupt the DOCX package.
                    template.render(context, autoescape=True)
                    if filename_column:
                        base_name = sanitize_filename(
                            context.get(filename_column, "")
                        )
                    else:
                        base_name = f"document_{index + 1}"
                    filename = f"{base_name}.docx"
                    counter = 2
                    while filename.casefold() in used_names:
                        filename = f"{base_name}_{counter}.docx"
                        counter += 1
                    used_names.add(filename.casefold())
                    document_buffer = io.BytesIO()
                    template.save(document_buffer)
                    document_bytes = document_buffer.getvalue()
                    generated_document_bytes += len(document_bytes)
                    if generated_document_bytes > MAX_ARCHIVE_BYTES:
                        raise DocumentGenerationError(
                            "Размер ZIP-архива превысил лимит 100 МБ "
                            "по суммарному размеру документов."
                        )
                    archive.writestr(filename, document_bytes)
                    generated_files.append(filename)
                    if archive_buffer.tell() > MAX_ARCHIVE_BYTES:
                        raise DocumentGenerationError(
                            "Размер ZIP-архива превысил лимит 100 МБ."
                        )
                except DocumentGenerationError:
                    raise
                except Exception as error:
                    raise DocumentGenerationError(
                        f"Не удалось создать документ для строки {index + 1}. Проверь переменные и формат шаблона."
                    ) from error
    except DocumentGenerationError:
        raise
    except Exception as error:
        raise DocumentGenerationError("Не удалось создать ZIP-архив.") from error

    result = archive_buffer.getvalue()
    if len(result) > MAX_ARCHIVE_BYTES:
        raise DocumentGenerationError(
            "Размер ZIP-архива превысил лимит 100 МБ."
        )
    return result, generated_files
