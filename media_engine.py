#!/usr/bin/env python3
"""
media_engine.py - Модуль обработки видео для VideoCreator
КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Фиксим проблему с AudioFileClip reader = None
"""

import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any 

from moviepy import (
    ImageClip, AudioFileClip, CompositeVideoClip,
    CompositeAudioClip, concatenate_videoclips,
    ColorClip
)

try:
    from moviepy.video.fx.all import crop
    CROP_FUNCTION_AVAILABLE = True
except ImportError:
    CROP_FUNCTION_AVAILABLE = False
    print("ПРЕДУПРЕЖДЕНИЕ: moviepy.video.fx.all.crop не найден. Пространственная обрезка в MoviePy может быть недоступна.")

try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("ПРЕДУПРЕЖДЕНИЕ: Библиотека Pillow (PIL) не найдена. Обрезка изображений может не работать корректно.")

from logger_setup import logger

def create_image_clips(image_paths: List[str], resolution: Tuple[int, int], total_duration: int, video_fps: int = 30) -> List[ImageClip]:
    logger.info(f"Начало создания клипов из {len(image_paths)} изображений. Общая длительность: {total_duration} сек, разрешение: {resolution}, FPS видео: {video_fps}.")
    clips_to_return = []
    if not image_paths:
        logger.warning("Список путей к изображениям пуст.")
        return [] 

    try:
        clip_duration = total_duration / len(image_paths)
        if clip_duration <= 0:
            logger.error(f"Рассчитанная длительность клипа ({clip_duration}) некорректна.")
            return []
    except ZeroDivisionError:
        logger.error("Ошибка: количество изображений равно нулю.")
        return []

    temp_files_to_delete = []
    
    for i, image_path_str in enumerate(image_paths):
        logger.debug(f"Обработка изображения {i+1}/{len(image_paths)}: '{image_path_str}'")
        current_image_path_for_moviepy = image_path_str
        
        processed_pil_image_path = None

        try:
            if PIL_AVAILABLE:
                img = PILImage.open(image_path_str)
                img = img.convert("RGB") 
                original_w, original_h = img.size

                target_h = resolution[1]
                scale_ratio = target_h / original_h
                new_w = int(original_w * scale_ratio)
                new_h = target_h
                
                resample_filter = PILImage.Resampling.LANCZOS if hasattr(PILImage.Resampling, 'LANCZOS') else PILImage.LANCZOS
                
                img_resized = img.resize((new_w, new_h), resample_filter)
                logger.debug(f"Изображение '{Path(image_path_str).name}' изменено Pillow до ({new_w}, {new_h})")
                processed_image_data = img_resized

                if new_w > resolution[0]:
                    target_w = resolution[0]
                    left = (new_w - target_w) / 2
                    right = left + target_w
                    img_cropped = img_resized.crop((int(left), 0, int(right), new_h))
                    logger.debug(f"Изображение обрезано Pillow до ({target_w}, {new_h})")
                    processed_image_data = img_cropped
                
                temp_image_path_obj = Path(image_path_str).parent / f"temp_pil_processed_{i}_{Path(image_path_str).name}"
                save_format = "PNG" 
                if temp_image_path_obj.suffix.lower() not in ['.png']:
                    temp_image_path_obj = temp_image_path_obj.with_suffix(".png")

                processed_image_data.save(temp_image_path_obj, format=save_format)
                current_image_path_for_moviepy = str(temp_image_path_obj)
                temp_files_to_delete.append(temp_image_path_obj)
                processed_pil_image_path = current_image_path_for_moviepy
            else:
                logger.warning("Pillow не доступен, предобработка средствами Pillow пропускаются.")

            final_clip_item: Optional[ImageClip] = None
            source_image_clip_obj: Optional[ImageClip] = None
            
            try:
                source_image_clip_obj = ImageClip(current_image_path_for_moviepy)
                source_image_clip_obj.fps = video_fps

                resize_attr = getattr(source_image_clip_obj, 'resize', None)
                if not resize_attr:
                    resize_attr = getattr(source_image_clip_obj, 'resized', None)
                if resize_attr:
                    current_moviepy_clip = resize_attr(height=resolution[1])
                else:
                    current_moviepy_clip = source_image_clip_obj
                
                if current_moviepy_clip.w > resolution[0]:
                    if CROP_FUNCTION_AVAILABLE:
                        current_moviepy_clip = crop(current_moviepy_clip, 
                                                    x_center=int(current_moviepy_clip.w / 2), 
                                                    width=int(resolution[0]))
                        logger.debug(f"MoviePy crop применен. Новая ширина: {current_moviepy_clip.w}")
                    else:
                        logger.warning("Функция crop недоступна. Попытка центрирования на фоне для 'обрезки'.")
                        background = ColorClip(size=(resolution[0], current_moviepy_clip.h), color=(0,0,0), duration=clip_duration)
                        background.fps = video_fps
                        positioned_image = current_moviepy_clip.with_position('center')
                        current_moviepy_clip = CompositeVideoClip([background, positioned_image], size=(resolution[0], current_moviepy_clip.h))
                
                final_clip_item = current_moviepy_clip
                
                if final_clip_item.w != resolution[0] or final_clip_item.h != resolution[1]:
                    logger.debug(f"Размеры клипа ({final_clip_item.w}x{final_clip_item.h}) отличаются от целевых ({resolution[0]}x{resolution[1]}). Создаем финальный фон.")
                    final_background = ColorClip(size=resolution, color=(0,0,0), is_mask=False, duration=clip_duration)
                    final_background.fps = video_fps

                    clip_to_composite = final_clip_item
                    if final_clip_item.w > resolution[0] or final_clip_item.h > resolution[1]:
                        resize_attr = getattr(final_clip_item, 'resize', None) or getattr(final_clip_item, 'resized', None)
                        if resize_attr:
                            if final_clip_item.w / final_clip_item.h > resolution[0] / resolution[1]:
                                clip_to_composite = resize_attr(width=resolution[0])
                            else:
                                clip_to_composite = resize_attr(height=resolution[1])
                    
                    if getattr(clip_to_composite, 'fps', None) is None: clip_to_composite.fps = video_fps
                    
                    positioned_final_image = clip_to_composite.with_position('center')
                    if getattr(positioned_final_image, 'fps', None) is None: positioned_final_image.fps = video_fps
                    
                    final_clip_item = CompositeVideoClip([final_background, positioned_final_image], 
                                                         size=resolution, use_bgclip=True, bg_color=(0,0,0,0))
                
                final_clip_item = final_clip_item.with_duration(clip_duration)
                if getattr(final_clip_item, 'fps', None) is None: final_clip_item.fps = video_fps

                clips_to_return.append(final_clip_item)
                logger.info(f"Клип для изображения '{Path(image_path_str).name}' успешно создан и добавлен в список.")

            except Exception as e_moviepy:
                logger.error(f"Ошибка MoviePy при создании ImageClip для '{current_image_path_for_moviepy}': {e_moviepy}", exc_info=True)
            finally:
                if source_image_clip_obj and (not clips_to_return or id(source_image_clip_obj) != id(clips_to_return[-1])):
                    try: source_image_clip_obj.close()
                    except: pass
        
        except Exception as e_pil_outer:
            logger.error(f"Ошибка Pillow при обработке изображения '{image_path_str}': {e_pil_outer}", exc_info=True)
    
    for temp_file in temp_files_to_delete:
        try:
            os.remove(temp_file)
            logger.debug(f"Временный файл Pillow {temp_file} удален.")
        except Exception as e_del:
            logger.warning(f"Не удалось удалить временный файл Pillow {temp_file}: {e_del}")

    if not clips_to_return: logger.warning("Не создано ни одного клипа изображений.")
    else: logger.info(f"Успешно создано {len(clips_to_return)} клипов изображений.")
    return clips_to_return


