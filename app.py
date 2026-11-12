
import io
import streamlit as st
from docxtpl import DocxTemplate

from app.reader import read_table, TableReadError
from app.generator import (
    generate_documents,
    DocumentGenerationError,
)
from app.logger import get_logger
from app.config import MAX_UPLOAD_BYTES, validate_upload_size


logger = get_logger()

st.set_page_config(
    page_title="DocFlow",
    page_icon="📄",
    layout="wide",
)
st.title("📄 DocFlow")
st.subheader("Автоматическая генерация Word-документов")
st.caption(
    "Загрузи таблицу с данными и Word-шаблон. "
    "DocFlow создаст отдельный документ для каждой строки."
)

st.divider()

# Шаг 1. Загрузка таблицы
st.header("1. Загрузка данных")

table_file = st.file_uploader(
    "Выбери Excel или CSV",
    type=["xlsx", "xls", "csv"],
    max_upload_size=MAX_UPLOAD_BYTES // (1024 * 1024),
    help="Первая строка таблицы должна содержать названия столбцов.",
)

dataframe = None

if table_file is not None:
    try:
        dataframe = read_table(table_file)

        st.success(
            f"Таблица загружена: {len(dataframe)} строк, "
            f"{len(dataframe.columns)} столбцов."
        )

        st.write("Предварительный просмотр:")
        st.dataframe(
            dataframe.head(10),
            width="stretch",
        )

        with st.expander("Показать названия столбцов"):
            st.write(list(dataframe.columns))

        logger.info(
            "Таблица успешно загружена: %s строк, %s столбцов",
            len(dataframe),
            len(dataframe.columns),
        )

    except TableReadError as error:
        st.error(str(error))
        logger.warning("Ошибка чтения таблицы: %s", error)

    except Exception:
        st.error("Произошла непредвиденная ошибка при чтении таблицы.")
        logger.exception("Непредвиденная ошибка чтения таблицы")


st.divider()

# Шаг 2. Загрузка Word-шаблона
st.header("2. Загрузка Word-шаблона")

template_file = st.file_uploader(
    "Выбери Word-шаблон (.docx)",
    type=["docx"],
    max_upload_size=MAX_UPLOAD_BYTES // (1024 * 1024),
    help="Используй переменные вида {{ name }} в документе.",
    key="template_upload",
)

template_bytes = None
template_variables = set()

if template_file is not None:
    template_bytes = template_file.getvalue()

    try:
        validate_upload_size(template_bytes, label="Word-шаблон")
        template = DocxTemplate(io.BytesIO(template_bytes))
        template_variables = (
            template.get_undeclared_template_variables()
        )

        st.success("Word-шаблон успешно прочитан.")

        if template_variables:
            st.write("Переменные, найденные в шаблоне:")
            st.code(", ".join(sorted(template_variables)))
        else:
            st.warning(
                "В шаблоне не найдены переменные вида {{ name }}."
            )

        logger.info(
            "Word-шаблон загружен, найдено переменных: %s",
            len(template_variables),
        )

    except ValueError as error:
        st.error(str(error))
        template_bytes = None
    except Exception:
        st.error(
            "Не удалось прочитать Word-шаблон. "
            "Проверь, что это корректный DOCX-файл."
        )
        logger.exception("Ошибка чтения Word-шаблона")
        template_bytes = None


st.divider()

# Шаг 3. Проверка переменных
st.header("3. Проверка шаблона")

variables_valid = False

if dataframe is not None and template_bytes is not None:
    missing_variables = (
        template_variables - set(dataframe.columns)
    )

    if missing_variables:
        st.error(
            "В таблице отсутствуют столбцы, необходимые шаблону:"
        )
        st.write(sorted(missing_variables))
        st.caption(
            "Добавь недостающие столбцы или исправь названия "
            "переменных в Word-шаблоне."
        )
    elif not template_variables:
        st.warning(
            "Добавь в Word-шаблон переменные, например {{ name }}."
        )
    else:
        st.success(
            "Все переменные шаблона найдены в таблице. "
            "Можно создавать документы."
        )
        variables_valid = True

elif dataframe is None or template_bytes is None:
    st.info("Для проверки загрузи таблицу и Word-шаблон.")


st.divider()

# Шаг 4. Генерация документов
st.header("4. Генерация документов")

if dataframe is not None and template_bytes is not None:
    filename_options = ["Автоматическая нумерация"] + list(
        dataframe.columns
    )

    filename_choice = st.selectbox(
        "Как называть созданные документы?",
        options=filename_options,
        help=(
            "Можно использовать значение одного из столбцов "
            "таблицы, например name."
        ),
    )

    filename_column = (
        None
        if filename_choice == "Автоматическая нумерация"
        else filename_choice
    )

    if st.button(
        "🚀 Создать документы",
        type="primary",
        disabled=not variables_valid,
        width="stretch",
    ):
        try:
            with st.spinner(
                f"Создаём {len(dataframe)} документов..."
            ):
                archive_bytes, generated_files = generate_documents(
                    template_bytes=template_bytes,
                    dataframe=dataframe,
                    filename_column=filename_column,
                )

            st.success(
                f"Готово! Создано документов: {len(generated_files)}."
            )

            st.download_button(
                label="📦 Скачать ZIP-архив",
                data=archive_bytes,
                file_name="docflow_documents.zip",
                mime="application/zip",
                type="primary",
                width="stretch",
            )

            with st.expander("Список созданных документов"):
                for filename in generated_files:
                    st.write(f"📄 {filename}")

            logger.info(
                "Генерация завершена: создано %s документов",
                len(generated_files),
            )

        except DocumentGenerationError as error:
            st.error(str(error))
            logger.error("Ошибка генерации: %s", error)

        except Exception:
            st.error(
                "Произошла непредвиденная ошибка. "
                "Подробности записаны в журнал."
            )
            logger.exception("Непредвиденная ошибка генерации")

else:
    st.info(
        "Загрузи таблицу и Word-шаблон, чтобы перейти к генерации."
    )

st.divider()

st.caption("DocFlow MVP · Локальная обработка документов")
