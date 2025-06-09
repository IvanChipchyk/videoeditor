#!/usr/bin/env python3
"""
test_fixes.py - Быстрый тест исправлений без запуска полного приложения
"""

import sys
from pathlib import Path
import platform

print(f"🔧 Тестирование исправлений VideoCreator Pro")
print(f"💻 Система: {platform.system()} {platform.release()}")
print(f"🐍 Python: {sys.version}")
print("=" * 50)

# Тест 1: Проверка импорта модулей
print("1️⃣ Проверка импорта модулей...")
try:
    from moviepy import TextClip, AudioFileClip
    print("✅ MoviePy импортирован")
except ImportError as e:
    print(f"❌ Ошибка MoviePy: {e}")
    sys.exit(1)

try:
    import gspread
    from google.oauth2.service_account import Credentials
    print("✅ Google Sheets API импортирован")
except ImportError as e:
    print(f"⚠️ Google Sheets API недоступен: {e}")

# Тест 2: Проверка шрифта
print("\n2️⃣ Тестирование шрифтов...")
try:
    # Импортируем нашу функцию определения шрифта
    sys.path.append('.')
    
    # Если файл text_effects_engine.py еще не обновлен, используем inline функцию
    def test_cyrillic_font():
        test_fonts = [None, "Arial", "Helvetica", "Times"]
        
        for font in test_fonts:
            try:
                if font:
                    clip = TextClip(text="Тест 🐏", font=font, font_size=24, color='white')
                else:
                    clip = TextClip(text="Тест 🐏", font_size=24, color='white')
                clip.close()
                font_name = font if font else "Системный по умолчанию"
                print(f"✅ Шрифт работает: {font_name}")
                return font_name
            except Exception as e:
                font_name = font if font else "Системный по умолчанию"
                print(f"❌ Шрифт не работает: {font_name} - {str(e)[:50]}...")
        
        return None
    
    working_font = test_cyrillic_font()
    if working_font:
        print(f"✅ Найден рабочий шрифт: {working_font}")
    else:
        print("❌ Не найден рабочий шрифт!")
        
except Exception as e:
    print(f"❌ Ошибка тестирования шрифтов: {e}")

# Тест 3: Проверка файлов проекта
print("\n3️⃣ Проверка файлов проекта...")

required_files = [
    "videocreator_main.py",
    "text_effects_engine.py", 
    "media_engine.py",
    "logger_setup.py",
    "template_manager.py"
]

for file in required_files:
    if Path(file).exists():
        print(f"✅ {file}")
    else:
        print(f"❌ {file} - отсутствует")

# Проверка Google Sheets файлов
sheets_files = [
    "elevenlabs-voice-generator-9cd6aae15cf6.json",
    "google_sheets_manager.py"
]

for file in sheets_files:
    if Path(file).exists():
        print(f"✅ {file}")
    else:
        print(f"⚠️ {file} - отсутствует (опционально)")

# Проверка папок
print("\n📁 Проверка папок...")
folders = ["output", "saved_templates", "logs"]
for folder in folders:
    folder_path = Path(folder)
    if folder_path.exists():
        files_count = len(list(folder_path.iterdir()))
        print(f"✅ {folder}/ ({files_count} файлов)")
    else:
        print(f"ℹ️ {folder}/ - будет создана автоматически")

# Тест 4: Проверка Google Sheets подключения (если файл есть)
print("\n4️⃣ Тестирование Google Sheets...")
service_account_file = "elevenlabs-voice-generator-9cd6aae15cf6.json"
if Path(service_account_file).exists():
    try:
        # Простая проверка валидности JSON
        import json
        with open(service_account_file, 'r') as f:
            data = json.load(f)
        
        required_keys = ["type", "project_id", "private_key", "client_email"]
        missing_keys = [key for key in required_keys if key not in data]
        
        if not missing_keys:
            print("✅ Файл сервисного аккаунта валиден")
            
            # Пробуем подключиться (если модуль доступен)
            if 'gspread' in sys.modules:
                try:
                    from google_sheets_manager import test_google_sheets_connection
                    SPREADSHEET_ID = "1FQV-3SZGYoR1z3ZY9zwmycQmoWbQ230MeKueWDjWroI"
                    test_result = test_google_sheets_connection(service_account_file, SPREADSHEET_ID)
                    
                    if test_result['connected']:
                        print(f"✅ Google Sheets подключение работает")
                        print(f"   📊 Таблица: {test_result['spreadsheet_title']}")
                        print(f"   📄 Лист: {test_result['sheet_title']}")
                        print(f"   🔢 Тем найдено: {test_result['themes_count']}")
                    else:
                        print(f"❌ Google Sheets подключение не работает: {test_result['error']}")
                        
                except Exception as e:
                    print(f"⚠️ Не удалось протестировать Google Sheets: {e}")
            else:
                print("ℹ️ gspread не доступен для тестирования подключения")
        else:
            print(f"❌ Файл сервисного аккаунта неполный, отсутствуют: {missing_keys}")
            
    except Exception as e:
        print(f"❌ Ошибка чтения файла сервисного аккаунта: {e}")
else:
    print("ℹ️ Файл сервисного аккаунта отсутствует (Google Sheets функции недоступны)")

# Тест 5: Проверка создания простого видео
print("\n5️⃣ Тестирование создания тестового клипа...")
try:
    # Создаем простой тестовый клип
    from moviepy import ColorClip, CompositeVideoClip
    
    # Тестовый фон
    test_clip = ColorClip(size=(1920, 1080), color=(50, 50, 50), duration=1)
    
    # Тестовый текст
    try:
        text_clip = TextClip(text="Тест ✓", font_size=40, color='white').with_duration(1).with_position('center')
        # ИСПРАВЛЕНО: Используем CompositeVideoClip вместо with_overlay
        final_clip = CompositeVideoClip([test_clip, text_clip], size=(1920, 1080))
        print("✅ Тестовый видеоклип с текстом создан успешно")
        
        # Освобождаем ресурсы
        final_clip.close()
        text_clip.close()
        test_clip.close()
        
    except Exception as e:
        print(f"⚠️ Текстовый клип не создан: {e}")
        print("✅ Базовый видеоклип создан успешно")
        test_clip.close()
        
except Exception as e:
    print(f"❌ Ошибка создания тестового клипа: {e}")

# Итоговый результат
print("\n" + "=" * 50)
print("🏁 РЕЗУЛЬТАТ ТЕСТИРОВАНИЯ:")
print("✅ = Готово к работе")
print("⚠️ = Частично работает") 
print("❌ = Требует исправления")
print("ℹ️ = Дополнительная информация")

print("\n💡 РЕКОМЕНДАЦИИ:")
print("1. Если есть ❌ с шрифтами - замените text_effects_engine.py")
print("2. Если есть ❌ с Google Sheets - проверьте файл сервисного аккаунта")
print("3. Для полного тестирования запустите: python3 videocreator_main.py")

print("\n🚀 Готово к тестированию!")