#!/usr/bin/env python3
"""
logger_setup.py - Модуль для настройки логирования VideoCreator
ЭТАП 4: Логирование процесса
"""

import logging
import sys
from pathlib import Path

LOG_DIR_NAME = "logs"
LOG_FILE_NAME = "videocreator.log"

# Определяем базовую директорию для логов
try:
    BASE_DIR = Path(__file__).resolve().parent
except NameError:
    BASE_DIR = Path.cwd()

LOG_DIR = BASE_DIR / LOG_DIR_NAME

def setup_logger(name: str = "VideoCreatorLogger", log_level: int = logging.INFO) -> logging.Logger:
    """
    Настраивает и возвращает экземпляр логгера.
    """
    # Создаем директорию для логов, если она не существует
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Критическая ошибка: Не удалось создать директорию для логов {LOG_DIR}: {e}", file=sys.stderr)
        # В случае невозможности создать директорию логов, можно либо падать,
        # либо продолжать без файлового логирования, выводя только в консоль.
        # Пока просто выведем ошибку и продолжим (логгер не будет писать в файл).

    logger = logging.getLogger(name)
    
    # Предотвращаем дублирование обработчиков, если функция вызывается несколько раз
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(log_level)

    # Форматтер для сообщений
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(module)s.%(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Обработчик для вывода в консоль (для отладки и информации)
    console_handler = logging.StreamHandler(sys.stdout) # Используем stdout для обычных логов
    console_handler.setFormatter(formatter)
    # Можно установить другой уровень для консоли, например, DEBUG, если нужно больше деталей при разработке
    # console_handler.setLevel(logging.DEBUG) 
    logger.addHandler(console_handler)

    # Обработчик для записи в файл
    log_file_path = LOG_DIR / LOG_FILE_NAME
    try:
        file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8') # 'a' для добавления
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.error(f"Не удалось настроить файловый обработчик для логов: {e}")


    logger.info(f"Логгер '{name}' настроен. Уровень логирования: {logging.getLevelName(log_level)}.")
    if file_handler in logger.handlers:
         logger.info(f"Логи будут записываться в: {log_file_path.resolve()}")
    else:
        logger.warning(f"Файловое логирование не настроено из-за предыдущей ошибки.")


    # Пример перехвата необработанных исключений (опционально, но полезно)
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Необработанное исключение:", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
    
    return logger

# Получаем основной логгер приложения при импорте модуля
# Это позволит другим модулям просто делать `from logger_setup import logger`
logger = setup_logger()

if __name__ == '__main__':
    # Пример использования логгера
    logger.debug("Это сообщение для отладки.")
    logger.info("Это информационное сообщение.")
    logger.warning("Это предупреждение.")
    logger.error("Это сообщение об ошибке.")
    logger.critical("Это критическое сообщение.")

    # Пример логирования исключения
    try:
        x = 1 / 0
    except ZeroDivisionError:
        logger.error("Произошла ошибка деления на ноль", exc_info=True) # exc_info=True добавляет traceback
    
    logger.info("Тестирование логгера завершено.")
    # Для теста необработанного исключения:
    # raise ValueError("Тестовое необработанное исключение для проверки sys.excepthook")