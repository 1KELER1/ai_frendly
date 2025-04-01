import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
import subprocess
import time
import json
import re
from datetime import datetime


def create_ai_friendly_summary(directory, output_path, exclude_extensions, exclude_folders, exclude_files, progress, status_label):
    """Создает краткое описание проекта, оптимизированное для ИИ."""
    try:
        total_items = count_items(directory, exclude_folders)
        progress["maximum"] = total_items

        # Создаем структуру для хранения информации
        project_info = {
            "project_name": os.path.basename(directory),
            "structure": [],
            "key_files": {},
            "file_types": {},
            "summary": ""
        }

        # Получаем структуру проекта
        project_info["structure"] = generate_project_structure(directory, exclude_folders).split("\n")

        # Собираем информацию о файлах
        collect_file_info(directory, project_info, exclude_extensions, exclude_folders, exclude_files, progress)

        # Создаем краткое описание
        generate_summary(project_info)

        # Записываем в файл
        with open(output_path, "w", encoding="utf-8") as out:
            out.write(f"# Проект: {project_info['project_name']}\n\n")

            # Добавляем README если он есть
            if "readme_content" in project_info:
                out.write("## README\n\n")
                out.write(project_info["readme_content"] + "\n\n")

            # Добавляем сгенерированное описание
            out.write("## Краткое описание проекта\n\n")
            out.write(project_info["summary"] + "\n\n")

            # Добавляем структуру проекта
            out.write("## Структура проекта\n\n")
            out.write("```\n")
            out.write("\n".join(project_info["structure"]) + "\n")
            out.write("```\n\n")

            # Добавляем информацию о ключевых файлах
            out.write("## Ключевые файлы\n\n")
            for file_path, info in project_info["key_files"].items():
                out.write(f"### {os.path.basename(file_path)}\n\n")
                out.write(f"Путь: `{file_path}`\n\n")

                if info.get("docstring"):
                    out.write(f"Документация: {info['docstring']}\n\n")

                if info.get("classes"):
                    out.write(f"Классы: {', '.join(info['classes'])}\n\n")

                if info.get("functions"):
                    out.write(f"Функции: {', '.join(info['functions'])}\n\n")

                if info.get("summary"):
                    out.write(f"Описание: {info['summary']}\n\n")

                # Добавляем код с выделением синтаксиса
                if info.get("content"):
                    out.write(f"```{info.get('language', 'python')}\n")
                    out.write(info["content"] + "\n")
                    out.write("```\n\n")

        progress["value"] = total_items
        progress.update_idletasks()
        status_label.config(text="✅ Готово!")
        messagebox.showinfo("Готово", f"Краткое описание сохранено в {output_path}")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Произошла ошибка при создании краткого описания: {e}")
        status_label.config(text="❌ Ошибка!")


def collect_file_info(directory, project_info, exclude_extensions, exclude_folders, exclude_files, progress):
    """Собирает информацию о файлах проекта."""
    # Найдем README файл
    readme_path = find_readme(directory)
    if readme_path:
        try:
            with open(readme_path, "r", encoding="utf-8") as readme_file:
                project_info["readme_content"] = readme_file.read()
        except Exception:
            project_info["readme_content"] = "[Ошибка чтения README]"

    # Список приоритетных файлов и расширений
    priority_files = ["settings.py", "urls.py", "models.py", "views.py", "main.py", "app.py", "index.py"]
    priority_extensions = [".py", ".js", ".html", ".css", ".java"]

    # Счетчик файлов
    file_count = 0

    # Обходим директорию
    for root, dirs, files in os.walk(directory):
        # Исключаем папки
        dirs[:] = [d for d in dirs if d not in exclude_folders]

        for file in files:
            # Add check for excluded files
            if file in exclude_files:
                continue
            file_path = os.path.join(root, file)
            ext = os.path.splitext(file)[1].lower()

            # Пропускаем исключенные расширения
            if ext in exclude_extensions:
                continue

            # Учитываем этот тип файла
            project_info["file_types"].setdefault(ext, 0)
            project_info["file_types"][ext] += 1

            # Определяем, является ли файл ключевым
            is_key_file = file in priority_files or ext in priority_extensions

            # Ограничиваем количество ключевых файлов
            if is_key_file and len(project_info["key_files"]) < 10:
                language = get_language_by_extension(ext)
                file_info = {
                    "language": language,
                    "size": os.path.getsize(file_path)
                }

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        file_info["content"] = content

                        # Для Python файлов извлекаем дополнительную информацию
                        if language == "python":
                            code_info = extract_functions_and_classes(content, language)
                            file_info.update(code_info)
                            file_info["docstring"] = extract_docstring(content, language)

                            # Генерируем краткое описание файла
                            file_info[
                                "summary"] = f"Файл содержит {len(code_info.get('functions', []))} функций и {len(code_info.get('classes', []))} классов."
                except Exception:
                    file_info["content"] = "[Ошибка чтения файла]"

                project_info["key_files"][file_path] = file_info

            file_count += 1
            progress["value"] += 1
            progress.update_idletasks()

    # Добавляем общую статистику
    project_info["total_files"] = file_count


