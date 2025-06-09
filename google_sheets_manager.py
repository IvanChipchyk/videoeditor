#!/usr/bin/env python3
"""
google_sheets_manager.py - Модуль для работы с Google Sheets в VideoCreator
Обеспечивает интеграцию с Google Sheets для загрузки данных проектов
"""

import os
from pathlib import Path
from typing import Optional, Dict, List, Any
import gspread
from google.oauth2.service_account import Credentials
from logger_setup import logger


class GoogleSheetsManager:
    """Менеджер для работы с Google Sheets"""
    
    def __init__(self, service_account_file: str, spreadsheet_id: str, sheet_name: str = "Лист1"):
        """
        Инициализация менеджера Google Sheets
        
        Args:
            service_account_file: Путь к файлу сервисного аккаунта
            spreadsheet_id: ID Google таблицы
            sheet_name: Имя листа в таблице
        """
        self.service_account_file = service_account_file
        self.spreadsheet_id = spreadsheet_id
        self.sheet_name = sheet_name
        self.client = None
        self.sheet = None
        
    def connect(self) -> bool:
        """
        Подключение к Google Sheets
        
        Returns:
            True если подключение успешно, False в противном случае
        """
        try:
            if not os.path.exists(self.service_account_file):
                logger.error(f"Файл сервисного аккаунта не найден: {self.service_account_file}")
                return False
                
            logger.info("Подключение к Google Sheets...")
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_file(self.service_account_file, scopes=SCOPES)
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(self.spreadsheet_id).worksheet(self.sheet_name)
            logger.info("Успешно подключено к Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка подключения к Google Sheets: {e}", exc_info=True)
            return False
    
    def get_all_themes(self) -> List[str]:
        """
        Получить список всех доступных тем (знаков зодиака и др.)
        
        Returns:
            Список тем из первой колонки таблицы
        """
        if not self.sheet:
            logger.error("Нет подключения к Google Sheets")
            return []
            
        try:
            # Получаем все значения из первой колонки (A)
            all_values = self.sheet.col_values(1)
            
            # Фильтруем пустые значения и заголовок
            themes = []
            for idx, value in enumerate(all_values[1:], start=1):  # Пропускаем заголовок
                if value.strip():
                    themes.append(value.strip())
                else:
                    break  # Прекращаем при первой пустой ячейке
                    
            logger.info(f"Найдено тем: {len(themes)}")
            return themes
            
        except Exception as e:
            logger.error(f"Ошибка получения списка тем: {e}", exc_info=True)
            return []
    
    def get_theme_data(self, theme: str) -> Optional[Dict[str, str]]:
        """
        Получить данные для конкретной темы
        
        Args:
            theme: Название темы (например, "Овен")
            
        Returns:
            Словарь с данными темы или None если не найдено
        """
        if not self.sheet:
            logger.error("Нет подключения к Google Sheets")
            return None
            
        try:
            logger.info(f"Поиск данных для темы: {theme}")
            
            # Получаем все данные таблицы
            all_data = self.sheet.get_all_values()
            
            # Ищем строку с нужной темой
            for row_idx, row in enumerate(all_data[1:], start=2):  # Пропускаем заголовок
                if len(row) >= 2 and row[0].strip() == theme:
                    data = {
                        'theme': row[0].strip(),
                        'title': row[0].strip(),  # Используем название темы как заголовок
                        'text': row[1].strip() if len(row) > 1 else "",
                        'row_number': row_idx
                    }
                    logger.info(f"Найдены данные для темы '{theme}': {len(data['text'])} символов текста")
                    return data
            
            logger.warning(f"Данные для темы '{theme}' не найдены")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения данных темы '{theme}': {e}", exc_info=True)
            return None
    
    def update_theme_text(self, theme: str, new_text: str) -> bool:
        """
        Обновить текст для темы в Google Sheets
        
        Args:
            theme: Название темы
            new_text: Новый текст
            
        Returns:
            True если обновление успешно, False в противном случае
        """
        if not self.sheet:
            logger.error("Нет подключения к Google Sheets")
            return False
            
        try:
            # Сначала получаем данные темы чтобы узнать номер строки
            theme_data = self.get_theme_data(theme)
            if not theme_data:
                logger.error(f"Не найдена тема '{theme}' для обновления")
                return False
            
            row_number = theme_data['row_number']
            self.sheet.update_cell(row_number, 2, new_text)  # Колонка B (текст)
            
            logger.info(f"Текст для темы '{theme}' успешно обновлен")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка обновления текста для темы '{theme}': {e}", exc_info=True)
            return False