def create_slideshow(clips: List[ImageClip], total_duration: int, video_fps: int = 30) -> Optional[CompositeVideoClip]:
    logger.info(f"Начало создания слайдшоу из {len(clips)} клипов. Общая длительность: {total_duration} сек.")
    if not clips:
        logger.error("Список клипов для слайдшоу пуст.")
        return None
    
    if total_duration <= 0 or len(clips) == 0:
        logger.error("Общая длительность или количество клипов некорректны для слайдшоу.")
        return None
        
    clip_duration = total_duration / len(clips)
    if clip_duration <=0:
        logger.error(f"Рассчитанная длительность клипа ({clip_duration}) некорректна для слайдшоу.")
        return None

    processed_clips_for_concat = []
    
    try:
        for i, original_clip in enumerate(clips):
            if getattr(original_clip, 'fps', None) is None:
                original_clip.fps = video_fps 
            
            processed_clip = original_clip.with_duration(clip_duration)
            if getattr(processed_clip, 'fps', None) is None:
                 processed_clip.fps = video_fps
            processed_clips_for_concat.append(processed_clip)

        if not processed_clips_for_concat:
            logger.warning("Не удалось обработать клипы для слайдшоу.")
            return None

        final_slideshow = concatenate_videoclips(processed_clips_for_concat, method="compose")
        final_slideshow.fps = video_fps 
        
        if abs(final_slideshow.duration - total_duration) > 0.01:
             current_ref = final_slideshow 
             final_slideshow = final_slideshow.with_duration(total_duration)
             if id(final_slideshow) != id(current_ref) and hasattr(current_ref, 'close'):
                 try: current_ref.close()
                 except: pass
        
        logger.info("Слайдшоу успешно создано.")
        return final_slideshow

    except Exception as e:
        logger.error(f"Ошибка при создании слайдшоу: {e}", exc_info=True)
        for i, original_clip in enumerate(clips):
            if i < len(processed_clips_for_concat):
                processed_version = processed_clips_for_concat[i]
                if id(processed_version) != id(original_clip) and hasattr(processed_version, 'close'):
                    try: processed_version.close()
                    except: pass
        return None

