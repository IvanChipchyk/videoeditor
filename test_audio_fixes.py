#!/usr/bin/env python3
"""
test_audio_fixes.py - Исправленный тест аудио проблем
"""

import sys
from pathlib import Path
import tempfile
import os

def main():
    print(f"🔧 Тестирование исправлений аудио VideoCreator Pro")
    print("=" * 60)

    print("🎵 Тестирование создания видео с аудио...")

    try:
        # Добавляем текущую папку в путь
        current_dir = Path(__file__).parent.resolve()
        if str(current_dir) not in sys.path:
            sys.path.append(str(current_dir))
        
        from text_effects_engine import create_enhanced_video
        print("✅ Модули импортированы успешно")
        
        # Проверяем наличие тестовых файлов
        test_audio_files = []
        audio_folder = Path("output")
        if audio_folder.exists():
            for audio_file in audio_folder.glob("*.mp3"):
                test_audio_files.append(str(audio_file))
                print(f"🎧 Найден аудиофайл: {audio_file.name}")
                break  # Берем первый найденный
        
        if not test_audio_files:
            print("⚠️ Аудиофайлы не найдены в папке output/")
            print("💡 Создайте аудиофайлы с помощью script.py или добавьте любой .mp3 файл в папку output/")
            
            # Попробуем найти любой аудиофайл в системе
            downloads_folder = Path.home() / "Downloads"
            for audio_ext in ["*.mp3", "*.wav", "*.m4a"]:
                for audio_file in downloads_folder.glob(audio_ext):
                    test_audio_files = [str(audio_file)]
                    print(f"🎧 Используем тестовый аудиофайл: {audio_file.name}")
                    break
                if test_audio_files:
                    break
        
        if not test_audio_files:
            print("❌ Аудиофайлы не найдены. Попробуйте:")
            print("   1. Запустить script.py для создания аудиофайлов")
            print("   2. Скопировать любой .mp3 файл в папку output/")
            print("   3. Протестировать основное приложение: python3 videocreator_main.py")
            return
        
        # Создаем простое тестовое изображение
        test_image_path = None
        downloads_folder = Path.home() / "Downloads"
        for img_ext in ["*.png", "*.jpg", "*.jpeg"]:
            for img_file in downloads_folder.glob(img_ext):
                test_image_path = str(img_file)
                print(f"🖼️ Используем тестовое изображение: {img_file.name}")
                break
            if test_image_path:
                break
        
        if not test_image_path:
            print("⚠️ Изображения не найдены в Downloads/")
            print("💡 Создаем простой фон...")
            try:
                from PIL import Image
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_img:
                    img = Image.new('RGB', (1920, 1080), color='blue')
                    img.save(temp_img.name)
                    test_image_path = temp_img.name
                    print(f"✅ Создано тестовое изображение: {temp_img.name}")
            except ImportError:
                print("❌ PIL недоступен для создания тестового изображения")
                print("💡 Добавьте любое изображение в Downloads/ или протестируйте основное приложение")
                return
        
        # Получаем длительность аудио
        try:
            from moviepy import AudioFileClip
            with AudioFileClip(test_audio_files[0]) as audio_clip:
                audio_duration = min(audio_clip.duration, 10)  # Максимум 10 секунд для теста
            print(f"🎵 Длительность аудио: {audio_duration:.2f} секунд")
        except Exception as e:
            print(f"⚠️ Ошибка определения длительности аудио: {e}")
            audio_duration = 5  # Fallback значение
        
        # Параметры для тестового видео
        test_params = {
            'image_paths': [test_image_path],
            'audio_tracks_info': [
                {
                    'path': test_audio_files[0],
                    'start_time': 0.0,
                    'duration': audio_duration
                }
            ],
            'output_path': 'test_video_with_audio.mp4',
            'resolution': (1920, 1080),
            'duration': int(audio_duration),
            'title_text': 'Тест',
            'subtitle_text': 'Проверка аудио',
            'text_color': '#ffffff',
            'stroke_color': '#000000',
            'stroke_width': 2,
            'title_size': 40,
            'subtitle_size': 24,
            'effects': {'typewriter': False, 'fade': False},
            'font_path': None,
            'fps': 30,
            'video_quality': 'medium',
            'codec_name': 'libx264'
        }
        
        print("\n🚀 Создание тестового видео с аудио...")
        print(f"   📁 Изображение: {Path(test_image_path).name}")
        print(f"   🎵 Аудио: {Path(test_audio_files[0]).name}")
        print(f"   📺 Выходной файл: {test_params['output_path']}")
        print(f"   ⏱️ Длительность: {test_params['duration']} сек")
        
        # Создаем видео
        result_path = create_enhanced_video(**test_params)
        
        if Path(result_path).exists():
            file_size = Path(result_path).stat().st_size
            print(f"\n✅ УСПЕХ! Видео создано: {result_path}")
            print(f"   📊 Размер файла: {file_size / 1024 / 1024:.2f} МБ")
            
            # Проверяем что видео содержит аудио
            try:
                from moviepy import VideoFileClip
                with VideoFileClip(result_path) as test_clip:
                    if test_clip.audio is not None:
                        print(f"   🎵 Аудио присутствует: длительность {test_clip.audio.duration:.2f} сек")
                        print(f"   ✅ ПРОБЛЕМА С АУДИО ИСПРАВЛЕНА!")
                    else:
                        print("   ⚠️ Аудио отсутствует в финальном видео")
                    print(f"   📺 Видео: {test_clip.duration:.2f} сек, {test_clip.size}")
            except Exception as e:
                print(f"   ⚠️ Ошибка проверки видео: {e}")
            
        else:
            print(f"❌ Видео не создано: {result_path}")
        
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("🏁 Тест завершен")
    print("\n💡 Если видео создалось с аудио - основная проблема исправлена!")
    print("   Теперь можно запускать: python3 videocreator_main.py")

if __name__ == "__main__":
    main()