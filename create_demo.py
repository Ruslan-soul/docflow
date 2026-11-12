
from docx import Document

document = Document()

document.add_heading("КАРТОЧКА СОТРУДНИКА", level=1)

document.add_paragraph("ФИО: {{ name }}")
document.add_paragraph("Компания: {{ company }}")
document.add_paragraph("Должность: {{ position }}")

document.add_paragraph(
    "Документ сформирован автоматически с помощью DocFlow."
)

document.save("demo_template.docx")

print("Готово! Шаблон demo_template.docx создан.")
