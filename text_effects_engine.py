#!/usr/bin/env python3
"""
text_effects_engine.py - Модуль визуальных эффектов для текста VideoCreator
ЭТАП 4: Исправление проблем с TextClip и AudioClip
ИСПРАВЛЕНО: Добавлена логика выбора шрифтов для macOS и включено аудио обратно
"""

import os
import sys
import platform
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from moviepy import (
    TextClip, CompositeVideoClip, ColorClip,
    concatenate_videoclips, AudioFileClip, ImageClip, CompositeAudioClip
)

from media_engine import (
    create_image_clips, create_slideshow, create_audio_track
)
from logger_setup import logger

def get_system_font_for_cyrillic():
    """
    Определяет доступный системный шрифт для поддержки кириллицы
    """
    system = platform.system()
    
    if system == "Darwin":  # macOS
        # Проверяем доступные шрифты на macOS
        possible_fonts = [
            "Arial",           # Основной Arial
            "Helvetica",       # Helvetica
            "San Francisco",   # Системный шрифт macOS
            "Lucida Grande",   # Старый системный шрифт
            "DejaVu Sans",     # Если установлен
            "Times New Roman", # Times
        ]
    elif system == "Windows":
        possible_fonts = [
            "Arial",
            "Arial Unicode MS",
            "Segoe UI",
            "Tahoma",
            "Verdana",
        ]
    else:  # Linux
        possible_fonts = [
            "DejaVu Sans",
            "Liberation Sans", 
            "Ubuntu",
            "Arial",
        ]
    
    # Тестируем каждый шрифт
    for font in possible_fonts:
        try:
            # Пробуем создать тестовый TextClip с кириллицей
            test_clip = TextClip(text="Тест", font=font, font_size=12, color='white')
            test_clip.close()  # Сразу закрываем тестовый клип
            logger.info(f"Найден рабочий шрифт для кириллицы: {font}")
            return font
        except Exception as e:
            logger.debug(f"Шрифт {font} недоступен: {e}")
            continue
    
    # Если ничего не найдено, возвращаем None (будет использован системный по умолчанию)
    logger.warning("Не найден подходящий шрифт для кириллицы, используется системный по умолчанию")
    return None