class ProjectDataManager:
    """Менеджер для комплексной загрузки данных проекта"""
    
    def __init__(self, google_sheets_manager: GoogleSheetsManager, 
                 audio_folder: str = "output", 
                 templates_folder: str = "saved_templates"):
        """
        Инициализация менеджера данных проекта
        
        Args:
            google_sheets_manager: Экземпляр GoogleSheetsManager
            audio_folder: Папка с аудиофайлами
            templates_folder: Папка с шаблонами
        """
        self.sheets_manager = google_sheets_manager
        self.audio_folder = Path(audio_folder)
        self.templates_folder = Path(templates_folder)
        
    def find_audio_file(self, theme: str) -> Optional[str]:
        """
        Найти аудиофайл для темы
        
        Args:
            theme: Название темы
            
        Returns:
            Путь к аудиофайлу или None
        """
        # Создаем безопасное имя файла (заменяем пробелы и спецсимволы)
        safe_filename = theme.replace(' ', '_').replace('-', '_')
        
        # Варианты имен файлов для поиска
        possible_names = [
            f"{theme}.mp3",
            f"{safe_filename}.mp3",
            f"{theme.lower()}.mp3",
            f"{safe_filename.lower()}.mp3"
        ]
        
        # Ищем файл
        for filename in possible_names:
            audio_path = self.audio_folder / filename
            if audio_path.exists():
                logger.info(f"Найден аудиофайл для темы '{theme}': {audio_path}")
                return str(audio_path)
        
        logger.warning(f"Аудиофайл для темы '{theme}' не найден в папке {self.audio_folder}")
        return None
    
    def find_template_file(self, theme: str) -> Optional[str]:
        """
        Найти файл шаблона для темы
        
        Args:
            theme: Название темы
            
        Returns:
            Путь к файлу шаблона или None
        """
        # Создаем безопасное имя файла
        safe_filename = theme.replace(' ', '_').replace('-', '_').lower()
        
        # Варианты имен файлов для поиска
        possible_names = [
            f"{safe_filename}.json",
            f"{theme.lower()}.json",
            f"{theme}.json"
        ]
        
        # Ищем файл
        for filename in possible_names:
            template_path = self.templates_folder / filename
            if template_path.exists():
                logger.info(f"Найден шаблон для темы '{theme}': {template_path}")
                return str(template_path)
        
        logger.warning(f"Шаблон для темы '{theme}' не найден в папке {self.templates_folder}")
        return None
    
    def load_project_data(self, theme: str) -> Dict[str, Any]:
        """
        Загрузить все данные проекта для темы
        
        Args:
            theme: Название темы
            
        Returns:
            Словарь с данными проекта
        """
        result = {
            'success': False,
            'theme': theme,
            'text_data': None,
            'audio_path': None,
            'template_path': None,
            'errors': []
        }
        
        # Получаем текстовые данные из Google Sheets
        if self.sheets_manager.connect():
            text_data = self.sheets_manager.get_theme_data(theme)
            if text_data:
                result['text_data'] = text_data
            else:
                result['errors'].append(f"Текстовые данные для темы '{theme}' не найдены в Google Sheets")
        else:
            result['errors'].append("Не удалось подключиться к Google Sheets")
        
        # Ищем аудиофайл
        audio_path = self.find_audio_file(theme)
        if audio_path:
            result['audio_path'] = audio_path
        else:
            result['errors'].append(f"Аудиофайл для темы '{theme}' не найден")
        
        # Ищем шаблон
        template_path = self.find_template_file(theme)
        if template_path:
            result['template_path'] = template_path
        else:
            # Это не критичная ошибка, можно использовать шаблон по умолчанию
            logger.info(f"Шаблон для темы '{theme}' не найден, будет использован текущий или по умолчанию")
        
        # Определяем успешность загрузки
        result['success'] = result['text_data'] is not None and result['audio_path'] is not None
        
        if result['success']:
            logger.info(f"Данные проекта для темы '{theme}' успешно загружены")
        else:
            logger.error(f"Не удалось загрузить все необходимые данные для темы '{theme}'")
        
        return result


# Вспомогательные функции для быстрого доступа
def get_available_themes(service_account_file: str, spreadsheet_id: str, sheet_name: str = "Лист1") -> List[str]:
    """Получить список доступных тем из Google Sheets"""
    manager = GoogleSheetsManager(service_account_file, spreadsheet_id, sheet_name)
    if manager.connect():
        return manager.get_all_themes()
    return []


def load_theme_project(theme: str, service_account_file: str, spreadsheet_id: str, 
                      sheet_name: str = "Лист1", audio_folder: str = "output", 
                      templates_folder: str = "saved_templates") -> Dict[str, Any]:
    """Загрузить полные данные проекта для темы"""
    sheets_manager = GoogleSheetsManager(service_account_file, spreadsheet_id, sheet_name)
    project_manager = ProjectDataManager(sheets_manager, audio_folder, templates_folder)
    return project_manager.load_project_data(theme)