def generate_summary(project_info):
    """Генерирует краткое описание проекта."""
    summary = []

    # Добавляем информацию о количестве файлов
    summary.append(f"Проект содержит всего {project_info['total_files']} файлов.")

    # Добавляем информацию о типах файлов
    file_types = project_info.get("file_types", {})
    if file_types:
        summary.append("Распределение по типам файлов:")
        for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True)[:5]:
            summary.append(f"- {ext}: {count} файлов")

    # Добавляем информацию о ключевых файлах
    key_files = project_info.get("key_files", {})
    if key_files:
        summary.append("\nКлючевые файлы проекта:")
        for file_path, info in key_files.items():
            summary.append(f"- {os.path.basename(file_path)}: {info.get('summary', 'Файл проекта')}")

    # Объединяем всё в одну строку
    project_info["summary"] = "\n".join(summary)

def collect_files_by_type(directory, grouped_files, exclude_extensions, exclude_folders, exclude_files):
    """Собирает файлы по типам расширений."""
    try:
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in exclude_folders]  # Исключаем папки
            for file in files:
                # Add check for excluded files
                if file in exclude_files:
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext in exclude_extensions:
                    continue
                file_path = os.path.join(root, file)
                grouped_files.setdefault(ext, []).append(file_path)
    except Exception:
        pass  # Игнорируем ошибки при сканировании

