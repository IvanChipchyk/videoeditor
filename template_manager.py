#!/usr/bin/env python3
"""
template_manager.py - Модуль для управления шаблонами VideoCreator
ЭТАП 4: Логирование процесса
"""

import json
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Any

# Импортируем настроенный логгер
from logger_setup import logger

TEMPLATES_DIR_NAME = "saved_templates"
TEMPLATE_FILE_EXTENSION = ".json"

try:
    BASE_DIR = Path(__file__).resolve().parent
except NameError:
    BASE_DIR = Path.cwd() 

TEMPLATES_DIR = BASE_DIR / TEMPLATES_DIR_NAME

def ensure_templates_dir_exists() -> None:
    """
    Гарантирует существование директории для сохранения шаблонов.
    Создает директорию, если она отсутствует.
    """
    # Эта функция вызывается в __init__ VideoCreatorApp и при импорте template_manager,
    # поэтому логирование здесь может быть избыточным, если логгер еще не настроен.
    # Однако, если вызывать ее отдельно, логирование полезно.
    # logger.debug(f"Проверка/создание директории шаблонов: {TEMPLATES_DIR}")
    try:
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        # logger.info(f"Директория шаблонов {TEMPLATES_DIR} проверена/создана.")
    except Exception as e:
        # Используем print, так как логгер может быть еще не полностью настроен при первом вызове
        print(f"Критическая ошибка: Не удалось создать директорию для шаблонов {TEMPLATES_DIR}: {e}")
        # logger.critical(f"Не удалось создать директорию для шаблонов {TEMPLATES_DIR}: {e}", exc_info=True)


def sanitize_filename(name: str) -> str:
    """
    Очищает строку для использования в качестве имени файла.
    """
    # logger.debug(f"Санитизация имени файла для: '{name}'")
    if not name or not isinstance(name, str) or not name.strip():
        # logger.warning("Попытка санитизировать пустое или некорректное имя. Возвращено 'untitled'.")
        return "untitled"
    
    original_name = name
    name = name.strip().lower()
    name = re.sub(r'\s+', '_', name)
    name = re.sub(r'[^\w\._-]', '', name)
    name = re.sub(r'_+', '_', name)
    name = name.strip('._-')

    if not name:
        # logger.warning(f"Имя '{original_name}' стало пустым после санитизации. Возвращено 'untitled'.")
        return "untitled"
    # logger.debug(f"Санитизированное имя: '{name}' (из '{original_name}')")
    return name

def save_template(settings: Dict[str, Any], template_display_name: str) -> bool:
    """
    Сохраняет переданные настройки как JSON-шаблон.
    """
    logger.info(f"Попытка сохранения шаблона с отображаемым именем: '{template_display_name}'")
    ensure_templates_dir_exists() # Убедимся, что директория есть
    
    if not template_display_name or not template_display_name.strip():
        logger.error("Ошибка сохранения шаблона: Отображаемое имя шаблона не может быть пустым.")
        return False

    clean_display_name = template_display_name.strip()
    logger.debug(f"Очищенное отображаемое имя: '{clean_display_name}'")
    
    template_data = settings.copy()
    template_data["name"] = clean_display_name

    filename_base = sanitize_filename(clean_display_name)
    filepath = TEMPLATES_DIR / f"{filename_base}{TEMPLATE_FILE_EXTENSION}"
    logger.debug(f"Полный путь для сохранения шаблона: {filepath}")

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, ensure_ascii=False, indent=4)
        logger.info(f"Шаблон '{clean_display_name}' (файл: {filepath.name}) успешно сохранен.")
        return True
    except IOError as e:
        logger.error(f"IOError при сохранении шаблона '{clean_display_name}' в {filepath}: {e}", exc_info=True)
    except TypeError as e:
        logger.error(f"TypeError (ошибка сериализации) при сохранении шаблона '{clean_display_name}': {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при сохранении шаблона '{clean_display_name}': {e}", exc_info=True)
    return False

def load_template(template_filename_stem: str) -> Optional[Dict[str, Any]]:
    """
    Загружает шаблон из JSON-файла.
    """
    logger.info(f"Попытка загрузки шаблона с именем файла (без расширения): '{template_filename_stem}'")
    # ensure_templates_dir_exists() # Обычно директория уже должна существовать
    
    filepath = TEMPLATES_DIR / f"{template_filename_stem}{TEMPLATE_FILE_EXTENSION}"
    logger.debug(f"Полный путь для загрузки шаблона: {filepath}")

    if not filepath.is_file():
        logger.error(f"Ошибка загрузки: Файл шаблона {filepath} не найден или не является файлом.")
        return None

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, dict) or "name" not in data:
            logger.error(f"Ошибка: Файл {filepath} не является корректным шаблоном (отсутствует поле 'name' или не является словарем).")
            return None
            
        logger.info(f"Шаблон '{data.get('name', template_filename_stem)}' успешно загружен из {filepath.name}.")
        return data
    except IOError as e:
        logger.error(f"IOError при загрузке шаблона из {filepath}: {e}", exc_info=True)
    except json.JSONDecodeError as e:
        logger.error(f"JSONDecodeError (ошибка декодирования JSON) из файла шаблона {filepath}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при загрузке шаблона {filepath}: {e}", exc_info=True)
    return None

