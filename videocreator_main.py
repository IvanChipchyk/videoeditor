#!/usr/bin/env python3
"""
VideoCreator - Десктопное приложение для создания видео
ЭТАП А: Визуализация формы волны (waveform) на таймлайне аудио
"""

import sys
import os
from pathlib import Path
import numpy as np # <--- ДОБАВЛЕН ИМПОРТ NUMPY

current_script_dir = Path(__file__).parent.resolve()
if str(current_script_dir) not in sys.path:
    sys.path.append(str(current_script_dir))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QFileDialog, QLineEdit, QTextEdit,
    QSpinBox, QComboBox, QProgressBar, QMessageBox, QGroupBox,
    QGridLayout, QSizePolicy, QColorDialog, QCheckBox, QListWidget,
    QListWidgetItem, QInputDialog, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsSimpleTextItem, QGraphicsItemGroup,
    QGraphicsLineItem, QGraphicsItem, QGraphicsPathItem # <--- ДОБАВЛЕН QGraphicsPathItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRectF, QPointF, QTimer
from PyQt6.QtGui import (
    QFont, QPixmap, QIcon, QColor, QBrush, QPen, QPainter, QResizeEvent,
    QPainterPath, QCloseEvent # <--- ДОБАВЛЕН QCloseEvent в правильное место
)

from typing import List, Optional, Dict, Any, Tuple

from logger_setup import logger

try:
    from google_sheets_manager import GoogleSheetsManager, ProjectDataManager, get_available_themes
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Google Sheets модули недоступны: {e}")
    GOOGLE_SHEETS_AVAILABLE = False

try:
    from text_effects_engine import create_enhanced_video, get_default_settings, validate_settings
    import template_manager
    from moviepy import AudioFileClip
except ImportError as e:
    missing_module = "template_manager" if "template_manager" in str(e) else "text_effects_engine or moviepy"
    logger.critical(f"Критическая ошибка импорта модуля {missing_module}: {e}", exc_info=True)
    print(f"Критическая ошибка импорта модуля {missing_module}: {e}", file=sys.stderr)
    if "moviepy" in str(e).lower():
        print("Убедитесь, что библиотека moviepy установлена: pip install moviepy", file=sys.stderr)
    sys.exit(1)

RULER_HEIGHT = 25
AUDIO_TRACK_HEIGHT = 30 # Общая высота блока
AUDIO_TRACK_SPACING = 5
AUDIO_TRACK_BASE_Y = RULER_HEIGHT + 10
DELETE_BUTTON_SIZE = 16 # Немного уменьшим кнопку
TEXT_ITEM_PADDING = 5
TIMELINE_MARGIN = 10
WAVEFORM_COLOR = QColor(Qt.GlobalColor.darkBlue) # Цвет для формы волны
WAVEFORM_SAMPLES_PER_PIXEL = 50 # Сколько сэмплов аудио усреднять для одного пикселя формы волны (упрощение)

class AudioTrackItem(QGraphicsItemGroup):
    def __init__(self, track_info: Dict[str, Any], display_name: str,
                 x: float, y: float, width: float, height: float, color: QColor,
                 timeline_app_ref: 'VideoCreatorApp', parent=None):
        super().__init__(parent)
        self.track_info = track_info
        self.audio_path = track_info["path"]
        self.timeline_app_ref = timeline_app_ref
        self.initial_y = y

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)

        self.rect_item = QGraphicsRectItem(0, 0, width, height, self)
        self.rect_item.setBrush(QBrush(color))
        self.rect_item.setPen(QPen(Qt.GlobalColor.black, 1))
        self.addToGroup(self.rect_item)
        
        # Элемент для формы волны
        self.waveform_path_item = QGraphicsPathItem(self)
        self.waveform_path_item.setPen(QPen(WAVEFORM_COLOR, 1))
        self.addToGroup(self.waveform_path_item)

        self.text_item = QGraphicsSimpleTextItem(display_name, self)
        font = self.text_item.font()
        font.setPointSize(8)
        self.text_item.setFont(font)
        # Позиционируем текст, чтобы он не перекрывался с волной (если волна по центру)
        self.text_item.setPos(TEXT_ITEM_PADDING, TEXT_ITEM_PADDING)
        self.addToGroup(self.text_item)

        delete_btn_x = width - DELETE_BUTTON_SIZE - TEXT_ITEM_PADDING / 2
        delete_btn_y = TEXT_ITEM_PADDING / 2 # Кнопка в правом верхнем углу
        self.delete_button_rect = QRectF(delete_btn_x, delete_btn_y, DELETE_BUTTON_SIZE, DELETE_BUTTON_SIZE)
        
        self.delete_text_item = QGraphicsSimpleTextItem("X", self)
        delete_text_font = QFont()
        delete_text_font.setBold(True)
        delete_text_font.setPointSize(7)
        self.delete_text_item.setFont(delete_text_font)
        self.delete_text_item.setBrush(QBrush(Qt.GlobalColor.red))
        
        text_br = self.delete_text_item.boundingRect()
        self.delete_text_item.setPos(
            delete_btn_x + (DELETE_BUTTON_SIZE - text_br.width()) / 2,
            delete_btn_y + (DELETE_BUTTON_SIZE - text_br.height()) / 2
        )
        self.addToGroup(self.delete_text_item)
        self.setPos(x, y)

    def set_waveform_data(self, waveform_points: List[Tuple[float, float, float, float]]):
        """
        Устанавливает данные для отрисовки формы волны.
        waveform_points: список кортежей (x1, y1_top, x2, y1_bottom) для каждой вертикальной линии.
                         y1_top и y1_bottom относительно центральной линии блока.
        """
        path = QPainterPath()
        center_y = self.rect_item.boundingRect().height() / 2
        for x, y_top_rel, _, y_bottom_rel in waveform_points: # x2 и y2_top пока не используем для простых линий
            path.moveTo(x, center_y - y_top_rel)
            path.lineTo(x, center_y + y_bottom_rel)
            
        self.waveform_path_item.setPath(path)
        logger.debug(f"Waveform path set for {self.audio_path} with {len(waveform_points)} segments.")

    def boundingRect(self) -> QRectF:
        return self.rect_item.boundingRect()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange: 
            new_pos: QPointF = value
            new_pos.setY(self.y()) 
            if new_pos.x() < TIMELINE_MARGIN:
                new_pos.setX(TIMELINE_MARGIN)
            return new_pos

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged: 
            new_x = self.pos().x()
            pixels_per_second, _ = self.timeline_app_ref._calculate_timeline_scale()
            if pixels_per_second > 0: 
                new_start_time = (new_x - TIMELINE_MARGIN) / pixels_per_second
                new_start_time = max(0, new_start_time) 

                total_video_duration = float(self.timeline_app_ref.duration_input.value())
                audio_actual_duration = self.track_info.get("duration", 0.0)
                if new_start_time + audio_actual_duration > total_video_duration:
                    new_start_time = total_video_duration - audio_actual_duration
                    new_start_time = max(0, new_start_time) 
                    corrected_x = TIMELINE_MARGIN + new_start_time * pixels_per_second
                    if abs(self.pos().x() - corrected_x) > 0.1 : 
                         self.setPos(corrected_x, self.y())
                
                self.timeline_app_ref.update_audio_track_start_time(self.audio_path, new_start_time)
            else:
                logger.warning("pixels_per_second равен нулю, не удалось обновить start_time.")
        return super().itemChange(change, value)

    def mousePressEvent(self, event: 'QGraphicsSceneMouseEvent'):
        if self.delete_button_rect.contains(event.pos()):
            if self.scene() and hasattr(self.scene(), 'request_delete_track_item'):
                self.scene().request_delete_track_item(self)
        else:
            super().mousePressEvent(event)
            
    def hoverEnterEvent(self, event: 'QGraphicsSceneHoverEvent'):
        self.delete_text_item.setBrush(QBrush(Qt.GlobalColor.darkRed))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: 'QGraphicsSceneHoverEvent'):
        self.delete_text_item.setBrush(QBrush(Qt.GlobalColor.red))
        super().hoverLeaveEvent(event)


class CustomGraphicsScene(QGraphicsScene):
    track_delete_requested_signal = pyqtSignal(str) 

    def __init__(self, parent=None):
        super().__init__(parent)

    def request_delete_track_item(self, item: AudioTrackItem):
        self.track_delete_requested_signal.emit(item.audio_path)