def create_audio_track(
    audio_tracks_info: List[Dict[str, Any]], 
    target_duration: float
) -> Optional[CompositeAudioClip]:
    logger.info(f"Начало создания композитной аудиодорожки. Целевая длительность: {target_duration:.2f} сек. Количество треков: {len(audio_tracks_info)}.")
    if not audio_tracks_info:
        logger.info("Список информации об аудиодорожках пуст.")
        return None
    
    clips_for_composition: List[AudioFileClip] = []

    for i, track_info in enumerate(audio_tracks_info):
        audio_path = track_info.get("path")
        start_time = float(track_info.get("start_time", 0.0))

        if not audio_path or not Path(audio_path).exists():
            logger.warning(f"Трек {i+1}: путь к файлу '{audio_path}' отсутствует или некорректен. Пропуск.")
            continue
            
        logger.debug(f"Обработка аудиофайла {i+1}/{len(audio_tracks_info)}: '{audio_path}', время начала: {start_time:.2f} сек.")

        if start_time >= target_duration:
            logger.info(f"Время начала трека '{Path(audio_path).name}' ({start_time:.2f} сек) выходит за рамки ({target_duration:.2f} сек). Трек пропущен.")
            continue

        try:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Создаем новый AudioFileClip каждый раз
            audio_clip = AudioFileClip(str(audio_path))
            
            # Проверяем валидность клипа
            if not hasattr(audio_clip, 'reader') or audio_clip.reader is None:
                logger.error(f"AudioFileClip для '{audio_path}' не имеет корректного reader. Пропускаем.")
                try: audio_clip.close()
                except: pass
                continue
            
            # Проверяем длительность
            try:
                clip_duration = audio_clip.duration
                if clip_duration is None or clip_duration <= 0:
                    logger.error(f"AudioFileClip для '{audio_path}' имеет некорректную длительность: {clip_duration}. Пропускаем.")
                    audio_clip.close()
                    continue
            except Exception as e:
                logger.error(f"Ошибка при получении длительности для '{audio_path}': {e}. Пропускаем.")
                audio_clip.close()
                continue
            
            # Обрезаем клип если нужно
            effective_end_time = start_time + clip_duration
            if effective_end_time > target_duration:
                new_duration = target_duration - start_time
                if new_duration > 0.01:
                    logger.debug(f"Обрезаем трек '{Path(audio_path).name}' с {clip_duration:.2f}с до {new_duration:.2f}с.")
                    # ИСПРАВЛЕНИЕ: Используем subclipped для безопасной обрезки
                    try:
                        audio_clip = audio_clip.subclipped(0, new_duration)
                    except AttributeError:
                        # Fallback если subclipped недоступен
                        audio_clip = audio_clip.with_duration(new_duration)
                else:
                    logger.info(f"Трек '{Path(audio_path).name}' после обрезки слишком мал. Пропуск.")
                    audio_clip.close()
                    continue
            
            # Устанавливаем время начала
            positioned_clip = audio_clip.with_start(start_time)
            clips_for_composition.append(positioned_clip)
            
            logger.info(f"Аудиосегмент из '{Path(audio_path).name}' добавлен в композицию: начало={start_time:.2f}с, длит={positioned_clip.duration:.2f}с.")
            
        except Exception as e:
            logger.error(f"Ошибка обработки аудиофайла '{audio_path}': {e}", exc_info=True)
            continue
            
    if not clips_for_composition:
        logger.warning("Не удалось подготовить ни одного аудиосегмента.")
        return None

    try:
        logger.debug(f"Создание CompositeAudioClip из {len(clips_for_composition)} сегментов.")
        composite_audio = CompositeAudioClip(clips_for_composition)
        
        # Обрезаем финальную композицию до целевой длительности
        if composite_audio.duration > target_duration:
            logger.debug(f"Обрезаем композитное аудио с {composite_audio.duration:.2f}с до {target_duration:.2f}с.")
            composite_audio = composite_audio.with_duration(target_duration)
        
        logger.info(f"Финальная композитная аудиодорожка создана. Длительность: {composite_audio.duration:.2f} сек.")
        return composite_audio
        
    except Exception as e:
        logger.error(f"Ошибка при создании CompositeAudioClip: {e}", exc_info=True)
        # Закрываем все клипы при ошибке
        for clip in clips_for_composition:
            try: clip.close()
            except: pass
        return None