def get_saved_templates() -> List[Dict[str, str]]:
    """
    Сканирует директорию шаблонов и возвращает список деталей шаблонов.
    """
    logger.info("Получение списка сохраненных шаблонов...")
    ensure_templates_dir_exists() # Убедимся, что директория есть
    templates_info = []
    
    file_count = 0
    processed_count = 0
    for filepath in TEMPLATES_DIR.glob(f"*{TEMPLATE_FILE_EXTENSION}"):
        file_count += 1
        if filepath.is_file():
            logger.debug(f"Обработка файла шаблона: {filepath.name}")
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                display_name = data.get("name", filepath.stem) 
                templates_info.append({"filename_stem": filepath.stem, "display_name": display_name})
                processed_count +=1
            except (IOError, json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Не удалось прочитать или распарсить файл шаблона {filepath.name}: {e}. Пропускаем.", exc_info=True)
                templates_info.append({"filename_stem": filepath.stem, "display_name": f"{filepath.stem} (ошибка чтения имени)"})
    
    logger.info(f"Найдено {file_count} файлов с расширением '{TEMPLATE_FILE_EXTENSION}'. Обработано как шаблоны: {processed_count}.")
    templates_info.sort(key=lambda x: x["display_name"].lower())
    logger.debug(f"Список шаблонов для возврата (отсортированный): {templates_info}")
    return templates_info

def delete_template(template_filename_stem: str) -> bool:
    """
    Удаляет файл шаблона.
    """
    logger.info(f"Попытка удаления шаблона с именем файла (без расширения): '{template_filename_stem}'")
    ensure_templates_dir_exists()
    filepath = TEMPLATES_DIR / f"{template_filename_stem}{TEMPLATE_FILE_EXTENSION}"
    logger.debug(f"Полный путь для удаления шаблона: {filepath}")

    if not filepath.is_file():
        logger.error(f"Ошибка удаления: Файл шаблона {filepath} не найден или не является файлом.")
        return False
    
    try:
        display_name_for_log = filepath.stem # Для лога, если не сможем прочитать JSON
        try: # Попытка прочитать имя из файла для более информативного лога
            with open(filepath, 'r', encoding='utf-8') as f_read:
                data_for_log = json.load(f_read)
                display_name_for_log = data_for_log.get("name", filepath.stem)
        except:
            pass # Если не удалось прочитать, используем имя файла

        filepath.unlink()
        logger.info(f"Шаблон '{display_name_for_log}' (файл: {filepath.name}) успешно удален.")
        return True
    except OSError as e:
        logger.error(f"OSError при удалении файла шаблона {filepath}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при удалении шаблона {filepath}: {e}", exc_info=True)
    return False

if __name__ == '__main__':
    # При запуске напрямую, логгер уже настроен при импорте
    logger.info("Запуск тестирования модуля template_manager.py...")
    
    logger.info(f"Директория шаблонов (из `if __name__`): {TEMPLATES_DIR.resolve()}")
    # ensure_templates_dir_exists() # Уже вызван при настройке логгера, если он там есть

    example_settings_data = {
        "resolution": [1920, 1080], "duration": 30, "title_text": "Тестовый Заголовок",
        "subtitle_text": "Это субтитры для теста шаблона.", "text_color": "#123456",
        "stroke_color": "#ABCDEF", "stroke_width": 1, "title_size": 50, "subtitle_size": 28,
        "effects": {"typewriter": False, "fade": True}, "font_path": "C:/Windows/Fonts/verdana.ttf",
        "image_paths": ["./img/test1.jpg", "./img/test2.png"], "audio_tracks_info": ["./audio/background.mp3"],
        "fps": 30, "video_quality": "medium" # Добавим новые поля для полноты
    }

    logger.info("--- Тест сохранения (из `if __name__`) ---")
    save_template(example_settings_data, " Мой Тестовый Шаблон ")
    save_template(example_settings_data, "Еще один шаблон *?")
    
    logger.info("--- Тест списка шаблонов (из `if __name__`) ---")
    available_templates = get_saved_templates()
    if available_templates:
        for t in available_templates:
            logger.debug(f"  Найден шаблон: Отображаемое имя: '{t['display_name']}', Имя файла (без .json): '{t['filename_stem']}'")
    else:
        logger.info("  Нет сохраненных шаблонов для теста.")

    if available_templates:
        stem_to_load = available_templates[0]["filename_stem"]
        logger.info(f"--- Тест загрузки шаблона ('{stem_to_load}') (из `if __name__`) ---")
        loaded_content = load_template(stem_to_load)
        if loaded_content:
            logger.debug(f"Содержимое загруженного шаблона ('{stem_to_load}'): {json.dumps(loaded_content, indent=2, ensure_ascii=False)}")
    
    logger.info("--- Тестирование модуля template_manager.py завершено (из `if __name__`) ---")