class VideoCreatorThread(QThread):
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    finished_successfully = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, video_params):
        super().__init__()
        self.video_params = video_params
        logger.debug(f"VideoCreatorThread инициализирован с параметрами вывода: {video_params.get('output_path', 'N/A')}")

    def run(self):
        logger.info(f"Поток VideoCreatorThread: Начало создания видео. Путь вывода: {self.video_params.get('output_path')}")
        try:
            self.status_updated.emit("Начинаем создание видео...")
            self.progress_updated.emit(10)
            if not self.video_params.get('image_paths'):
                logger.error("Поток VideoCreatorThread: Отсутствуют пути к изображениям.")
                raise ValueError("Не указаны изображения")

            logger.debug("Поток VideoCreatorThread: Обновление статуса и прогресса перед вызовом create_enhanced_video.")
            self.progress_updated.emit(30)
            self.status_updated.emit("Обрабатываем медиафайлы...")

            output_path = create_enhanced_video(**self.video_params)

            logger.info(f"Поток VideoCreatorThread: Видео успешно создано: {output_path}")
            self.progress_updated.emit(100)
            self.finished_successfully.emit(output_path)

        except Exception as e:
            logger.error(f"Поток VideoCreatorThread: Ошибка при создании видео: {e}", exc_info=True)
            self.error_occurred.emit(f"Ошибка в процессе создания видео: {str(e)}")
        logger.info("Поток VideoCreatorThread: Завершение работы.")

class VideoCreatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("Инициализация приложения VideoCreatorApp...")
        self.image_paths: List[str] = []
        self.audio_tracks_info: List[Dict[str, Any]] = []
        self.font_path: Optional[str] = None
        self.video_thread: Optional[VideoCreatorThread] = None

        self.default_settings = get_default_settings()
        logger.debug(f"Загружены настройки по умолчанию: {self.default_settings}")
        self.current_text_color: str = self.default_settings['text_color']
        self.current_stroke_color: str = self.default_settings['stroke_color']
        
        self.next_audio_track_y = AUDIO_TRACK_BASE_Y
        self.ruler_items: List[QGraphicsItem] = [] 
        
        # Настройки Google Sheets
        self.GOOGLE_SHEET_ID = "1FQV-3SZGYoR1z3ZY9zwmycQmoWbQ230MeKueWDjWroI"
        self.SHEET_NAME = "Лист1"
        self.SERVICE_ACCOUNT_FILE = "elevenlabs-voice-generator-9cd6aae15cf6.json"
        self.AUDIO_OUTPUT_FOLDER = "output"

        template_manager.ensure_templates_dir_exists()
        logger.info("Директория шаблонов проверена/создана.")

        self.init_ui() 
        
        QTimer.singleShot(0, self._redraw_audio_timeline) 
        logger.info("Интерфейс VideoCreatorApp успешно инициализирован.")

    def get_contrasting_text_color(self, hex_color_str: str) -> str:
        logger.debug(f"Определение контрастного цвета для HEX: {hex_color_str}")
        try:
            hex_color = hex_color_str.lstrip('#')
            if len(hex_color) == 3:
                r, g, b = tuple(int(hex_color[i:i+1]*2, 16) for i in (0, 1, 2))
            elif len(hex_color) == 6:
                r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            else:
                logger.warning(f"Некорректная длина HEX цвета '{hex_color_str}'. Возвращен черный.")
                return '#000000'

            brightness = (r * 299 + g * 587 + b * 114) / 1000
            contrasting_color = '#FFFFFF' if brightness < 128 else '#000000'
            logger.debug(f"Для HEX {hex_color_str} (R:{r},G:{g},B:{b}, Brightness:{brightness:.2f}) контрастный цвет: {contrasting_color}")
            return contrasting_color
        except Exception as e:
            logger.error(f"Ошибка при определении контрастного цвета для '{hex_color_str}': {e}", exc_info=True)
            return '#000000'

    def init_ui(self):
        logger.debug("Начало init_ui()")
        self.setWindowTitle("VideoCreator Pro")
        self.setGeometry(100, 100, 1250, 850)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.title_app_label = QLabel("🎬 VideoCreator Pro")
        self.title_app_label.setObjectName("TitleAppLabel")
        self.title_app_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.title_app_label)

        self.tab_widget = QTabWidget()
        
        self.create_video_tab() 
        self.create_templates_tab()
        main_layout.addWidget(self.tab_widget)

        self.setStyleSheet("""
            QMainWindow { background-color: #f8f9fa; }
            QLabel { color: #2c3e50; font-weight: normal; }
            QLabel#TitleAppLabel { font-size: 28px; font-weight: bold; color: #2c3e50; margin: 20px; }
            QLabel#ImagesLabel, QLabel#AudioTracksInfoLabel, QLabel#FontLabel { color: #000000; font-style: normal; font-weight: bold; }
            QLabel#ImagesLabel[status="loaded"], QLabel#AudioTracksInfoLabel[status="loaded"], QLabel#FontLabel[status="loaded"] { color: #27ae60; font-weight: bold; font-style: normal; }
            QPushButton { background-color: #3498db; color: white; border: none; padding: 10px 20px; border-radius: 5px; font-weight: bold; }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #21618c; }
            QPushButton:disabled { background-color: #95a5a6; }
            QPushButton#DeleteButton { background-color: #e74c3c; padding: 5px 10px; font-size: 12px; }
            QPushButton#DeleteButton:hover { background-color: #c0392b; }
            QLineEdit, QTextEdit, QComboBox { padding: 8px; border: 1px solid #bdc3c7; border-radius: 5px; background-color: white; color: #333333; }
            QSpinBox { padding: 8px; border: 1px solid #bdc3c7; border-radius: 5px; background-color: white; color: #000000; }
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QComboBox:focus { border-color: #3498db; }
            QMessageBox QLabel { color: #FFFFFF; font-weight: bold; }
            QGroupBox { font-weight: bold; border: 1px solid #bdc3c7; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px 0 5px; color: #2c3e50; }
            QCheckBox { color: #2c3e50; }
            QListWidget { border: 1px solid #bdc3c7; border-radius: 5px; background-color: white; }
            QGraphicsView { border: 1px solid #bdc3c7; border-radius: 5px; background-color: #e9e9e9; }
            QTabWidget::pane { border: 1px solid #bdc3c7; border-top-right-radius: 5px; border-bottom-left-radius: 5px; border-bottom-right-radius: 5px; }
            QTabBar::tab { background: #ecf0f1; color: #2c3e50; padding: 10px 20px; margin-right: 2px; border-top-left-radius: 5px; border-top-right-radius: 5px; font-weight: bold; }
            QTabBar::tab:selected { background: #3498db; color: white; }
            QTabBar::tab:hover { background: #dde4e6; color: #1a252f; }
        """)
        logger.debug("Завершение init_ui()")

    def resizeEvent(self, event: QResizeEvent): 
        super().resizeEvent(event) 
        if hasattr(self, 'audio_timeline_view') and self.audio_timeline_view.isVisible():
            QTimer.singleShot(50, self._redraw_audio_timeline)

    def create_video_tab(self):
        logger.debug("Создание вкладки 'Создание видео'")
        tab = QWidget()
        layout = QVBoxLayout(tab)
        main_grid = QGridLayout()
        main_grid.setSpacing(15)
        
        settings_group = self.create_settings_group() 
        main_grid.addWidget(settings_group, 0, 2)

        media_group = self.create_media_group() 
        main_grid.addWidget(media_group, 0, 0, 2, 1) 
        
        text_group = self.create_text_group()
        main_grid.addWidget(text_group, 0, 1)

        text_style_group = self.create_text_style_group()
        main_grid.addWidget(text_style_group, 1, 1)
        
        preview_group = self.create_preview_group()
        main_grid.addWidget(preview_group, 1, 2, 2, 1)

        main_grid.setColumnStretch(0, 1) 
        main_grid.setColumnStretch(1, 1) 
        main_grid.setColumnStretch(2, 1)

        layout.addLayout(main_grid)
        self.tab_widget.addTab(tab, "🎥 Создание видео")
        logger.debug("Вкладка 'Создание видео' создана и добавлена.")

    def create_media_group(self):
        logger.debug("Создание группы 'Медиафайлы'")
        group = QGroupBox("📁 Медиафайлы")
        group_layout = QVBoxLayout(group)

        # Секция загрузки проекта по теме (только если Google Sheets доступны)
        if GOOGLE_SHEETS_AVAILABLE:
            theme_section_label = QLabel("🌟 Быстрая загрузка проекта:")
            theme_section_label.setStyleSheet("font-weight: bold; color: #2980b9;")
            group_layout.addWidget(theme_section_label)
            
            theme_layout = QHBoxLayout()
            self.theme_combo = QComboBox()
            self.theme_combo.setPlaceholderText("Выберите тему...")
            self.theme_combo.setMinimumWidth(200)
            theme_layout.addWidget(self.theme_combo)
            
            self.refresh_themes_btn = QPushButton("🔄")
            self.refresh_themes_btn.setMaximumWidth(40)
            self.refresh_themes_btn.setToolTip("Обновить список тем из Google Sheets")
            self.refresh_themes_btn.clicked.connect(self.refresh_themes_list)
            theme_layout.addWidget(self.refresh_themes_btn)
            
            self.load_theme_btn = QPushButton("📥 Загрузить проект")
            self.load_theme_btn.clicked.connect(self.load_project_by_theme)
            theme_layout.addWidget(self.load_theme_btn)
            
            group_layout.addLayout(theme_layout)
            group_layout.addSpacing(15)
            
            # Разделитель
            separator = QLabel("─" * 50)
            separator.setStyleSheet("color: #bdc3c7;")
            group_layout.addWidget(separator)
            group_layout.addSpacing(10)

        self.images_btn = QPushButton("🖼️ Загрузить изображения")
        self.images_btn.clicked.connect(self.load_images)
        group_layout.addWidget(self.images_btn)

        self.images_label = QLabel("Изображения не загружены")
        self.images_label.setObjectName("ImagesLabel")
        self.images_label.setProperty("status", "unloaded")
        group_layout.addWidget(self.images_label)

        self.font_btn = QPushButton("🔤 Загрузить шрифт (TTF)")
        self.font_btn.clicked.connect(self.load_font)
        group_layout.addWidget(self.font_btn)

        self.font_label = QLabel("Стандартный шрифт")
        self.font_label.setObjectName("FontLabel")
        self.font_label.setProperty("status", "unloaded")
        group_layout.addWidget(self.font_label)

        group_layout.addSpacing(15)

        audio_section_label = QLabel("🎧 Аудиодорожки (Таймлайн):") 
        audio_section_label.setStyleSheet("font-weight: bold;")
        group_layout.addWidget(audio_section_label)

        self.add_audio_btn = QPushButton("🎵 Добавить аудиодорожку")
        self.add_audio_btn.clicked.connect(self.load_audio)
        group_layout.addWidget(self.add_audio_btn)

        self.audio_scene = CustomGraphicsScene(self)
        self.audio_scene.track_delete_requested_signal.connect(self._handle_track_delete_request)

        self.audio_timeline_view = QGraphicsView(self.audio_scene)
        self.audio_timeline_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.audio_timeline_view.setMinimumHeight(150) 
        self.audio_timeline_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.audio_timeline_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn) 
        self.audio_timeline_view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        group_layout.addWidget(self.audio_timeline_view)

        self.audio_tracks_info_label = QLabel("Аудио не добавлено")
        self.audio_tracks_info_label.setObjectName("AudioTracksInfoLabel")
        self.audio_tracks_info_label.setProperty("status", "unloaded")
        group_layout.addWidget(self.audio_tracks_info_label)

        group_layout.addStretch(1)
        
        self.style().polish(self.images_label)
        self.style().polish(self.font_label)
        self.style().polish(self.audio_tracks_info_label)
        
        QTimer.singleShot(0, self._connect_duration_input_signal)
        
        # Загружаем список тем при запуске (только если Google Sheets доступны)
        if GOOGLE_SHEETS_AVAILABLE:
            QTimer.singleShot(100, self.refresh_themes_list)
        
        return group

    def create_text_group(self):
        logger.debug("Создание группы 'Текстовое содержание'")
        group = QGroupBox("✏️ Текстовое содержание")
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel("Заголовок:"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Например: Овен — 27 мая")
        layout.addWidget(self.title_input)
        
        layout.addWidget(QLabel("Субтитры/основной текст:"))
        self.subtitle_input = QTextEdit()
        self.subtitle_input.setPlaceholderText("Введите основной текст видео...")
        self.subtitle_input.setFixedHeight(100) 
        layout.addWidget(self.subtitle_input)
        return group

    def create_text_style_group(self):
        logger.debug("Создание группы 'Стиль текста и эффекты'")
        group = QGroupBox("🎨 Стиль текста и эффекты")
        layout = QGridLayout(group)

        layout.addWidget(QLabel("Цвет текста:"), 0, 0)
        self.text_color_btn = QPushButton(self.current_text_color)
        self.text_color_btn.setStyleSheet(f"background-color: {self.current_text_color}; color: {self.get_contrasting_text_color(self.current_text_color)}; font-weight: bold;")
        self.text_color_btn.clicked.connect(self.select_text_color)
        layout.addWidget(self.text_color_btn, 0, 1)

        layout.addWidget(QLabel("Цвет обводки:"), 1, 0)
        self.stroke_color_btn = QPushButton(self.current_stroke_color)
        self.stroke_color_btn.setStyleSheet(f"background-color: {self.current_stroke_color}; color: {self.get_contrasting_text_color(self.current_stroke_color)}; font-weight: bold;")
        self.stroke_color_btn.clicked.connect(self.select_stroke_color)
        layout.addWidget(self.stroke_color_btn, 1, 1)

        layout.addWidget(QLabel("Толщина обводки:"), 2, 0)
        self.stroke_width_input = QSpinBox()
        self.stroke_width_input.setRange(0, 10)
        self.stroke_width_input.setValue(self.default_settings['stroke_width'])
        layout.addWidget(self.stroke_width_input, 2, 1)

        layout.addWidget(QLabel("Размер заголовка:"), 3, 0)
        self.title_size_input = QSpinBox()
        self.title_size_input.setRange(10, 100)
        self.title_size_input.setValue(self.default_settings['title_size'])
        layout.addWidget(self.title_size_input, 3, 1)

        layout.addWidget(QLabel("Размер субтитров:"), 4, 0)
        self.subtitle_size_input = QSpinBox()
        self.subtitle_size_input.setRange(8, 80)
        self.subtitle_size_input.setValue(self.default_settings['subtitle_size'])
        layout.addWidget(self.subtitle_size_input, 4, 1)
        
        effects_label = QLabel("Эффекты:")
        layout.addWidget(effects_label, 5, 0, 1, 2, Qt.AlignmentFlag.AlignCenter) 

        self.typewriter_checkbox = QCheckBox("Печатная машинка")
        self.typewriter_checkbox.setChecked(self.default_settings['effects'].get('typewriter', False))
        layout.addWidget(self.typewriter_checkbox, 6, 0)

        self.fade_checkbox = QCheckBox("Появление/исчезание")
        self.fade_checkbox.setChecked(self.default_settings['effects'].get('fade', False))
        layout.addWidget(self.fade_checkbox, 6, 1)
        
        layout.setColumnStretch(1, 1)
        return group

    def create_settings_group(self):
        logger.debug("Создание группы 'Настройки видео' (с FPS, Качеством и Кодеком)")
        group = QGroupBox("📐 Настройки видео")
        layout = QGridLayout(group)
        
        layout.addWidget(QLabel("Разрешение:"), 0, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["1920×1080 (Альбомное)", "1080×1920 (Вертикальное)"])
        layout.addWidget(self.resolution_combo, 0, 1)
        
        layout.addWidget(QLabel("Длительность (сек):"), 1, 0)
        self.duration_input = QSpinBox() 
        self.duration_input.setRange(5, 7200) 
        self.duration_input.setValue(self.default_settings['duration'])
        layout.addWidget(self.duration_input, 1, 1)

        layout.addWidget(QLabel("FPS:"), 2, 0)
        self.fps_combo = QComboBox()
        self.fps_options = ["24", "30", "60"]
        self.fps_combo.addItems(self.fps_options)
        default_fps_str = str(self.default_settings.get('fps', 30))
        if self.fps_combo.findText(default_fps_str) != -1:
            self.fps_combo.setCurrentText(default_fps_str)
        layout.addWidget(self.fps_combo, 2, 1)

        layout.addWidget(QLabel("Качество видео:"), 3, 0)
        self.video_quality_combo = QComboBox()
        self.quality_options = {"low": "Низкое (быстро)", "medium": "Среднее (баланс)", "high": "Высокое (медленно)"}
        self.video_quality_combo.addItems(list(self.quality_options.values()))
        default_quality_key = self.default_settings.get('video_quality', "medium")
        default_quality_display = self.quality_options.get(default_quality_key, "Среднее (баланс)")
        if self.video_quality_combo.findText(default_quality_display) != -1:
            self.video_quality_combo.setCurrentText(default_quality_display)
        layout.addWidget(self.video_quality_combo, 3, 1)

        layout.addWidget(QLabel("Кодек:"), 4, 0)
        self.codec_combo = QComboBox()
        self.codec_options = {"libx264": "H.264 (стандарт)", "libx265": "H.265 (эффективный)"}
        self.codec_combo.addItems(list(self.codec_options.values()))
        default_codec_key = self.default_settings.get('codec_name', "libx264")
        default_codec_display = self.codec_options.get(default_codec_key, "H.264 (стандарт)")
        if self.codec_combo.findText(default_codec_display) != -1:
            self.codec_combo.setCurrentText(default_codec_display)
        layout.addWidget(self.codec_combo, 4, 1)
        
        layout.setColumnStretch(1, 1)
        return group

    def create_preview_group(self):
        logger.debug("Создание группы 'Превью и создание'")
        group = QGroupBox("👁️ Превью и создание")
        layout = QVBoxLayout(group)
        
        self.preview_label = QLabel("Загрузите изображение для превью")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(150)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding) 
        self.preview_label.setStyleSheet("QLabel { border: 2px dashed #bdc3c7; border-radius: 10px; background-color: #ecf0f1; color: #444444; }")
        layout.addWidget(self.preview_label)
        
        self.create_btn = QPushButton("🚀 Создать видео")
        self.create_btn.setStyleSheet("QPushButton { background-color: #e74c3c; font-size: 16px; padding: 15px; } QPushButton:hover { background-color: #c0392b; } QPushButton:disabled { background-color: #95a5a6; }")
        self.create_btn.clicked.connect(self.create_video)
        layout.addWidget(self.create_btn)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("QLabel { color: #2c3e50; font-weight: normal; }")
        layout.addWidget(self.status_label)
        return group

    def create_templates_tab(self):
        logger.info("Создание вкладки 'Шаблоны'")
        tab = QWidget()
        main_layout = QHBoxLayout(tab)

        list_group = QGroupBox("Сохраненные шаблоны")
        list_layout = QVBoxLayout(list_group)
        
        self.templates_list_widget = QListWidget()
        self.templates_list_widget.itemDoubleClicked.connect(self.load_template_ui)
        list_layout.addWidget(self.templates_list_widget)
        
        main_layout.addWidget(list_group, 2)

        controls_group = QGroupBox("Управление")
        controls_layout = QVBoxLayout(controls_group)

        controls_layout.addWidget(QLabel("Имя нового шаблона:"))
        self.template_name_input = QLineEdit()
        self.template_name_input.setPlaceholderText("Введите имя для сохранения...")
        controls_layout.addWidget(self.template_name_input)

        self.save_template_btn = QPushButton("💾 Сохранить текущий шаблон")
        self.save_template_btn.clicked.connect(self.save_template_ui)
        controls_layout.addWidget(self.save_template_btn)
        
        controls_layout.addSpacing(20)

        self.load_template_btn = QPushButton("📂 Загрузить выбранный")
        self.load_template_btn.clicked.connect(self.load_template_ui)
        controls_layout.addWidget(self.load_template_btn)

        self.delete_template_btn = QPushButton("🗑️ Удалить выбранный")
        self.delete_template_btn.clicked.connect(self.delete_template_ui)
        self.delete_template_btn.setStyleSheet("QPushButton { background-color: #e74c3c; } QPushButton:hover { background-color: #c0392b; }")
        
        controls_layout.addWidget(self.delete_template_btn)
        
        controls_layout.addStretch()
        main_layout.addWidget(controls_group, 1)

        self.tab_widget.addTab(tab, "📝 Шаблоны")
        self.populate_templates_list()
        logger.debug("Вкладка 'Шаблоны' создана и заполнена.")

    # Google Sheets методы (только если доступны)
    def refresh_themes_list(self):
        """Обновить список тем из Google Sheets"""
        if not GOOGLE_SHEETS_AVAILABLE:
            logger.warning("Google Sheets недоступны, обновление списка тем пропущено")
            return
            
        logger.info("Обновление списка тем из Google Sheets...")
        try:
            themes = get_available_themes(
                self.SERVICE_ACCOUNT_FILE,
                self.GOOGLE_SHEET_ID,
                self.SHEET_NAME
            )
            
            self.theme_combo.clear()
            if themes:
                self.theme_combo.addItems(themes)
                logger.info(f"Загружено {len(themes)} тем из Google Sheets")
            else:
                logger.warning("Не удалось загрузить темы из Google Sheets")
                QMessageBox.warning(self, "Предупреждение", "Не удалось загрузить список тем из Google Sheets")
                
        except Exception as e:
            logger.error(f"Ошибка при обновлении списка тем: {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Ошибка при обновлении списка тем:\n{str(e)}")

    def load_project_by_theme(self):
        """Загрузить проект по выбранной теме"""
        if not GOOGLE_SHEETS_AVAILABLE:
            QMessageBox.warning(self, "Ошибка", "Google Sheets интеграция недоступна")
            return
            
        selected_theme = self.theme_combo.currentText()
        if not selected_theme:
            QMessageBox.warning(self, "Ошибка", "Выберите тему из списка")
            return
            
        logger.info(f"Загрузка проекта для темы: {selected_theme}")
        
        try:
            from google_sheets_manager import load_theme_project
            
            project_data = load_theme_project(
                selected_theme,
                self.SERVICE_ACCOUNT_FILE,
                self.GOOGLE_SHEET_ID,
                self.SHEET_NAME,
                self.AUDIO_OUTPUT_FOLDER
            )
            
            if not project_data['success']:
                error_msg = f"Не удалось загрузить проект для темы '{selected_theme}':\n"
                error_msg += "\n".join(project_data['errors'])
                QMessageBox.critical(self, "Ошибка загрузки", error_msg)
                return
            
            # Применяем загруженные данные
            text_data = project_data['text_data']
            if text_data:
                self.title_input.setText(text_data['title'])
                self.subtitle_input.setPlainText(text_data['text'])
                logger.info(f"Загружены текстовые данные для темы '{selected_theme}'")
            
            # Загружаем аудио
            audio_path = project_data['audio_path']
            if audio_path:
                try:
                    # Проверяем, не добавлен ли уже этот аудиофайл
                    if not any(track["path"] == audio_path for track in self.audio_tracks_info):
                        audio_clip_temp = AudioFileClip(audio_path)
                        duration = audio_clip_temp.duration
                        audio_clip_temp.close()
                        
                        track_info = {"path": audio_path, "start_time": 0.0, "duration": duration, "item": None}
                        self.audio_tracks_info.append(track_info)
                        
                        # Устанавливаем длительность видео равной длительности аудио
                        self.duration_input.setValue(int(duration))
                        
                        self._redraw_audio_timeline()
                        self._update_audio_tracks_info_label()
                        
                        logger.info(f"Загружен аудиофайл: {Path(audio_path).name}, длительность: {duration:.2f} сек")
                    else:
                        logger.info(f"Аудиофайл {audio_path} уже был добавлен ранее")
                        
                except Exception as e:
                    logger.error(f"Ошибка при загрузке аудиофайла {audio_path}: {e}", exc_info=True)
                    QMessageBox.warning(self, "Ошибка аудио", f"Не удалось загрузить аудиофайл:\n{str(e)}")
            
            # Загружаем шаблон (если есть)
            template_path = project_data['template_path']
            if template_path:
                try:
                    import json
                    with open(template_path, 'r', encoding='utf-8') as f:
                        template_settings = json.load(f)
                    self._apply_settings_to_ui(template_settings)
                    logger.info(f"Применен шаблон: {Path(template_path).name}")
                except Exception as e:
                    logger.error(f"Ошибка при загрузке шаблона {template_path}: {e}", exc_info=True)
                    # Это не критичная ошибка, продолжаем
            
            QMessageBox.information(self, "Успех", 
                f"Проект для темы '{selected_theme}' успешно загружен!\n\n"
                f"✓ Текстовые данные: {len(text_data['text']) if text_data else 0} символов\n"
                f"✓ Аудиофайл: {'Да' if audio_path else 'Нет'}\n"
                f"✓ Шаблон: {'Да' if template_path else 'Используется текущий'}")
                
        except Exception as e:
            logger.error(f"Ошибка при загрузке проекта для темы '{selected_theme}': {e}", exc_info=True)
            QMessageBox.critical(self, "Ошибка", f"Ошибка при загрузке проекта:\n{str(e)}")

    # Остальные методы без изменений
    def _connect_duration_input_signal(self):
        if hasattr(self, 'duration_input') and self.duration_input:
            try:
                self.duration_input.valueChanged.disconnect(self._redraw_audio_timeline)
            except TypeError: 
                pass
            self.duration_input.valueChanged.connect(self._redraw_audio_timeline)
            logger.debug("Сигнал duration_input.valueChanged подключен к _redraw_audio_timeline.")
        else:
            logger.warning("duration_input не найден для подключения сигнала valueChanged. Повторная попытка через QTimer.")
            QTimer.singleShot(100, self._connect_duration_input_signal)

    def _calculate_timeline_scale(self) -> Tuple[float, float]:
        if not hasattr(self, 'duration_input') or not self.duration_input or \
           not hasattr(self, 'audio_timeline_view') or not self.audio_timeline_view.viewport():
            logger.warning("_calculate_timeline_scale: UI не полностью инициализирован. Дефолтные значения.")
            return 10.0, 600.0 

        total_video_duration = float(self.duration_input.value())
        if total_video_duration <= 0:
            total_video_duration = 60.0 

        viewport_width = self.audio_timeline_view.viewport().width()
        available_width = viewport_width - (2 * TIMELINE_MARGIN) 
        
        if available_width < 50 : 
            available_width = 50 
        
        pixels_per_second = available_width / total_video_duration
        return pixels_per_second, available_width

    def _draw_time_ruler(self):
        for item in self.ruler_items: 
            if item.scene() == self.audio_scene: self.audio_scene.removeItem(item)
        self.ruler_items.clear()

        if not hasattr(self, 'duration_input'): 
            return

        pixels_per_second, timeline_content_width = self._calculate_timeline_scale()
        total_duration = float(self.duration_input.value())
        if total_duration <= 0 or pixels_per_second <= 0: 
            logger.warning(f"Невозможно нарисовать линейку: total_duration={total_duration}, px_per_sec={pixels_per_second}")
            return

        ruler_y_offset = 5 
        line_y = ruler_y_offset + RULER_HEIGHT / 2
        
        main_line = QGraphicsLineItem(TIMELINE_MARGIN, line_y, TIMELINE_MARGIN + timeline_content_width, line_y)
        main_line.setPen(QPen(Qt.GlobalColor.darkGray, 1))
        self.audio_scene.addItem(main_line)
        self.ruler_items.append(main_line)

        major_tick_interval_seconds = 5
        if total_duration > 120: major_tick_interval_seconds = 30
        elif total_duration > 60: major_tick_interval_seconds = 10
        elif total_duration < 10 and total_duration > 0 : major_tick_interval_seconds = 1
        elif total_duration == 0 : return 
        
        for i in range(int(total_duration / major_tick_interval_seconds) + 2) : 
            sec = i * major_tick_interval_seconds
            if sec > total_duration + major_tick_interval_seconds: break 
                
            x_pos = TIMELINE_MARGIN + sec * pixels_per_second
            
            if x_pos > TIMELINE_MARGIN + timeline_content_width + 5 : continue 

            tick_line = QGraphicsLineItem(x_pos, ruler_y_offset, x_pos, ruler_y_offset + RULER_HEIGHT * 0.75)
            tick_line.setPen(QPen(Qt.GlobalColor.darkGray, 1))
            self.audio_scene.addItem(tick_line)
            self.ruler_items.append(tick_line)

            label = QGraphicsSimpleTextItem(f"{int(sec)}s")
            font = QFont()
            font.setPointSize(7)
            label.setFont(font)
            label.setPos(x_pos - label.boundingRect().width() / 2, ruler_y_offset - label.boundingRect().height() -1)
            self.audio_scene.addItem(label)
            self.ruler_items.append(label)
            
            if major_tick_interval_seconds >= 5:
                minor_interval = 1
                if major_tick_interval_seconds > 10: minor_interval = major_tick_interval_seconds // 5

                for j in range(1, int(major_tick_interval_seconds / minor_interval)):
                    minor_sec_offset = j * minor_interval
                    if sec + minor_sec_offset > total_duration + 0.1 and sec + minor_sec_offset > i * major_tick_interval_seconds + major_tick_interval_seconds : break
                    if sec + minor_sec_offset > total_duration + major_tick_interval_seconds: continue

                    minor_x_pos = TIMELINE_MARGIN + (sec + minor_sec_offset) * pixels_per_second
                    if minor_x_pos > TIMELINE_MARGIN + timeline_content_width + 5 : continue 
                    
                    minor_tick_line = QGraphicsLineItem(minor_x_pos, ruler_y_offset + RULER_HEIGHT * 0.25, minor_x_pos, ruler_y_offset + RULER_HEIGHT * 0.5)
                    minor_tick_line.setPen(QPen(Qt.GlobalColor.gray, 1))
                    self.audio_scene.addItem(minor_tick_line)
                    self.ruler_items.append(minor_tick_line)
        logger.debug("Временная линейка нарисована.")

    def _generate_simplified_waveform_data(self, audio_path: str, target_item_width: float, target_item_height: float) -> List[Tuple[float, float, float, float]]:
        """Генерирует упрощенные данные формы волны для отображения."""
        waveform_points = []
        if not Path(audio_path).exists() or target_item_width <= 0:
            return waveform_points

        try:
            waveform_sample_rate = 4000 # Например, 4kHz
            
            with AudioFileClip(audio_path) as audio_clip:
                sound_array = audio_clip.to_soundarray(fps=waveform_sample_rate)

            if sound_array.ndim == 2: # Стерео -> Моно (берем среднее или один канал)
                sound_array = sound_array.mean(axis=1)
            
            num_frames = len(sound_array)
            if num_frames == 0: return waveform_points

            # Сколько аудиокадров приходится на один горизонтальный пиксель нашего блока
            frames_per_pixel = num_frames / target_item_width
            if frames_per_pixel <=0 : frames_per_pixel = 1 # Защита от деления на ноль, если target_item_width мал

            # Максимальная высота для отображения волны (чуть меньше высоты трека)
            drawable_height = target_item_height * 0.8 # 80% высоты трека для волны
            half_drawable_height = drawable_height / 2

            for i in range(int(target_item_width)):
                start_frame = int(i * frames_per_pixel)
                end_frame = int((i + 1) * frames_per_pixel)
                if start_frame >= num_frames: break
                end_frame = min(end_frame, num_frames)
                
                if start_frame == end_frame: # Если сегмент пуст или слишком мал
                    if start_frame < num_frames:
                        peak_amplitude = abs(sound_array[start_frame])
                    else: continue
                else:
                    segment = sound_array[start_frame:end_frame]
                    peak_amplitude = np.max(np.abs(segment)) if len(segment) > 0 else 0
                
                # Масштабируем амплитуду к высоте отрисовки
                # Амплитуды в sound_array обычно в диапазоне [-1.0, 1.0]
                line_height = peak_amplitude * half_drawable_height
                
                # Координаты для вертикальной линии (относительно 0,0 элемента AudioTrackItem)
                # x, y_top_relative_to_center, x, y_bottom_relative_to_center
                waveform_points.append((float(i), line_height, float(i), line_height))
            
            logger.debug(f"Сгенерировано {len(waveform_points)} точек для волны '{Path(audio_path).name}'.")

        except Exception as e:
            logger.error(f"Ошибка генерации формы волны для {audio_path}: {e}", exc_info=True)
        
        return waveform_points

    def _add_audio_item_to_timeline(self, track_info: Dict[str, Any]):
        logger.info(f"Добавление аудио '{track_info['path']}' на таймлайн. Y={self.next_audio_track_y}")
        
        audio_path = track_info["path"]
        start_time = float(track_info.get("start_time", 0.0))
        audio_actual_duration = float(track_info.get("duration", 10.0))

        pixels_per_second, _ = self._calculate_timeline_scale() 

        rect_x = TIMELINE_MARGIN + start_time * pixels_per_second 
        rect_width = audio_actual_duration * pixels_per_second
        
        track_colors = [QColor("#5DADE2"), QColor("#48C9B0"), QColor("#F7DC6F"), QColor("#EB984E"), QColor("#AF7AC5")]
        # Используем индекс для стабильного цвета при перерисовках
        idx_for_color = next((i for i, t in enumerate(self.audio_tracks_info) if t["path"] == audio_path), 0)
        item_color = track_colors[idx_for_color % len(track_colors)]
        display_name = Path(audio_path).name

        audio_item = AudioTrackItem(
            track_info, display_name, 
            rect_x, self.next_audio_track_y, rect_width, AUDIO_TRACK_HEIGHT, 
            item_color, self 
        )
        
        # Генерация и установка данных формы волны
        if rect_width > 0: # Генерируем волну, только если есть ширина
            waveform_data = self._generate_simplified_waveform_data(audio_path, rect_width, AUDIO_TRACK_HEIGHT)
            if waveform_data:
                audio_item.set_waveform_data(waveform_data)
        
        self.audio_scene.addItem(audio_item)
        track_info["item"] = audio_item 
        
        logger.debug(f"Аудио элемент для '{display_name}' добавлен на сцену: x={rect_x:.2f}, y={self.next_audio_track_y}, w={rect_width:.2f}, h={AUDIO_TRACK_HEIGHT}")

    def _redraw_audio_timeline(self):
        if not hasattr(self, 'audio_scene') or not hasattr(self, 'duration_input'):
            logger.debug("_redraw_audio_timeline вызван до полной инициализации, отложено.")
            QTimer.singleShot(10, self._redraw_audio_timeline) 
            return
            
        logger.info("Перерисовка таймлайна аудио...")
        
        for item in self.ruler_items:
            if item.scene() == self.audio_scene: self.audio_scene.removeItem(item)
        self.ruler_items.clear()

        old_audio_items = []
        for track_info in self.audio_tracks_info:
            if "item" in track_info and track_info["item"] is not None:
                old_audio_items.append(track_info["item"])
                track_info["item"] = None 
        
        for item in old_audio_items:
             if item.scene() == self.audio_scene:
                self.audio_scene.removeItem(item)
        
        self._draw_time_ruler() 

        self.next_audio_track_y = AUDIO_TRACK_BASE_Y 
        for track_info in self.audio_tracks_info:
            track_info["start_time"] = float(track_info.get("start_time", 0.0))
            track_info["duration"] = float(track_info.get("duration", 10.0))
            self._add_audio_item_to_timeline(track_info) 
            self.next_audio_track_y += AUDIO_TRACK_HEIGHT + AUDIO_TRACK_SPACING

        _, timeline_content_width = self._calculate_timeline_scale()
        scene_width = timeline_content_width + 2 * TIMELINE_MARGIN
        scene_height = self.next_audio_track_y + AUDIO_TRACK_HEIGHT + TIMELINE_MARGIN 
        self.audio_scene.setSceneRect(0, 0, scene_width, max(self.audio_timeline_view.minimumHeight() - 2*self.audio_timeline_view.frameWidth() , scene_height))
        logger.info(f"Таймлайн аудио перерисован. SceneRect: 0,0,{scene_width:.0f},{self.audio_scene.sceneRect().height():.0f}")

    def update_audio_track_start_time(self, audio_path: str, new_start_time: float):
        updated = False
        for track in self.audio_tracks_info:
            if track["path"] == audio_path:
                track["start_time"] = new_start_time
                logger.info(f"Обновлен start_time для '{Path(audio_path).name}' на {new_start_time:.2f} в self.audio_tracks_info.")
                updated = True
                break
        if not updated:
            logger.warning(f"Не удалось найти трек с путем '{audio_path}' для обновления start_time.")
        
    def _handle_track_delete_request(self, audio_path_to_remove: str):
        logger.info(f"Получен запрос на удаление аудиодорожки с таймлайна: {audio_path_to_remove}")
        
        track_to_remove_index = -1
        for i, track in enumerate(self.audio_tracks_info):
            if track["path"] == audio_path_to_remove:
                track_to_remove_index = i
                break
        
        if track_to_remove_index != -1:
            track_to_remove = self.audio_tracks_info.pop(track_to_remove_index) 
            if "item" in track_to_remove and track_to_remove["item"] is not None:
                if track_to_remove["item"].scene() == self.audio_scene:
                    self.audio_scene.removeItem(track_to_remove["item"])
            
            logger.info(f"Аудиодорожка {audio_path_to_remove} удалена из списка self.audio_tracks_info.")
            self._redraw_audio_timeline() 
            self._update_audio_tracks_info_label()
        else:
            logger.warning(f"Не удалось найти трек для удаления с путем: {audio_path_to_remove}")

    def _update_audio_tracks_info_label(self):
        if self.audio_tracks_info:
            self.audio_tracks_info_label.setText(f"Загружено аудиодорожек: {len(self.audio_tracks_info)}")
            self.audio_tracks_info_label.setProperty("status", "loaded")
        else:
            self.audio_tracks_info_label.setText("Аудио не добавлено")
            self.audio_tracks_info_label.setProperty("status", "unloaded")
        if hasattr(self, 'audio_tracks_info_label') and self.audio_tracks_info_label:
            self.style().unpolish(self.audio_tracks_info_label)
            self.style().polish(self.audio_tracks_info_label)

    def populate_templates_list(self):
        logger.info("Обновление списка сохраненных шаблонов...")
        self.templates_list_widget.clear()
        templates = template_manager.get_saved_templates()
        logger.debug(f"Получено {len(templates)} шаблонов от менеджера.")
        for t_info in templates:
            item = QListWidgetItem(t_info["display_name"])
            item.setData(Qt.ItemDataRole.UserRole, t_info["filename_stem"])
            self.templates_list_widget.addItem(item)
        logger.info(f"Список шаблонов в UI обновлен. Количество: {self.templates_list_widget.count()}.")

    def _gather_current_settings_from_ui(self) -> dict:
        logger.debug("Сбор текущих настроек из UI...")
        
        selected_quality_display = self.video_quality_combo.currentText()
        video_quality_key = next((k for k, v in self.quality_options.items() if v == selected_quality_display), "medium")
        
        selected_codec_display = self.codec_combo.currentText()
        codec_key = next((k for k, v in self.codec_options.items() if v == selected_codec_display), "libx264")
        
        settings = {
            "image_paths": self.image_paths, 
            "audio_tracks_info": self.audio_tracks_info, 
            "font_path": self.font_path,
            "resolution": self.get_resolution(), "duration": self.duration_input.value(),
            "title_text": self.title_input.text(), "subtitle_text": self.subtitle_input.toPlainText(),
            "text_color": self.current_text_color, "stroke_color": self.current_stroke_color,
            "stroke_width": self.stroke_width_input.value(), "title_size": self.title_size_input.value(),
            "subtitle_size": self.subtitle_size_input.value(),
            "effects": {'typewriter': self.typewriter_checkbox.isChecked(), 'fade': self.fade_checkbox.isChecked()},
            "fps": int(self.fps_combo.currentText()), 
            "video_quality": video_quality_key,
            "codec_name": codec_key 
        }
        logger.info("Текущие настройки из UI успешно собраны.")
        logger.debug(f"Собранные настройки (audio_tracks_info): {[{k: v for k, v in t.items() if k != 'item'} for t in settings['audio_tracks_info']]}") 
        return settings

    def _apply_settings_to_ui(self, settings: dict):
        template_name = settings.get('name', 'Неизвестный')
        logger.info(f"Применение настроек из шаблона '{template_name}' в UI...")
        logger.debug(f"Полные настройки из шаблона: {settings}")

        self.image_paths = settings.get("image_paths", [])
        if self.image_paths:
            self.images_label.setText(f"Загружено изображений: {len(self.image_paths)}")
            self.images_label.setProperty("status", "loaded")
            if self.image_paths and Path(self.image_paths[0]).exists():
                 self.show_preview(self.image_paths[0])
            else:
                 self.preview_label.setText("Файл из шаблона не найден")
        else:
            self.images_label.setText("Изображения не загружены")
            self.images_label.setProperty("status", "unloaded")
            self.preview_label.setText("Загрузите изображение для превью")
        if hasattr(self, 'images_label') and self.images_label:
            self.style().unpolish(self.images_label); self.style().polish(self.images_label)
        
        self.audio_tracks_info = [] 
        loaded_audio_tracks = settings.get("audio_tracks_info", [])
        logger.debug(f"Загрузка аудиодорожек из шаблона: {loaded_audio_tracks}")
        
        for track_data in loaded_audio_tracks:
            path = track_data.get("path")
            start_time = float(track_data.get("start_time", 0.0))
            duration = float(track_data.get("duration", 0.0)) 
            
            if not path or not isinstance(path, str):
                logger.warning(f"Пропуск аудиодорожки из шаблона: неверный путь {path}")
                continue

            if duration <= 0: 
                logger.warning(f"Длительность для {path} не указана в шаблоне или некорректна, пытаемся получить из файла.")
                try:
                    audio_clip = AudioFileClip(path)
                    duration = audio_clip.duration
                    audio_clip.close()
                    logger.info(f"Получена длительность {duration} сек для {path} из файла.")
                except Exception as e:
                    logger.error(f"Не удалось получить длительность для {path} из файла: {e}. Используется дефолтная 10 сек.")
                    duration = 10.0 

            new_track_info = {"path": path, "start_time": start_time, "duration": duration, "item": None}
            self.audio_tracks_info.append(new_track_info)
        
        self.duration_input.setValue(settings.get("duration", self.default_settings['duration']))
        self._redraw_audio_timeline() 
        self._update_audio_tracks_info_label()

        self.font_path = settings.get("font_path", None)
        if self.font_path and Path(self.font_path).exists():
            self.font_label.setText(f"Шрифт: {Path(self.font_path).name}")
            self.font_label.setProperty("status", "loaded")
        else:
            if self.font_path: QMessageBox.warning(self, "Внимание", f"Файл шрифта '{self.font_path}' из шаблона не найден.")
            self.font_path = None
            self.font_label.setText("Стандартный шрифт")
            self.font_label.setProperty("status", "unloaded")
        if hasattr(self, 'font_label') and self.font_label:
             self.style().unpolish(self.font_label); self.style().polish(self.font_label)
        
        res = settings.get("resolution", self.default_settings['resolution'])
        res_str_portrait = "1080×1920 (Вертикальное)"
        res_str_landscape = "1920×1080 (Альбомное)"
        target_res_str = res_str_portrait if res[0] == 1080 and res[1] == 1920 else res_str_landscape
        if self.resolution_combo.findText(target_res_str) != -1:
            self.resolution_combo.setCurrentText(target_res_str)
        
        self.title_input.setText(settings.get("title_text", ""))
        self.subtitle_input.setPlainText(settings.get("subtitle_text", ""))

        self.current_text_color = settings.get("text_color", self.default_settings['text_color'])
        self.text_color_btn.setText(self.current_text_color)
        self.text_color_btn.setStyleSheet(f"background-color: {self.current_text_color}; color: {self.get_contrasting_text_color(self.current_text_color)}; font-weight: bold;")

        self.current_stroke_color = settings.get("stroke_color", self.default_settings['stroke_color'])
        self.stroke_color_btn.setText(self.current_stroke_color)
        self.stroke_color_btn.setStyleSheet(f"background-color: {self.current_stroke_color}; color: {self.get_contrasting_text_color(self.current_stroke_color)}; font-weight: bold;")

        self.stroke_width_input.setValue(settings.get("stroke_width", self.default_settings['stroke_width']))
        self.title_size_input.setValue(settings.get("title_size", self.default_settings['title_size']))
        self.subtitle_size_input.setValue(settings.get("subtitle_size", self.default_settings['subtitle_size']))

        effects = settings.get("effects", self.default_settings['effects'])
        self.typewriter_checkbox.setChecked(effects.get('typewriter', False))
        self.fade_checkbox.setChecked(effects.get('fade', False))

        loaded_fps_str = str(settings.get("fps", self.default_settings['fps']))
        if self.fps_combo.findText(loaded_fps_str) != -1:
            self.fps_combo.setCurrentText(loaded_fps_str)
        
        loaded_quality_key = settings.get("video_quality", self.default_settings['video_quality'])
        loaded_quality_display = self.quality_options.get(loaded_quality_key, "Среднее (баланс)")
        if self.video_quality_combo.findText(loaded_quality_display) != -1:
            self.video_quality_combo.setCurrentText(loaded_quality_display)

        loaded_codec_key = settings.get("codec_name", self.default_settings['codec_name'])
        loaded_codec_display = self.codec_options.get(loaded_codec_key, "H.264 (стандарт)")
        if self.codec_combo.findText(loaded_codec_display) != -1:
            self.codec_combo.setCurrentText(loaded_codec_display)
        
        logger.info(f"Настройки из шаблона '{template_name}' успешно применены к UI.")

    # Методы для работы с файлами и UI
    def load_images(self):
        logger.info("Открытие диалога выбора изображений...")
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите изображения", "", "Изображения (*.jpg *.jpeg *.png *.bmp)")
        if files:
            self.image_paths = files
            logger.info(f"Загружено изображений: {len(files)}. Пути: {self.image_paths}")
            self.images_label.setText(f"Загружено изображений: {len(files)}")
            self.images_label.setProperty("status", "loaded") 
            if self.image_paths and Path(self.image_paths[0]).exists():
                self.show_preview(self.image_paths[0])
            else:
                logger.warning(f"Первый файл изображения '{self.image_paths[0] if self.image_paths else 'N/A'}' не найден для превью.")
                self.preview_label.setText("Файл превью не найден")
                self.preview_label.setStyleSheet("QLabel { border: 2px dashed #bdc3c7; border-radius: 10px; background-color: #ecf0f1; color: red; }")
        else: 
            logger.info("Загрузка изображений отменена или файлы не выбраны.")
            if not self.image_paths: 
                self.images_label.setText("Изображения не загружены")
                self.images_label.setProperty("status", "unloaded") 
                self.preview_label.setText("Загрузите изображение для превью")
                self.preview_label.setStyleSheet("QLabel { border: 2px dashed #bdc3c7; border-radius: 10px; background-color: #ecf0f1; color: #444444; }") 
        if hasattr(self, 'images_label') and self.images_label:
            self.style().unpolish(self.images_label); self.style().polish(self.images_label)

    def load_audio(self):
        logger.info("Открытие диалога добавления аудиофайлов...")
        files, _ = QFileDialog.getOpenFileNames(
            self, "Выберите аудиодорожки для добавления", "", "Аудио (*.mp3 *.wav *.m4a *.aac)"
        )
        
        if files:
            newly_added_count = 0
            for file_path_str in files:
                if not any(track["path"] == file_path_str for track in self.audio_tracks_info):
                    try:
                        audio_clip_temp = AudioFileClip(file_path_str)
                        duration = audio_clip_temp.duration
                        audio_clip_temp.close()
                        logger.info(f"Аудиофайл '{file_path_str}' длительностью {duration:.2f} сек.")
                    except Exception as e:
                        logger.error(f"Не удалось прочитать длительность аудиофайла {file_path_str}: {e}", exc_info=True)
                        QMessageBox.warning(self, "Ошибка аудио", f"Не удалось обработать аудиофайл: {Path(file_path_str).name}\n{e}")
                        continue 

                    track_info = {"path": file_path_str, "start_time": 0.0, "duration": duration, "item": None}
                    self.audio_tracks_info.append(track_info)
                    newly_added_count +=1
                else:
                    logger.warning(f"Аудиодорожка {file_path_str} уже была добавлена ранее.")
            
            if newly_added_count > 0:
                self._redraw_audio_timeline() 
                QMessageBox.information(self, "Аудио добавлено", f"Добавлено новых аудиодорожек: {newly_added_count}.")
            elif files: 
                QMessageBox.information(self, "Информация", "Все выбранные аудиодорожки уже были добавлены ранее.")
            self._update_audio_tracks_info_label()
        else:
            logger.info("Добавление аудиофайлов отменено или файлы не выбраны.")

    def load_font(self):
        logger.info("Открытие диалога выбора файла шрифта...")
        file, _ = QFileDialog.getOpenFileName(
            self, "Выберите шрифт", "", "Шрифты (*.ttf *.otf)"
        )
        if file:
            self.font_path = file
            font_name = Path(file).name
            logger.info(f"Загружен шрифт: '{font_name}'. Путь: {self.font_path}")
            self.font_label.setText(f"Шрифт: {font_name}")
            self.font_label.setProperty("status", "loaded")
        else:
            logger.info("Загрузка шрифта отменена или файл не выбран.")
            if not self.font_path:
                self.font_label.setText("Стандартный шрифт")
                self.font_label.setProperty("status", "unloaded")
        
        if hasattr(self, 'font_label') and self.font_label:
            self.style().unpolish(self.font_label)
            self.style().polish(self.font_label)

    def show_preview(self, image_path_str: str):
        logger.debug(f"Попытка показать превью для: '{image_path_str}'")
        try:
            image_path = Path(image_path_str) 
            if not image_path.exists():
                logger.warning(f"Файл для превью не существует: '{image_path_str}'")
                self.preview_label.setText("Файл превью не найден")
                self.preview_label.setStyleSheet("QLabel { border: 2px dashed #bdc3c7; border-radius: 10px; background-color: #ecf0f1; color: red; }")
                return

            pixmap = QPixmap(image_path_str)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    self.preview_label.width() - 10, 
                    self.preview_label.height() - 10,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.preview_label.setPixmap(scaled_pixmap)
                self.preview_label.setStyleSheet("QLabel { border: none; }") 
                logger.debug(f"Превью для '{image_path_str}' успешно отображено.")
            else: 
                logger.warning(f"Не удалось загрузить QPixmap для превью (не изображение?): '{image_path_str}'")
                self.preview_label.setText("Не удалось загрузить превью (не изображение?)")
                self.preview_label.setStyleSheet("QLabel { border: 2px dashed #bdc3c7; border-radius: 10px; background-color: #ecf0f1; color: red; }")

        except Exception as e:
            logger.error(f"Ошибка при отображении превью для '{image_path_str}': {e}", exc_info=True)
            self.preview_label.setText("Ошибка превью")
            self.preview_label.setStyleSheet("QLabel { border: 2px dashed #bdc3c7; border-radius: 10px; background-color: #ecf0f1; color: red; }")

    def get_resolution(self):
        resolution_text = self.resolution_combo.currentText()
        return (1080, 1920) if "1080×1920" in resolution_text else (1920, 1080)

    # Методы для работы с цветами
    def select_stroke_color(self):
        logger.debug("Вызов диалога выбора цвета обводки.")
        initial_color = QColor(self.current_stroke_color) if QColor.isValidColor(self.current_stroke_color) else Qt.GlobalColor.black
        
        color = QColorDialog.getColor(initial_color, self, "Выберите цвет обводки")
        
        if color.isValid():
            logger.info(f"Выбран новый цвет обводки: {color.name()}")
            self.current_stroke_color = color.name()
            self.stroke_color_btn.setText(self.current_stroke_color)
            self.stroke_color_btn.setStyleSheet(
                f"background-color: {self.current_stroke_color}; "
                f"color: {self.get_contrasting_text_color(self.current_stroke_color)}; "
                f"font-weight: bold;"
            )
        else:
            logger.debug("Выбор цвета обводки отменен.")

    def select_text_color(self):
        logger.debug("Вызов диалога выбора цвета текста.")
        initial_color = QColor(self.current_text_color) if QColor.isValidColor(self.current_text_color) else Qt.GlobalColor.white
        
        color = QColorDialog.getColor(initial_color, self, "Выберите цвет текста")
        
        if color.isValid():
            logger.info(f"Выбран новый цвет текста: {color.name()}")
            self.current_text_color = color.name()
            self.text_color_btn.setText(self.current_text_color)
            self.text_color_btn.setStyleSheet(
                f"background-color: {self.current_text_color}; "
                f"color: {self.get_contrasting_text_color(self.current_text_color)}; "
                f"font-weight: bold;"
            )
        else:
            logger.debug("Выбор цвета текста отменен.")

    # Методы для работы с шаблонами
    def delete_template_ui(self):
        logger.info("Запрос на удаление выбранного шаблона.")
        selected_item = self.templates_list_widget.currentItem()
        if not selected_item:
            logger.warning("Попытка удалить шаблон, но ни один шаблон не выбран в списке.")
            QMessageBox.warning(self, "Ошибка", "Выберите шаблон из списка для удаления.")
            return

        display_name = selected_item.text()
        filename_stem = selected_item.data(Qt.ItemDataRole.UserRole)
        logger.debug(f"Удаление шаблона: отображаемое имя='{display_name}', имя файла (без .json)='{filename_stem}'")
        
        reply = QMessageBox.question(self, "Подтверждение удаления", 
                                     f"Вы уверены, что хотите удалить шаблон '{display_name}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            logger.info(f"Пользователь подтвердил удаление шаблона '{display_name}'.")
            if template_manager.delete_template(filename_stem):
                logger.info(f"Шаблон '{display_name}' успешно удален через template_manager.")
                QMessageBox.information(self, "Успех", f"Шаблон '{display_name}' удален.")
                self.populate_templates_list()
            else:
                logger.error(f"Ошибка при удалении шаблона '{display_name}' через template_manager.")
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить шаблон '{display_name}'.")
        else:
            logger.info(f"Пользователь отменил удаление шаблона '{display_name}'.")
            
    def save_template_ui(self):
        logger.info("Запрос на сохранение текущих настроек как шаблон.")
        template_name = self.template_name_input.text().strip()
        if not template_name:
            logger.debug("Имя шаблона в поле ввода пустое, запрашиваем через QInputDialog.")
            template_name, ok = QInputDialog.getText(self, "Сохранить шаблон", "Введите имя для шаблона:")
            if not ok or not template_name.strip():
                logger.info("Сохранение шаблона отменено пользователем или не указано имя.")
                QMessageBox.warning(self, "Отмена", "Сохранение шаблона отменено: не указано имя.")
                return
            template_name = template_name.strip()
        logger.info(f"Имя для сохранения шаблона: '{template_name}'")
        
        current_settings = self._gather_current_settings_from_ui()
        settings_to_save = current_settings.copy()
        if "audio_tracks_info" in settings_to_save:
            settings_to_save["audio_tracks_info"] = [
                {k: v for k, v in track.items() if k != "item"} 
                for track in settings_to_save["audio_tracks_info"]
            ]

        if template_manager.save_template(settings_to_save, template_name):
            logger.info(f"Шаблон '{template_name}' успешно сохранен через template_manager.")
            QMessageBox.information(self, "Успех", f"Шаблон '{template_name}' успешно сохранен.")
            self.populate_templates_list()
            self.template_name_input.clear()
        else:
            logger.error(f"Ошибка при сохранении шаблона '{template_name}' через template_manager.")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить шаблон '{template_name}'.")

    def load_template_ui(self):
        logger.info("Запрос на загрузку выбранного шаблона.")
        selected_item = self.templates_list_widget.currentItem()
        if not selected_item:
            logger.warning("Попытка загрузить шаблон, но ни один шаблон не выбран в списке.")
            QMessageBox.warning(self, "Ошибка", "Выберите шаблон из списка для загрузки.")
            return
        
        filename_stem = selected_item.data(Qt.ItemDataRole.UserRole)
        display_name = selected_item.text()
        logger.info(f"Загрузка шаблона: отображаемое имя='{display_name}', имя файла (без .json)='{filename_stem}'")
        
        settings = template_manager.load_template(filename_stem)
        
        if settings:
            logger.info(f"Шаблон '{display_name}' успешно загружен из файла, применение настроек к UI...")
            self._apply_settings_to_ui(settings) 
            self.tab_widget.setCurrentIndex(0)
        else:
            logger.error(f"Не удалось загрузить шаблон '{display_name}' (файл: '{filename_stem}').")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить шаблон '{display_name}'.")

    # Методы для создания видео
    def create_video(self):
        logger.info("Нажата кнопка 'Создать видео'.")
        if not self.image_paths:
            logger.warning("Попытка создать видео без изображений. Отображено предупреждение пользователю.")
            QMessageBox.warning(self, "Ошибка", "Загрузите хотя бы одно изображение!")
            return
        
        if self.video_thread and self.video_thread.isRunning():
            logger.info("Попытка запустить создание видео, когда предыдущий процесс еще не завершен.")
            QMessageBox.information(self, "Информация", "Видео уже создается, подождите...")
            return
        
        logger.debug("Открытие диалога сохранения файла для видео.")
        output_path, _ = QFileDialog.getSaveFileName(self, "Сохранить видео как...", "video.mp4", "Видео (*.mp4)")
        if not output_path:
            logger.info("Сохранение видео отменено пользователем (не выбран путь вывода).")
            return
        logger.info(f"Видео будет сохранено в: {output_path}")
        
        video_params = self._gather_current_settings_from_ui()
        video_params['output_path'] = output_path
        logger.info(f"Параметры для создания видео собраны (без списков файлов): { {k: v for k, v in video_params.items() if k not in ['image_paths', 'audio_tracks_info']} }")
        
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.create_btn.setEnabled(False)
        self.status_label.setText("Создание видео...")
        self.status_label.setStyleSheet("QLabel { color: #2c3e50; font-weight: normal; }")
        
        self.video_thread = VideoCreatorThread(video_params)
        self.video_thread.progress_updated.connect(self.update_progress)
        self.video_thread.status_updated.connect(self.update_status)
        self.video_thread.finished_successfully.connect(self.video_finished)
        self.video_thread.error_occurred.connect(self.video_error)
        
        logger.info("Запуск потока VideoCreatorThread...")
        self.video_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_status(self, status):
        logger.info(f"Обновление статуса UI: '{status}'")
        self.status_label.setText(status)
        if "ошибка" not in status.lower() and "успешно" not in status.lower():
             self.status_label.setStyleSheet("QLabel { color: #2c3e50; font-weight: normal; }")

    def video_finished(self, output_path):
        logger.info(f"Процесс создания видео успешно завершен. Файл: {output_path}")
        self.progress_bar.setVisible(False)
        self.create_btn.setEnabled(True)
        self.status_label.setText("✅ Видео создано успешно!")
        self.status_label.setStyleSheet("QLabel { color: #27ae60; font-weight: bold; }")
        QMessageBox.information(self, "Успех", f"Видео сохранено:\n{output_path}")

    def video_error(self, error_msg):
        logger.error(f"Ошибка в процессе создания видео (сигнал из потока): {error_msg}")
        self.progress_bar.setVisible(False)
        self.create_btn.setEnabled(True)
        self.status_label.setText("❌ Ошибка создания видео")
        self.status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
        QMessageBox.critical(self, "Ошибка", error_msg)

    def closeEvent(self, event: QCloseEvent):
        logger.info("Событие закрытия приложения (closeEvent).")
        if self.video_thread and self.video_thread.isRunning():
            logger.warning("Попытка закрыть приложение во время создания видео.")
            reply = QMessageBox.question(self, "Закрытие приложения", "Видео еще создается. Закрыть приложение?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                logger.info("Пользователь подтвердил закрытие приложения во время создания видео.")
                if self.video_thread.isRunning(): 
                    logger.debug("Попытка мягкого завершения потока (quit/wait)...")
                    self.video_thread.quit() 
                    if not self.video_thread.wait(3000): 
                        logger.warning("Поток не завершился штатно за 3 сек. Принудительное завершение (terminate/wait)...")
                        self.video_thread.terminate() 
                        self.video_thread.wait() 
                        logger.info("Поток принудительно завершен.")
                    else:
                        logger.info("Поток штатно завершен после quit().")
                event.accept()
                logger.info("Приложение будет закрыто.")
            else:
                logger.info("Пользователь отменил закрытие приложения.")
                event.ignore()
        else:
            logger.info("Нет активного процесса создания видео. Приложение будет закрыто.")
            event.accept()


def main():
    # Исправление для macOS
    if sys.platform == 'darwin':
        os.environ['QT_MAC_WANTS_LAYER'] = '1'
    
    app = QApplication(sys.argv)
    app.setApplicationName("VideoCreator Pro")
    
    # Дополнительные настройки для macOS
    if sys.platform == 'darwin':
        app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)
    
    try:
        current_dir = Path(__file__).parent
        icon_path = current_dir / "icon.png" 
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
            logger.info(f"Иконка приложения установлена: {icon_path}")
        else:
            logger.warning(f"Файл иконки не найден: {icon_path}")
    except Exception as e:
        logger.error(f"Ошибка установки иконки приложения: {e}", exc_info=True)
    
    logger.info("Создание главного окна приложения VideoCreatorApp...")
    window = VideoCreatorApp()
    window.show()
    
    # Дополнительно для macOS - поднимаем окно на передний план
    if sys.platform == 'darwin':
        window.raise_()
        window.activateWindow()
    
    logger.info("Главное окно приложения отображено. Запуск event loop.")
    
    exit_code = app.exec()
    logger.info(f"Приложение завершено с кодом выхода: {exit_code}")
    sys.exit(exit_code)

if __name__ == "__main__":
    logger.info("Приложение VideoCreator Pro запускается (из __main__)...")
    main()