def scan_folder_json(directory, files_list, exclude_extensions, exclude_folders, exclude_files, max_file_size, progress):
    try:
        items = os.listdir(directory)
        for item in items:
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                if item in exclude_folders:
                    continue
                scan_folder_json(item_path, files_list, exclude_extensions, exclude_folders, exclude_files, max_file_size, progress)
            else:
                # Add check for excluded files
                if item in exclude_files:
                    continue
                ext = os.path.splitext(item)[1].lower()
                if ext in exclude_extensions:
                    continue
                file_data = {
                    "path": item_path,
                    "name": item,
                    "extension": ext,
                    "language": get_language_by_extension(ext),
                    "size": os.path.getsize(item_path),
                    "modified": time.ctime(os.path.getmtime(item_path))
                }
                try:
                    with open(item_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        if max_file_size > 0 and len(content) > max_file_size:
                            file_data["content"] = content[:max_file_size]
                            file_data["truncated"] = True
                            file_data["original_size"] = len(content)
                        else:
                            file_data["content"] = content
                            file_data["truncated"] = False
                except Exception as e:
                    file_data["error"] = str(e)
                files_list.append(file_data)
            progress["value"] += 1
            progress.update_idletasks()
    except PermissionError:
        files_list.append({"error": f"Ошибка доступа к папке: {directory}"})
    except Exception as e:
        files_list.append({"error": f"Ошибка обработки папки {directory}: {e}"})

def scan_folder(directory, out, exclude_extensions, exclude_folders, exclude_files, max_file_size, include_metadata, progress, level=0):
    indent = "    " * level
    try:
        items = os.listdir(directory)
        for item in items:
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                if item in exclude_folders:
                    continue
                out.write(f"{indent}📂 {item}/\n")
                scan_folder(item_path, out, exclude_extensions, exclude_folders, exclude_files, max_file_size, include_metadata, progress, level + 1)
            else:
                # Add check for excluded files
                if item in exclude_files:
                    continue
                ext = os.path.splitext(item)[1].lower()
                if ext in exclude_extensions:
                    continue
                out.write(f"{indent}📄 {item}\n")
                language = get_language_by_extension(ext)
                process_file(item_path, out, max_file_size, include_metadata, ext, language, progress)
            progress["value"] += 1
            progress.update_idletasks()
    except PermissionError:
        out.write(f"{indent}[Ошибка доступа к папке: {directory}]\n\n")
    except Exception as e:
        out.write(f"{indent}[Ошибка обработки папки {directory}: {e}]\n\n")


def create_context_menu(widget):
    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="Копировать", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="Вставить", command=lambda: widget.event_generate("<<Paste>>"))
    menu.add_command(label="Вырезать", command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_command(label="Выделить всё", command=lambda: widget.select_range(0, 'end'))

    def show_menu(event):
        menu.tk_popup(event.x_root, event.y_root)

    widget.bind("<Button-3>", show_menu)  # ПКМ вызывает меню


def enable_copy_paste(widget):
    """Добавляет поддержку Ctrl+C, Ctrl+V, Ctrl+X в русской раскладке, но не дублирует в английской."""
    widget.bind("<Control-KeyPress>", on_ctrl_key)


def on_ctrl_key(event):
    """Обрабатывает нажатие Ctrl + <клавиша>, работая только в русской раскладке."""

    if event.keycode == 67:  # Русская "С" (копировать)
        event.widget.event_generate("<<Copy>>")
        return "break"
    elif event.keycode == 86:  # Русская "м" (вставить)
        event.widget.event_generate("<<Paste>>")
        return "break"
    elif event.keycode == 88:  # Русская "Ч" (вырезать)
        event.widget.event_generate("<<Cut>>")
        return "break"
    elif event.keycode == 65:  # Русская "Ф" (выделить всё)
        event.widget.select_range(0, 'end')
        return "break"


def get_language_by_extension(ext):
    """Определяет язык программирования по расширению файла."""
    language_map = {
        ".py": "python",
        ".js": "javascript",
        ".html": "html",
        ".css": "css",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".cs": "csharp",
        ".php": "php",
        ".rb": "ruby",
        ".go": "go",
        ".rs": "rust",
        ".ts": "typescript",
        ".json": "json",
        ".xml": "xml",
        ".md": "markdown",
        ".txt": "text",
        ".sh": "bash",
        ".bat": "batch",
        ".ps1": "powershell",
        ".sql": "sql",
        ".yaml": "yaml",
        ".yml": "yaml",
    }
    return language_map.get(ext.lower(), "text")


def extract_docstring(content, language):
    """Извлекает документацию из файла."""
    if language == "python":
        # Ищем строки документации Python
        docstring_pattern = r'"""(.*?)"""'
        docstrings = re.findall(docstring_pattern, content, re.DOTALL)
        if docstrings:
            return docstrings[0].strip()
    return ""


def extract_functions_and_classes(content, language):
    """Извлекает имена функций и классов из кода."""
    if language == "python":
        # Ищем определения функций и классов
        functions = re.findall(r'def\s+(\w+)\s*\(', content)
        classes = re.findall(r'class\s+(\w+)\s*[\(:]', content)
        return {
            "functions": functions,
            "classes": classes
        }
    return {"functions": [], "classes": []}


# Функция для генерации структуры проекта
def generate_project_structure(directory, exclude_folders, max_depth=10):
    """Генерирует текстовое представление структуры проекта."""
    result = []

    def _scan_dir(path, prefix="", depth=0):
        if depth > max_depth:
            return

        try:
            items = sorted(os.listdir(path))
            for i, item in enumerate(items):
                if item in exclude_folders:
                    continue

                item_path = os.path.join(path, item)
                is_last = i == len(items) - 1

                # Определяем префикс для текущего элемента
                curr_prefix = prefix + ("└── " if is_last else "├── ")
                result.append(curr_prefix + item)

                # Если это папка, рекурсивно сканируем
                if os.path.isdir(item_path):
                    # Следующий префикс для элементов в этой папке
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    _scan_dir(item_path, next_prefix, depth + 1)
        except PermissionError:
            result.append(prefix + f"[Ошибка доступа: {path}]")
        except Exception as e:
            result.append(prefix + f"[Ошибка: {e}]")

    _scan_dir(directory)
    return "\n".join(result)


# Функция для подсчёта всех элементов в папке
def count_items(directory, exclude_folders):
    total = 0
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in exclude_folders]  # Исключаем папки
        total += len(dirs) + len(files)  # Считаем и файлы, и папки
    return total