def validate_image_file(file_path: str) -> bool:
    try:
        if not os.path.exists(file_path): return False
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif'}
        return Path(file_path).suffix.lower() in valid_extensions
    except: return False

def validate_audio_file(file_path: str) -> bool:
    try:
        if not os.path.exists(file_path): return False
        valid_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'}
        return Path(file_path).suffix.lower() in valid_extensions
    except: return False

def get_media_info(file_path: str) -> dict:
    info = {'exists': False, 'size': 0, 'extension': '', 'name': ''}
    try:
        info['exists'] = os.path.exists(file_path)
        if info['exists']:
            path_obj = Path(file_path)
            info['size'] = path_obj.stat().st_size
            info['extension'] = path_obj.suffix.lower()
            info['name'] = path_obj.name
            
            img_clip_temp: Optional[ImageClip] = None
            audio_clip_temp: Optional[AudioFileClip] = None
            try:
                if info['extension'] in {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff'}:
                    if PIL_AVAILABLE:
                        with PILImage.open(file_path) as img:
                            info['dimensions'] = img.size
                            info['format'] = img.format
                    else: 
                        logger.warning("PIL (Pillow) не установлен для get_media_info.")
                        img_clip_temp = ImageClip(file_path)
                        info['dimensions'] = (img_clip_temp.w, img_clip_temp.h)
                elif info['extension'] in {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac'}:
                    audio_clip_temp = AudioFileClip(file_path)
                    if hasattr(audio_clip_temp, 'reader') and audio_clip_temp.reader is not None:
                        info['duration'] = audio_clip_temp.duration
                    else:
                        logger.warning(f"AudioFileClip для '{file_path}' не имеет корректного reader в get_media_info")
            except Exception as e_mi:
                 logger.warning(f"Ошибка получения доп. медиаинформации для '{info['name']}': {e_mi}")
            finally:
                if img_clip_temp: 
                    try: img_clip_temp.close()
                    except: pass
                if audio_clip_temp: 
                    try: audio_clip_temp.close()
                    except: pass
    except Exception as e:
        logger.error(f"Ошибка получения медиаинформации для '{file_path}': {e}", exc_info=True)
    return info