class TextEffectsEngine:
    def __init__(self):
        logger.debug("Инициализация TextEffectsEngine...")
        # Определяем системный шрифт при инициализации
        self.system_font = get_system_font_for_cyrillic()
        logger.debug("TextEffectsEngine инициализирован.")

    def create_enhanced_title_clip(
        self, text: str, resolution: Tuple[int, int], duration: int,
        text_color: str = "#ffffff", stroke_color: str = "#000000", stroke_width: int = 2,
        title_size: int = 40, font_path: Optional[str] = None, effects: Optional[Dict[str, bool]] = None,
        video_fps: int = 30
    ) -> Optional[TextClip]:
        logger.info(f"Создание улучшенного клипа заголовка: '{text[:30]}...'")
        if not text.strip():
            logger.warning("Текст заголовка пуст, клип не будет создан.")
            return None
        effects = effects or {}
        
        # Определяем шрифт
        font_to_use = None
        if font_path and os.path.exists(font_path):
            font_to_use = font_path
            logger.info(f"Используется пользовательский шрифт: {font_path}")
        elif self.system_font:
            font_to_use = self.system_font
            logger.info(f"Используется системный шрифт: {self.system_font}")
        else:
            logger.info("Шрифт не указан, используется системный по умолчанию")
        
        try:
            # Используем правильные параметры для TextClip (MoviePy 2.0)
            clip_kwargs = {
                "font_size": title_size,
                "color": text_color,
                "stroke_color": stroke_color,
                "stroke_width": stroke_width,
                "size": (resolution[0] - 100, None),
                "method": 'caption'
            }
            
            # Добавляем шрифт только если он определен
            if font_to_use:
                clip_kwargs["font"] = font_to_use

            # Передаем текст как первый позиционный аргумент
            base_clip = TextClip(text=text, **clip_kwargs).with_position(('center', 50))
            if getattr(base_clip, 'fps', None) is None:
                base_clip.fps = video_fps
            
            # Применяем эффекты
            final_clip = None
            if effects.get('typewriter', False):
                final_clip = self._apply_typewriter_effect(base_clip, duration, fps=video_fps)
            elif effects.get('fade', False):
                final_clip = self._apply_fade_effect(base_clip, duration)
            else:
                final_clip = base_clip.with_duration(duration)
            
            if final_clip and getattr(final_clip, 'fps', None) is None:
                final_clip.fps = video_fps

            logger.info(f"Клип заголовка '{text[:30]}...' успешно создан.")
            return final_clip

        except Exception as e:
            logger.error(f"Ошибка создания заголовка: {e}", exc_info=True)
            try:
                # Простой fallback без кастомного шрифта
                fb_clip = TextClip(
                    text=text,
                    font_size=title_size,
                    color=text_color,
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                    size=(resolution[0] - 100, None),
                    method='caption'
                    # НЕ указываем font, пусть система сама выберет
                ).with_position(('center', 50)).with_duration(duration)
                fb_clip.fps = video_fps
                logger.info("Fallback клип заголовка создан без указания шрифта.")
                return fb_clip
            except Exception as fe:
                logger.error(f"Ошибка fallback заголовка: {fe}", exc_info=True)
                return None
                  
    def create_enhanced_subtitle_clip(
        self, text: str, resolution: Tuple[int, int], duration: int,
        text_color: str = "#ffffff", stroke_color: str = "#000000", stroke_width: int = 1,
        subtitle_size: int = 24, font_path: Optional[str] = None, effects: Optional[Dict[str, bool]] = None,
        video_fps: int = 30
    ) -> Optional[TextClip]:
        logger.info(f"Создание улучшенного клипа субтитров: '{text[:30]}...'")
        if not text.strip():
            logger.warning("Текст субтитров пуст, клип не будет создан.")
            return None
        effects = effects or {}
        
        # Определяем шрифт
        font_to_use = None
        if font_path and os.path.exists(font_path):
            font_to_use = font_path
            logger.info(f"Используется пользовательский шрифт: {font_path}")
        elif self.system_font:
            font_to_use = self.system_font
            logger.info(f"Используется системный шрифт: {self.system_font}")
        else:
            logger.info("Шрифт не указан, используется системный по умолчанию")

        try:
            # Используем правильные параметры для TextClip (MoviePy 2.0)
            clip_kwargs = {
                "font_size": subtitle_size,
                "color": text_color,
                "stroke_color": stroke_color,
                "stroke_width": stroke_width,
                "size": (resolution[0] - 100, None),
                "method": 'caption'
            }
            
            # Добавляем шрифт только если он определен
            if font_to_use:
                clip_kwargs["font"] = font_to_use

            # Передаем текст как первый позиционный аргумент
            base_clip = TextClip(text=text, **clip_kwargs).with_position(('center', resolution[1] - 200))
            
            if getattr(base_clip, 'fps', None) is None:
                base_clip.fps = video_fps
            
            # Применяем эффекты
            final_clip = None
            if effects.get('typewriter', False):
                final_clip = self._apply_typewriter_effect(base_clip, duration, fps=video_fps)
            elif effects.get('fade', False):
                final_clip = self._apply_fade_effect(base_clip, duration)
            else:
                final_clip = base_clip.with_duration(duration)
            
            if final_clip and getattr(final_clip, 'fps', None) is None:
                final_clip.fps = video_fps

            logger.info(f"Клип субтитров '{text[:30]}...' успешно создан.")
            return final_clip
        except Exception as e:
            logger.error(f"Ошибка создания субтитров: {e}", exc_info=True)
            try:
                # Простой fallback без кастомного шрифта
                fb_clip = TextClip(
                    text=text,
                    font_size=subtitle_size,
                    color=text_color,
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                    size=(resolution[0] - 100, None),
                    method='caption'
                    # НЕ указываем font, пусть система сама выберет
                ).with_position(('center', resolution[1] - 200)).with_duration(duration)
                fb_clip.fps = video_fps
                logger.info("Fallback клип субтитров создан без указания шрифта.")
                return fb_clip
            except Exception as fe:
                logger.error(f"Ошибка fallback субтитров: {fe}", exc_info=True)
                return None

    def _apply_typewriter_effect(self, text_clip: TextClip, duration: int, fps: int = 30) -> Optional[CompositeVideoClip]:
        text_value = getattr(text_clip, 'text', getattr(text_clip, 'txt', ''))
        logger.debug(
            f"Применение эффекта 'печатная машинка' к тексту '{str(text_value)[:50]}...' "
            f"длительностью {duration} сек, FPS={fps}."
        )
        original_text = str(text_value)
        if not original_text or duration <= 0:
            logger.warning("Для эффекта 'печатная машинка' текст пуст или длительность некорректна.")
            returned_clip = text_clip.with_duration(duration)
            if getattr(returned_clip, 'fps', None) is None:
                returned_clip.fps = fps
            return returned_clip
        
        # ИСПРАВЛЕНО: Убираем ограничение на количество символов
        # Оптимизируем для производительности другими способами
        
        # Умная оптимизация: для очень длинных текстов используем группировку слов
        if len(original_text) > 500:
            logger.info(f"Длинный текст ({len(original_text)} символов), используем группировку по словам")
            # Разбиваем по словам для более быстрой анимации
            words = original_text.split()
            # Группируем слова для оптимизации
            words_per_frame = max(1, len(words) // min(100, duration * fps // 10))
            
            animated_clips = []
            current_time = 0.0
            
            # Получаем атрибуты из исходного text_clip
            font_to_use_effect = getattr(text_clip, 'font', None)
            font_size_effect = getattr(text_clip, 'font_size', 24)
            color_effect = getattr(text_clip, 'color', 'white')
            stroke_color_effect = getattr(text_clip, 'stroke_color', 'black')
            stroke_width_effect = getattr(text_clip, 'stroke_width', 1)
            size_effect = getattr(text_clip, 'size', (None, None))
            method_effect = getattr(text_clip, 'method', 'caption')
            position_effect = text_clip.pos
            
            frame_duration = duration / len(words) * words_per_frame
            frame_duration = max(0.1, frame_duration)  # Минимум 0.1 сек на кадр
            
            for i in range(0, len(words), words_per_frame):
                if current_time >= duration - 0.1:
                    break
                    
                # Собираем группу слов
                word_group = words[i:i+words_per_frame]
                sub_text = ' '.join(words[:i+len(word_group)])
                
                try:
                    clip_kwargs_frag = {
                        "font_size": font_size_effect,
                        "color": color_effect,
                        "stroke_color": stroke_color_effect,
                        "stroke_width": stroke_width_effect,
                        "size": size_effect,
                        "method": method_effect
                    }
                    
                    if font_to_use_effect:
                        clip_kwargs_frag["font"] = font_to_use_effect
                    
                    clip = TextClip(text=sub_text, **clip_kwargs_frag).with_position(position_effect).with_duration(frame_duration)
                    clip.fps = fps
                    animated_clips.append(clip)
                    
                    current_time += frame_duration
                    
                    # Логируем прогресс для длинных текстов
                    if i % (words_per_frame * 5) == 0:
                        logger.debug(f"Typewriter прогресс: {i}/{len(words)} слов ({current_time:.1f}/{duration} сек)")
                        
                except Exception as e:
                    logger.error(f"Ошибка создания фрагмента typewriter на слове {i}: {e}")
                    returned_clip = text_clip.with_duration(duration)
                    if getattr(returned_clip, 'fps', None) is None:
                        returned_clip.fps = fps
                    return returned_clip
        
        else:
            # Для коротких и средних текстов используем посимвольную анимацию
            animated_clips = []
            char_time = max(0.03, duration / len(original_text)) if len(original_text) > 0 else duration
            
            # Получаем атрибуты из исходного text_clip
            font_to_use_effect = getattr(text_clip, 'font', None)
            font_size_effect = getattr(text_clip, 'font_size', 24)
            color_effect = getattr(text_clip, 'color', 'white')
            stroke_color_effect = getattr(text_clip, 'stroke_color', 'black')
            stroke_width_effect = getattr(text_clip, 'stroke_width', 1)
            size_effect = getattr(text_clip, 'size', (None, None))
            method_effect = getattr(text_clip, 'method', 'caption')
            position_effect = text_clip.pos

            current_time = 0.0
            
            # Оптимизация: показываем не каждый символ, а через определенный интервал
            step = max(1, len(original_text) // min(150, duration * 10))  # Адаптивный шаг
            
            for i in range(0, len(original_text), step):
                if current_time >= duration - 0.1:
                    break
                    
                sub_text = original_text[:i+step]
                
                frag_duration = char_time * step
                if i + step >= len(original_text):
                    frag_duration = max(0.03, duration - current_time)
                
                frag_duration = max(0.03, frag_duration)

                try:
                    clip_kwargs_frag = {
                        "font_size": font_size_effect,
                        "color": color_effect,
                        "stroke_color": stroke_color_effect,
                        "stroke_width": stroke_width_effect,
                        "size": size_effect,
                        "method": method_effect
                    }
                    
                    if font_to_use_effect:
                        clip_kwargs_frag["font"] = font_to_use_effect
                    
                    clip = TextClip(text=sub_text, **clip_kwargs_frag).with_position(position_effect).with_duration(frag_duration)
                    clip.fps = fps
                    animated_clips.append(clip)
                    
                    current_time += frag_duration
                    
                except Exception as e:
                    logger.error(f"Ошибка создания фрагмента typewriter на позиции {i}: {e}")
                    returned_clip = text_clip.with_duration(duration)
                    if getattr(returned_clip, 'fps', None) is None:
                        returned_clip.fps = fps
                    return returned_clip
        
        if not animated_clips:
            logger.warning("Не создано анимированных фрагментов для печатной машинки.")
            returned_clip = text_clip.with_duration(duration)
            if getattr(returned_clip, 'fps', None) is None:
                returned_clip.fps = fps
            return returned_clip
        
        try:
            logger.debug(f"Сборка typewriter из {len(animated_clips)} фрагментов...")
            final_typewriter_clip = concatenate_videoclips(animated_clips, method="compose")
            final_typewriter_clip = final_typewriter_clip.with_duration(duration)
            final_typewriter_clip.fps = fps
            final_typewriter_clip = final_typewriter_clip.with_position(position_effect)

            logger.info("Эффект 'печатная машинка' успешно собран.")
            return final_typewriter_clip
            
        except Exception as e:
            logger.error(f"Ошибка сборки эффекта 'печатная машинка': {e}", exc_info=True)
            returned_clip = text_clip.with_duration(duration)
            if getattr(returned_clip, 'fps', None) is None:
                returned_clip.fps = fps
            return returned_clip
        
    def _apply_fade_effect(self, text_clip: TextClip, duration: int) -> TextClip:
        logger.debug(f"Применение эффекта 'появление/исчезание' к тексту '{str(text_clip.text)[:20]}...'")
        try:
            fade_duration = min(1.0, duration / 4.0 if duration > 0 else 0.25)
            
            # ИСПРАВЛЕНО: Используем правильные методы для MoviePy 2.x
            # Проверяем доступность методов fade
            if hasattr(text_clip, 'fadein') and hasattr(text_clip, 'fadeout'):
                return text_clip.with_duration(duration).fadein(fade_duration).fadeout(fade_duration)
            else:
                # Альтернативный способ для MoviePy 2.x
                logger.warning("Методы fadein/fadeout недоступны, используем альтернативный способ")
                
                # Используем crossfade эффект через opacity
                clip_with_duration = text_clip.with_duration(duration)
                
                # Создаем функцию изменения прозрачности
                def make_opacity_func(total_duration, fade_dur):
                    def opacity_func(get_frame, t):
                        frame = get_frame(t)
                        if t < fade_dur:
                            # Появление
                            alpha = t / fade_dur
                        elif t > total_duration - fade_dur:
                            # Исчезание
                            alpha = (total_duration - t) / fade_dur
                        else:
                            # Полная видимость
                            alpha = 1.0
                        
                        # Применяем альфа-канал
                        if len(frame.shape) == 3 and frame.shape[2] == 3:
                            # RGB -> RGBA
                            import numpy as np
                            alpha_channel = (alpha * 255).astype(frame.dtype)
                            alpha_array = np.full((frame.shape[0], frame.shape[1], 1), alpha_channel)
                            frame = np.concatenate([frame, alpha_array], axis=2)
                        elif len(frame.shape) == 3 and frame.shape[2] == 4:
                            # Уже RGBA
                            frame[:, :, 3] = (frame[:, :, 3] * alpha).astype(frame.dtype)
                        
                        return frame
                    return opacity_func
                
                # Применяем эффект прозрачности
                faded_clip = clip_with_duration.with_updated_frame_function(
                    make_opacity_func(duration, fade_duration)
                )
                
                logger.debug("Альтернативный fade эффект применен через изменение прозрачности")
                return faded_clip
                
        except Exception as e:
            logger.error(f"Ошибка применения fade эффекта: {e}", exc_info=True)
            return text_clip.with_duration(duration)
    
    def hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        try:
            hex_color = hex_color.lstrip('#')
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        except Exception as e:
            logger.warning(f"Ошибка конвертации HEX '{hex_color}' в RGB: {e}.", exc_info=True)
            return (255, 255, 255)
    
    def validate_color(self, color: str) -> bool:
        try:
            if not color.startswith('#') or len(color) != 7:
                return False
            int(color[1:], 16)
            return True
        except Exception:
            return False

def create_enhanced_video(
    image_paths: List[str],
    audio_tracks_info: List[Dict[str, Any]], 
    output_path: str,
    resolution: Tuple[int, int],
    duration: int,
    title_text: str = "",
    subtitle_text: str = "",
    text_color: str = "#ffffff",
    stroke_color: str = "#000000",
    stroke_width: int = 2,
    title_size: int = 40,
    subtitle_size: int = 24,
    effects: Optional[Dict[str, bool]] = None,
    font_path: Optional[str] = None,
    fps: int = 30,
    video_quality: str = "medium",
    codec_name: str = "libx264"
) -> str:
    logger.info(f"Запрос на создание видео: output='{output_path}', разрешение={resolution}, длительность={duration} сек.")
    logger.info(f"Параметры рендеринга: FPS={fps}, Качество (пресет)='{video_quality}', Кодек='{codec_name}'")
    logger.debug(f"Детали аудио запроса: {audio_tracks_info}")
    logger.debug(f"Детали остального запроса: изображения={len(image_paths)}, заголовок='{title_text[:20]}...', "
                 f"субтитры='{subtitle_text[:20]}...', цвет_текста='{text_color}', эффекты={effects}, шрифт='{font_path}'")
    
    main_clip_instance: Optional[CompositeVideoClip] = None
    video_clips_instances: List[ImageClip] = []
    valid_text_clips_instances: List[TextClip] = []
    audio_clip_resource: Optional[CompositeAudioClip] = None
    final_video_instance: Optional[CompositeVideoClip] = None

    try:
        effects_engine = TextEffectsEngine()
        if not effects_engine.validate_color(text_color):
            text_color = "#ffffff"
        if not effects_engine.validate_color(stroke_color):
            stroke_color = "#000000"
        
        video_clips_instances = create_image_clips(image_paths, resolution, duration, fps)
        if not video_clips_instances:
            raise ValueError("Не удалось создать видеоклипы из изображений.")
        
        main_clip_instance = video_clips_instances[0] if len(video_clips_instances) == 1 else create_slideshow(video_clips_instances, duration, fps)
        if not main_clip_instance:
            for vc_clip in video_clips_instances:
                try:
                    vc_clip.close()
                except:
                    pass
            raise ValueError("Не удалось создать основной видеоряд.")
        
        text_clips_list_temp: List[Optional[TextClip]] = []
        if title_text.strip():
            title_clip = effects_engine.create_enhanced_title_clip(
                title_text, resolution, duration, text_color, stroke_color,
                stroke_width, title_size, font_path, effects, fps)
            if title_clip:
                text_clips_list_temp.append(title_clip)
        if subtitle_text.strip():
            subtitle_clip = effects_engine.create_enhanced_subtitle_clip(
                subtitle_text, resolution, duration, text_color, stroke_color,
                stroke_width, subtitle_size, font_path, effects, fps)
            if subtitle_clip:
                text_clips_list_temp.append(subtitle_clip)
        
        valid_text_clips_instances = [clip for clip in text_clips_list_temp if clip is not None]
        
        all_clips_for_composite_list: List[Any] = [main_clip_instance] + valid_text_clips_instances
        final_video_instance = CompositeVideoClip(all_clips_for_composite_list, size=resolution)
        final_video_instance.fps = fps
        logger.info("Видеоряд и текстовые клипы скомпонованы.")
        
        # ====== ВКЛЮЧАЕМ АУДИО ОБРАТНО ======
        logger.info("✅ Аудио включено обратно!")
        
        if audio_tracks_info:
            logger.info(f"Создание аудиодорожки из информации: {len(audio_tracks_info)} треков")
            clean_audio_tracks = []
            for track in audio_tracks_info:
                clean_track = {k: v for k, v in track.items() if k != "item"}
                clean_audio_tracks.append(clean_track)
            
            audio_clip_resource = create_audio_track(clean_audio_tracks, float(duration))
            if audio_clip_resource:
                logger.debug("Добавление аудио к final_video_instance с помощью with_audio().")
                final_video_with_audio = final_video_instance.with_audio(audio_clip_resource)
                final_video_instance = final_video_with_audio
                logger.info("Аудиодорожка успешно добавлена к видео.")
            else:
                logger.warning("Не удалось создать или добавить аудиодорожку (audio_clip_resource is None).")
        else:
            logger.info("Информация об аудиодорожках отсутствует, аудио не будет добавлено.")
            
        if not final_video_instance:
            logger.critical("Финальный видеоклип (final_video_instance) не был создан. Невозможно записать видео.")
            if main_clip_instance:
                main_clip_instance.close()
            for vc_clip in video_clips_instances:
                vc_clip.close()
            for vtc_clip in valid_text_clips_instances:
                vtc_clip.close()
            if audio_clip_resource:
                audio_clip_resource.close()
            raise ValueError("Финальный видеоклип не был создан.")

        quality_preset_map = {"high": "medium", "medium": "fast", "low": "ultrafast"}
        codec_preset = quality_preset_map.get(video_quality.lower(), "fast")
        
        # Определяем временный файл аудио
        temp_audio_path = output_path.replace('.mp4', '_temp_audio.m4a')
        
        write_params = {
            "fps": fps,
            "audio_codec": 'aac',
            "temp_audiofile": temp_audio_path,
            "remove_temp": True,
            "threads": os.cpu_count() or 4,
            "logger": None
        }
        write_params["codec"] = codec_name
        if codec_name in ['libx264', 'libx265']:
            write_params["preset"] = codec_preset
        
        logger.info(f"Начало записи видео С АУДИО в файл: '{output_path}'. Параметры: {write_params}")
        final_video_instance.write_videofile(str(output_path), **write_params)
        
        logger.info(f"Видео С АУДИО успешно записано в файл: {output_path}")
        return str(output_path)
        
    except Exception as e:
        logger.critical(f"Критическая ошибка при создании видео '{output_path}': {e}", exc_info=True)
        raise
    finally:
        logger.debug("Начало освобождения ресурсов MoviePy...")
        if final_video_instance: 
            try: 
                final_video_instance.close() 
                logger.debug("Ресурс final_video_instance (главный композит) закрыт.")
            except Exception as e_fv: 
                logger.warning(f"Ошибка при закрытии final_video_instance: {e_fv}", exc_info=True)
        else:
            if main_clip_instance:
                try:
                    main_clip_instance.close()
                except Exception as e_mc:
                    logger.warning(f"Ошибка закрытия main_clip_instance (когда final_video не создан): {e_mc}", exc_info=True)
            if audio_clip_resource:
                try:
                    audio_clip_resource.close()
                except Exception as e_acr:
                    logger.warning(f"Ошибка закрытия audio_clip_resource (когда final_video не создан): {e_acr}", exc_info=True)
        
        logger.debug("Освобождение ресурсов MoviePy завершено (основные контейнеры закрыты).")


def get_available_effects() -> Dict[str, str]:
    return {"typewriter": "Печатная машинка", "fade": "Появление/исчезание", "none": "Без эффектов"}

def get_default_settings() -> Dict[str, Any]:
    logger.debug("Запрос настроек по умолчанию.")
    return {
        "text_color": "#ffffff", "stroke_color": "#000000", "stroke_width": 2,
        "title_size": 40, "subtitle_size": 24,
        "effects": {"typewriter": False, "fade": False},
        "fps": 30, "video_quality": "medium",
        "codec_name": "libx264", 
        "resolution": [1920, 1080], "duration": 60,
        "title_text": "", "subtitle_text": "",
        "font_path": None, "image_paths": [], "audio_tracks_info": []
    }

def validate_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    logger.debug(f"Валидация общих настроек: {settings}")
    defaults = get_default_settings()
    validated_settings = settings.copy()
    
    if not TextEffectsEngine().validate_color(validated_settings.get("text_color", "")):
        validated_settings["text_color"] = defaults["text_color"]
    if not TextEffectsEngine().validate_color(validated_settings.get("stroke_color", "")):
        validated_settings["stroke_color"] = defaults["stroke_color"]
    validated_settings["stroke_width"] = max(0, min(10, validated_settings.get("stroke_width", defaults["stroke_width"])))
    validated_settings["title_size"] = max(10, min(100, validated_settings.get("title_size", defaults["title_size"])))
    validated_settings["subtitle_size"] = max(8, min(80, validated_settings.get("subtitle_size", defaults["subtitle_size"])))
    
    current_effects = validated_settings.get("effects")
    if not isinstance(current_effects, dict):
        validated_settings["effects"] = defaults["effects"].copy()
    else:
        validated_effects_dict = defaults["effects"].copy()
        validated_effects_dict["typewriter"] = bool(current_effects.get("typewriter", defaults["effects"]["typewriter"]))
        validated_effects_dict["fade"] = bool(current_effects.get("fade", defaults["effects"]["fade"]))
        validated_settings["effects"] = validated_effects_dict
    
    loaded_fps = validated_settings.get("fps", defaults["fps"])
    if not isinstance(loaded_fps, int) or loaded_fps not in [24, 30, 60]:
        validated_settings["fps"] = defaults["fps"]
    
    loaded_quality = validated_settings.get("video_quality", defaults["video_quality"])
    if not isinstance(loaded_quality, str) or loaded_quality not in ["high", "medium", "low"]:
        validated_settings["video_quality"] = defaults["video_quality"]
    
    loaded_codec = validated_settings.get("codec_name", defaults["codec_name"])
    valid_codecs = ["libx264", "libx265"]
    if not isinstance(loaded_codec, str) or loaded_codec.lower() not in valid_codecs:
        validated_settings["codec_name"] = defaults["codec_name"]
    else:
        validated_settings["codec_name"] = loaded_codec.lower()
    
    loaded_audio_data = validated_settings.get("audio_tracks_info", defaults["audio_tracks_info"])
    if isinstance(loaded_audio_data, list):
        valid_audio_tracks = []
        for i, track_info_or_path in enumerate(loaded_audio_data):
            if isinstance(track_info_or_path, dict) and "path" in track_info_or_path and isinstance(track_info_or_path["path"], str):
                track_path = track_info_or_path["path"]
                start_time = track_info_or_path.get("start_time", 0)
                if not (isinstance(start_time, (int, float)) and start_time >=0):
                    start_time = 0.0
                valid_audio_tracks.append({"path": track_path, "start_time": float(start_time)})
            elif isinstance(track_info_or_path, str):
                valid_audio_tracks.append({"path": track_info_or_path, "start_time": 0.0})
            else:
                logger.warning(f"Некорректный формат элемента #{i} в 'audio_tracks_info': {track_info_or_path}.")
        validated_settings["audio_tracks_info"] = valid_audio_tracks
    else:
        validated_settings["audio_tracks_info"] = defaults["audio_tracks_info"].copy()
    
    return validated_settings