# Найти файл README в директории
def find_readme(directory):
    """Ищет файл README в директории."""
    for item in os.listdir(directory):
        if item.lower().startswith("readme"):
            return os.path.join(directory, item)
    return None


# Функция обработки файлов
def process_directory(directory, output_path, exclude_extensions, exclude_folders, exclude_files,
                      max_file_size, output_format, group_by_type, prioritize_files,
                      include_metadata, progress, status_label):
    try:
        total_items = count_items(directory, exclude_folders)  # Считаем файлы и папки
        progress["maximum"] = total_items  # Устанавливаем правильное максимальное значение

        # Проверяем формат выходного файла
        if output_format == "txt":
            with open(output_path, "w", encoding="utf-8") as out:
                # Добавляем заголовок и метаданные
                out.write("=" * 80 + "\n")
                out.write(f"ПРОЕКТ: {os.path.basename(directory)}\n")
                out.write(f"ДАТА СКАНИРОВАНИЯ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                out.write("=" * 80 + "\n\n")

                # Добавляем README если он есть
                readme_path = find_readme(directory)
                if readme_path:
                    try:
                        with open(readme_path, "r", encoding="utf-8") as readme_file:
                            readme_content = readme_file.read()
                            out.write("README:\n")
                            out.write("=" * 80 + "\n")
                            out.write(readme_content)
                            out.write("\n\n" + "=" * 80 + "\n\n")
                    except Exception as e:
                        out.write(f"[Ошибка чтения README: {e}]\n\n")

                # Генерируем структуру проекта
                out.write("СТРУКТУРА ПРОЕКТА:\n")
                out.write("=" * 80 + "\n")
                project_structure = generate_project_structure(directory, exclude_folders)
                out.write(project_structure + "\n\n")
                out.write("=" * 80 + "\n\n")

                out.write("СОДЕРЖИМОЕ ФАЙЛОВ:\n")
                out.write("=" * 80 + "\n\n")

                # Если нужно группировать по типу
                if group_by_type:
                    grouped_files = {}
                    # Сначала собираем все файлы по типам
                    collect_files_by_type(directory, grouped_files, exclude_extensions, exclude_folders, exclude_files)

                    # Затем выводим их группами
                    for ext, files in grouped_files.items():
                        language = get_language_by_extension(ext)
                        out.write(f"\n{'-' * 40}\n")
                        out.write(f"ФАЙЛЫ ТИПА: {ext} ({language})\n")
                        out.write(f"{'-' * 40}\n\n")

                        for file_path in files:
                            process_file(file_path, out, max_file_size, include_metadata,
                                         ext, language, progress)
                else:
                    # Если нужно приоритизировать файлы
                    if prioritize_files:
                        priority_list = prioritize_files.split(",")
                        for priority_file in priority_list:
                            priority_file = priority_file.strip()
                            if not priority_file:
                                continue

                            # Ищем файлы с таким именем
                            for root, _, files in os.walk(directory):
                                for file in files:
                                    if file == priority_file:
                                        file_path = os.path.join(root, file)
                                        ext = os.path.splitext(file)[1].lower()
                                        language = get_language_by_extension(ext)

                                        out.write(f"\n{'-' * 40}\n")
                                        out.write(f"ПРИОРИТЕТНЫЙ ФАЙЛ: {file_path}\n")
                                        out.write(f"{'-' * 40}\n\n")

                                        process_file(file_path, out, max_file_size, include_metadata,
                                                     ext, language, progress)

                    # Обычный скан
                    scan_folder(directory, out, exclude_extensions, exclude_folders, exclude_files,
                                max_file_size, include_metadata, progress)

        elif output_format == "json":
            # Создаем структуру JSON
            project_data = {
                "project_name": os.path.basename(directory),
                "scan_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "structure": generate_project_structure(directory, exclude_folders).split("\n"),
                "files": []
            }

            # Добавляем README
            readme_path = find_readme(directory)
            if readme_path:
                try:
                    with open(readme_path, "r", encoding="utf-8") as readme_file:
                        project_data["readme"] = readme_file.read()
                except Exception:
                    project_data["readme"] = "[Ошибка чтения README]"

            # Сканируем файлы для JSON
            scan_folder_json(directory, project_data["files"], exclude_extensions,
                             exclude_folders, exclude_files, max_file_size, progress)

            # Записываем JSON в файл
            with open(output_path, "w", encoding="utf-8") as out:
                json.dump(project_data, out, ensure_ascii=False, indent=2)

        progress["value"] = total_items  # Делаем 100%, если вдруг не дошло
        progress.update_idletasks()
        status_label.config(text="✅ Готово!")
        messagebox.showinfo("Готово", f"Данные сохранены в {output_path}")
    except Exception as e:
        messagebox.showerror("Ошибка", f"Произошла ошибка: {e}")
        status_label.config(text="❌ Ошибка!")


# Функция для обработки отдельного файла
def process_file(file_path, out, max_file_size, include_metadata, ext, language, progress):
    try:
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)

        # Записываем разделитель и имя файла
        out.write(f"\n{'=' * 80}\n")
        out.write(f"ФАЙЛ: {file_path}\n")
        out.write(f"{'=' * 80}\n")

        # Добавляем метаданные если нужно
        if include_metadata:
            out.write(f"РАЗМЕР: {file_size} байт\n")
            out.write(f"ТИП: {language}\n")
            out.write(f"ПОСЛЕДНЕЕ ИЗМЕНЕНИЕ: {time.ctime(os.path.getmtime(file_path))}\n")
            out.write(f"{'-' * 80}\n\n")

        # Читаем содержимое файла
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

                # Если файл слишком большой, усекаем
                if max_file_size > 0 and len(content) > max_file_size:
                    preview = content[:max_file_size]
                    out.write(f"{preview}\n\n... (файл усечен, показано {max_file_size} из {len(content)} байт)\n")
                else:
                    # Если это код, добавляем маркеры языка
                    if language != "text":
                        # Извлекаем информацию о функциях и классах
                        code_info = extract_functions_and_classes(content, language)
                        docstring = extract_docstring(content, language)

                        # Добавляем информацию о файле
                        if code_info["functions"] or code_info["classes"]:
                            out.write("СОДЕРЖИТ:\n")
                            if code_info["classes"]:
                                out.write(f"Классы: {', '.join(code_info['classes'])}\n")
                            if code_info["functions"]:
                                out.write(f"Функции: {', '.join(code_info['functions'])}\n")
                            out.write("\n")

                        if docstring:
                            out.write(f"ДОКУМЕНТАЦИЯ:\n{docstring}\n\n")

                        out.write(f"```{language}\n{content}\n```\n\n")
                    else:
                        out.write(f"{content}\n\n")
        except Exception as e:
            out.write(f"[Ошибка чтения файла: {e}]\n\n")

        progress["value"] += 1
        progress.update_idletasks()
    except Exception as e:
        out.write(f"[Ошибка обработки файла {file_path}: {e}]\n\n")




