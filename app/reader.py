"""Read and validate CSV and Excel tables uploaded to DocFlow."""

import csv
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pandas as pd

from app.config import (
    MAX_TABLE_ROWS,
    MAX_UNPACKED_ARCHIVE_BYTES,
    validate_upload_size,
)

SUPPORTED_EXTENSIONS = {".xlsx", ".xls", ".csv"}


class TableReadError(Exception):
    """An uploaded table could not be read or failed validation."""


def _check_spreadsheet_container(content: bytes, extension: str) -> None:
    """Bound decompressed spreadsheet size before passing it to pandas."""
    if extension != ".xlsx":
        return
    try:
        with ZipFile(BytesIO(content)) as archive:
            unpacked_size = sum(item.file_size for item in archive.infolist())
            if unpacked_size > MAX_UNPACKED_ARCHIVE_BYTES:
                raise TableReadError(
                    "Распакованный размер таблицы превышает лимит 100 МБ."
                )
    except BadZipFile as error:
        raise TableReadError("Файл XLSX повреждён или имеет неверный формат.") from error


def read_table(file) -> pd.DataFrame:
    """Read CSV/XLS/XLSX, then validate headers, rows, and values."""
    filename = getattr(file, "name", "")
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise TableReadError("Поддерживаются только файлы XLSX, XLS и CSV.")

    try:
        if hasattr(file, "seek"):
            file.seek(0)
        content = file.read()
        validate_upload_size(content, label="Таблица")
        _check_spreadsheet_container(content, extension)
        buffer = BytesIO(content)

        if extension == ".csv":
            try:
                text = content.decode("utf-8-sig")
                encoding = "utf-8-sig"
            except UnicodeDecodeError:
                text = content.decode("cp1251")
                encoding = "cp1251"
            try:
                delimiter = csv.Sniffer().sniff(
                    text[:8192], delimiters=",;\t|"
                ).delimiter
            except csv.Error:
                delimiter = ","
            try:
                raw = pd.read_csv(
                    BytesIO(content),
                    sep=delimiter,
                    engine="python",
                    encoding=encoding,
                    header=None,
                    on_bad_lines="error",
                )
            except (pd.errors.ParserError, ValueError) as error:
                raise TableReadError(
                    "CSV имеет неверный формат: проверьте число столбцов и кавычки."
                ) from error
        else:
            raw = pd.read_excel(buffer, header=None)
    except TableReadError:
        raise
    except ValueError as error:
        raise TableReadError(str(error)) from error
    except Exception as error:
        raise TableReadError(f"Не удалось прочитать таблицу: {error}") from error

    if raw.empty or len(raw.columns) == 0:
        raise TableReadError("В таблице отсутствуют столбцы.")

    columns = [
        "" if pd.isna(column) else str(column).strip()
        for column in raw.iloc[0].tolist()
    ]
    if any(not column for column in columns):
        raise TableReadError(
            "Обнаружен столбец без названия. Заполните все заголовки."
        )
    if len(columns) != len(set(columns)):
        duplicates = sorted(
            {column for column in columns if columns.count(column) > 1}
        )
        raise TableReadError(
            "Обнаружены повторяющиеся названия столбцов: "
            + ", ".join(duplicates)
        )
    df = raw.iloc[1:].copy()
    df.columns = columns
    df = df.dropna(how="all")
    if df.empty:
        raise TableReadError("Таблица не содержит заполненных строк.")
    df = df.apply(
        lambda column: column.map(
            lambda value: value.strip() if isinstance(value, str) else value
        )
    )
    # A row containing only whitespace is blank after normalization too.
    df = df.replace("", pd.NA).dropna(how="all")
    if df.empty:
        raise TableReadError("Таблица не содержит заполненных строк.")
    if len(df) > MAX_TABLE_ROWS:
        raise TableReadError(
            f"В таблице {len(df)} строк. Максимум — {MAX_TABLE_ROWS} строк за один запуск."
        )
    return df