# Открытие файла с помощью стандартной программы ОС
def open_file(file_path):
    if os.path.exists(file_path):
        if os.name == 'nt':  # Windows
            os.startfile(file_path)
        elif os.name == 'posix':  # macOS или Linux
            subprocess.call(('xdg-open', file_path))
    else:
        messagebox.showwarning("Предупреждение", "Файл не существует")

# GUI
def start_gui():
    global source_folder_var, output_file_var

    root = tk.Tk()
    root.title("AI-Friendly Копирование содержимого файлов")
    root.geometry("650x600")
    root.resizable(True, True)  # Разрешаем изменение размера окна

    # Настройка стилей
    style = ttk.Style()
    style.configure("TButton", padding=6, relief="flat", background="#ccc")
    style.configure("Green.TButton", foreground="white", background="green")
    style.configure("Blue.TButton", foreground="white", background="blue")

    # Создаем основной фрейм с отступами
    main_frame = ttk.Frame(root, padding="10 10 10 10")
    main_frame.pack(fill=tk.BOTH, expand=True)

    ai_friendly_var = tk.BooleanVar(value=False)

    def select_source_folder():
        folder = filedialog.askdirectory()
        if folder:
            source_folder_var.set(folder)

    def select_output_file():
        file_types = [("Текстовые файлы", "*.txt"), ("JSON файлы", "*.json")]
        file = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=file_types)
        if file:
            output_file_var.set(file)
            # Обновляем формат вывода на основе расширения файла
            if file.endswith(".json"):
                output_format_var.set("json")
            else:
                output_format_var.set("txt")

    def start_processing():
        source_folder = source_folder_var.get()
        output_file = output_file_var.get()

        if not source_folder or not output_file:
            messagebox.showwarning("Ошибка", "Выберите папку и файл для сохранения!")
            return

        try:
            exclude_extensions = set(ext.strip() for ext in exclude_extensions_var.get().split(",") if ext.strip())
            exclude_folders = set(folder.strip() for folder in exclude_folders_var.get().split(",") if folder.strip())
            # Add parse for exclude_files
            exclude_files = set(file.strip() for file in exclude_files_var.get().split(",") if file.strip())
            max_file_size = max_file_size_var.get()
            output_format = output_format_var.get()
            group_by_type = group_by_type_var.get()
            prioritize_files = prioritize_files_var.get()
            include_metadata = include_metadata_var.get()
            ai_friendly = ai_friendly_var.get()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Неверный формат параметров: {e}")
            return

        progress_bar["value"] = 0
        status_label.config(text="⏳ Обработка...")

        # Сохраняем настройки в файле конфигурации для следующего запуска
        save_settings()

        # Выбираем нужную функцию обработки
        if ai_friendly:
            thread = threading.Thread(target=create_ai_friendly_summary, args=(
                source_folder, output_file, exclude_extensions, exclude_folders, exclude_files,
                progress_bar, status_label))
        else:
            thread = threading.Thread(target=process_directory, args=(
                source_folder, output_file, exclude_extensions, exclude_folders, exclude_files,
                max_file_size, output_format, group_by_type, prioritize_files,
                include_metadata, progress_bar, status_label))

        thread.daemon = True  # Поток завершится при закрытии программы
        thread.start()

    # Функция для сохранения настроек
    def save_settings():
        try:
            with open("file_scanner_config.txt", "w", encoding="utf-8") as f:
                f.write(f"source_folder={source_folder_var.get()}\n")
                f.write(f"output_file={output_file_var.get()}\n")
                f.write(f"exclude_extensions={exclude_extensions_var.get()}\n")
                f.write(f"exclude_folders={exclude_folders_var.get()}\n")
                f.write(f"exclude_files={exclude_files_var.get()}\n")  # Add exclude_files
                f.write(f"max_file_size={max_file_size_var.get()}\n")
                f.write(f"output_format={output_format_var.get()}\n")
                f.write(f"group_by_type={group_by_type_var.get()}\n")
                f.write(f"prioritize_files={prioritize_files_var.get()}\n")
                f.write(f"include_metadata={include_metadata_var.get()}\n")
                f.write(f"ai_friendly={ai_friendly_var.get()}\n")
        except Exception:
            pass


            # Функция для загрузки настроек

    def load_settings():
        try:
            if os.path.exists("file_scanner_config.txt"):
                settings = {}
                with open("file_scanner_config.txt", "r", encoding="utf-8") as f:
                    for line in f.readlines():
                        if "=" in line:
                            key, value = line.strip().split("=", 1)
                            settings[key] = value

                if "source_folder" in settings:
                    source_folder_var.set(settings["source_folder"])
                if "output_file" in settings:
                    output_file_var.set(settings["output_file"])
                if "exclude_extensions" in settings:
                    exclude_extensions_var.set(settings["exclude_extensions"])
                if "exclude_folders" in settings:
                    exclude_folders_var.set(settings["exclude_folders"])
                if "max_file_size" in settings and settings["max_file_size"].isdigit():
                    max_file_size_var.set(int(settings["max_file_size"]))
                if "output_format" in settings:
                    output_format_var.set(settings["output_format"])
                if "group_by_type" in settings:
                    group_by_type_var.set(settings["group_by_type"] == "True")
                if "prioritize_files" in settings:
                    prioritize_files_var.set(settings["prioritize_files"])
                if "include_metadata" in settings:
                    include_metadata_var.set(settings["include_metadata"] == "True")
                if "exclude_files" in settings:
                    exclude_files_var.set(settings["exclude_files"])
        except Exception:
            pass  # Игнорируем ошибки при загрузке настроек

    source_folder_var = tk.StringVar()
    output_file_var = tk.StringVar()
    exclude_extensions_var = tk.StringVar(value=".exe, .dll, .zip, .mp4, .jpg, .jpeg, .png, .gif, .bin")
    exclude_folders_var = tk.StringVar(value="node_modules, __pycache__, .git, venv, .vscode, build, dist")
    exclude_files_var = tk.StringVar(value="")  # Add new variable for excluding specific files
    max_file_size_var = tk.IntVar(value=50000)  # По умолчанию ограничение 50KB
    output_format_var = tk.StringVar(value="txt")
    group_by_type_var = tk.BooleanVar(value=False)
    prioritize_files_var = tk.StringVar(value="settings.py, urls.py, models.py, views.py")
    include_metadata_var = tk.BooleanVar(value=True)

    # Создаем вкладки для лучшей организации опций
    notebook = ttk.Notebook(main_frame)
    notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Вкладка основных настроек
    basic_frame = ttk.Frame(notebook)
    notebook.add(basic_frame, text="Основные")

    # Поле выбора папки
    source_frame = ttk.Frame(basic_frame)
    source_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Label(source_frame, text="Папка с файлами:").pack(side=tk.LEFT)
    source_entry = ttk.Entry(source_frame, textvariable=source_folder_var)
    source_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    ttk.Button(source_frame, text="Обзор...", command=select_source_folder).pack(side=tk.RIGHT)
    create_context_menu(source_entry)
    enable_copy_paste(source_entry)

    # Поле выбора файла
    output_frame = ttk.Frame(basic_frame)
    output_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Label(output_frame, text="Файл для сохранения:").pack(side=tk.LEFT)
    output_entry = ttk.Entry(output_frame, textvariable=output_file_var)
    output_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    ttk.Button(output_frame, text="Обзор...", command=select_output_file).pack(side=tk.RIGHT)
    create_context_menu(output_entry)
    enable_copy_paste(output_entry)

    # Выбор формата вывода
    format_frame = ttk.Frame(basic_frame)
    format_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Label(format_frame, text="Формат вывода:").pack(side=tk.LEFT)
    ttk.Radiobutton(format_frame, text="Текст", variable=output_format_var, value="txt").pack(side=tk.LEFT, padx=5)
    ttk.Radiobutton(format_frame, text="JSON", variable=output_format_var, value="json").pack(side=tk.LEFT, padx=5)

    # Группа исключений
    exclude_frame = ttk.LabelFrame(basic_frame, text="Исключения через запитую")
    exclude_frame.pack(fill=tk.X, padx=5, pady=5)

    ai_friendly_frame = ttk.Frame(basic_frame)
    ai_friendly_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Checkbutton(ai_friendly_frame, text="Создать краткое описание для ИИ", variable=ai_friendly_var).pack(
        anchor=tk.W)

    # Поле исключаемых расширений
    ext_frame = ttk.Frame(exclude_frame)
    ext_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Label(ext_frame, text="Расширения файлов:").pack(side=tk.LEFT)
    exclude_ext_entry = ttk.Entry(ext_frame, textvariable=exclude_extensions_var)
    exclude_ext_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    create_context_menu(exclude_ext_entry)
    enable_copy_paste(exclude_ext_entry)

    # Поле исключаемых папок
    folders_frame = ttk.Frame(exclude_frame)
    folders_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Label(folders_frame, text="Названия папок:").pack(side=tk.LEFT)
    exclude_folders_entry = ttk.Entry(folders_frame, textvariable=exclude_folders_var)
    exclude_folders_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    create_context_menu(exclude_folders_entry)
    enable_copy_paste(exclude_folders_entry)

    # Вкладка дополнительных настроек
    advanced_frame = ttk.Frame(notebook)
    notebook.add(advanced_frame, text="Дополнительно")

    # Максимальный размер файла
    size_frame = ttk.Frame(advanced_frame)
    size_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Label(size_frame, text="Максимальный размер файла (байт):").pack(side=tk.LEFT)
    size_entry = ttk.Entry(size_frame, textvariable=max_file_size_var, width=10)
    size_entry.pack(side=tk.LEFT, padx=5)
    ttk.Label(size_frame, text="(0 = без ограничений)").pack(side=tk.LEFT)

    # Опции группировки
    group_frame = ttk.Frame(advanced_frame)
    group_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Checkbutton(group_frame, text="Группировать файлы по типу", variable=group_by_type_var).pack(anchor=tk.W)
    ttk.Checkbutton(group_frame, text="Включать метаданные файлов", variable=include_metadata_var).pack(anchor=tk.W)

    # Приоритетные файлы
    priority_frame = ttk.Frame(advanced_frame)
    priority_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Label(priority_frame, text="Приоритетные файлы:").pack(anchor=tk.W)
    priority_entry = ttk.Entry(priority_frame, textvariable=prioritize_files_var)
    priority_entry.pack(fill=tk.X, padx=5, pady=2)
    ttk.Label(priority_frame, text="(через запятую, эти файлы будут обработаны первыми)").pack(anchor=tk.W, padx=5)
    create_context_menu(priority_entry)
    enable_copy_paste(priority_entry)

    files_exclude_frame = ttk.Frame(exclude_frame)
    files_exclude_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Label(files_exclude_frame, text="Исключить файлы:").pack(side=tk.LEFT)
    exclude_files_entry = ttk.Entry(files_exclude_frame, textvariable=exclude_files_var)
    exclude_files_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    create_context_menu(exclude_files_entry)
    enable_copy_paste(exclude_files_entry)

    # Группа справки
    help_frame = ttk.LabelFrame(advanced_frame, text="Справка")
    help_frame.pack(fill=tk.X, padx=5, pady=5)
    help_text = tk.Text(help_frame, height=8, wrap=tk.WORD)
    help_text.pack(fill=tk.X, padx=5, pady=5)
    help_text.insert(tk.END,
                     "Эта программа помогает подготовить файлы для AI-моделей:\n\n"
                     "1. Выберите папку проекта для сканирования\n"
                     "2. Укажите файл для сохранения результатов\n"
                     "3. Настройте параметры сканирования\n"
                     "4. Нажмите 'Запустить' для начала сканирования\n\n"
                     "Для Django-проектов рекомендуется указать в приоритетных файлах: settings.py, urls.py, models.py, views.py\n"
                     "Группировка по типу поможет AI-модели лучше понять структуру вашего проекта."
                     )
    help_text.config(state=tk.DISABLED)

    # Группа статуса и прогресса
    status_frame = ttk.LabelFrame(main_frame, text="Статус")
    status_frame.pack(fill=tk.X, padx=5, pady=5)

    status_label = ttk.Label(status_frame, text="Готов к работе", font=("Arial", 10, "bold"))
    status_label.pack(pady=5)

    progress_bar = ttk.Progressbar(status_frame, orient="horizontal", length=300, mode="determinate")
    progress_bar.pack(fill=tk.X, padx=5, pady=5)

    # Кнопки действий
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill=tk.X, padx=5, pady=10)

    # Обычные кнопки tk вместо ttk для возможности полной окраски
    start_button = tk.Button(button_frame, text="Запустить", command=start_processing,
                             bg="green", fg="white", font=("Arial", 10, "bold"))
    start_button.pack(side=tk.LEFT, padx=5, pady=5)

    open_result_button = tk.Button(button_frame, text="Открыть результат",
                                   command=lambda: open_file(output_file_var.get()),
                                   bg="blue", fg="white", font=("Arial", 10, "bold"))
    open_result_button.pack(side=tk.LEFT, padx=5, pady=5)

    ttk.Button(button_frame, text="Выход", command=root.destroy).pack(side=tk.RIGHT, padx=5)

    # Загружаем сохраненные настройки
    load_settings()

    # Сохраняем настройки при закрытии
    root.protocol("WM_DELETE_WINDOW", lambda: (save_settings(), root.destroy()))

    # Функция для центрирования окна после полной загрузки интерфейса
    def center_window(event=None):
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

    # Вызываем центрирование после полной загрузки интерфейса
    root.bind("<Map>", center_window)

    # Также попробуем центрировать через 100 мс после запуска
    root.after(100, center_window)

    root.mainloop()

if __name__ == "__main__":
    start_gui()