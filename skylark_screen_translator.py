import sys
import os
import certifi
import time
import re
import queue
import threading
import pytesseract
from PIL import ImageGrab, Image, ImageEnhance
import numpy as np
import subprocess
import platform
import shutil
import requests
import json
import math
import cv2
import socket
from datetime import datetime
from threading import Lock
from pathlib import Path
from online_translator import OnlineTranslator
from google_api import GoogleAPIDialog

# 设置外部数据目录
if 'APPIMAGE' in os.environ:
    # 如果是AppImage运行，使用AppImage所在目录
    external_dir = os.path.dirname(os.environ['APPIMAGE'])
elif 'APPDIR' in os.environ:
    # 如果是AppDir运行，使用AppDir所在目录
    external_dir = os.path.dirname(os.environ['APPDIR'])
else:
    # 否则，使用脚本所在目录
    external_dir = os.path.dirname(os.path.abspath(__file__))

# 只设置tessdata目录（不再需要argos包目录）
tessdata_dir = os.path.join(external_dir, 'tessdata')

# 创建目录（如果不存在）
os.makedirs(tessdata_dir, exist_ok=True)

# 设置环境变量（只保留TESSDATA_PREFIX）
os.environ['TESSDATA_PREFIX'] = tessdata_dir

# 打印目录信息（调试用）
print(f"外部数据目录: {external_dir}")
print(f"TESSDATA目录: {tessdata_dir}")

# 修复AppImage网络问题
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
if 'LD_PRELOAD' in os.environ:
    del os.environ['LD_PRELOAD']

MODERN_THEME_STYLES = """
/* 全局样式 */
QMainWindow {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #1a1a2e, stop:1 #16213e);
    color: #ffffff;
    font-family: 'Segoe UI', 'Microsoft YaHei', Arial, sans-serif;
}

/* 主要容器 */
QWidget {
    background-color: transparent;
    color: #ffffff;
    font-size: 14px;
}

/* 上方文字显示区域 - 设置为黑色字体 */
QWidget[objectName*="display"], QWidget[objectName*="info"], 
QTextEdit[objectName*="display"], QLabel[objectName*="display"] {
    color: #000000;  /* 黑色字体 */
    background-color: rgba(255, 255, 255, 0.9);  /* 浅色背景确保可读性 */
}

/* 或者为整个上方区域设置样式 */
QFrame[objectName*="top"], QFrame[objectName*="upper"],
QGroupBox[objectName*="display"] {
    color: #000000;
}

QFrame[objectName*="top"] QLabel, QFrame[objectName*="upper"] QLabel,
QGroupBox[objectName*="display"] QLabel {
    color: #000000;
}

/* 组框样式 - 增强文字对比度 */
QGroupBox {
    font-size: 16px;
    font-weight: bold;
    color: #ffffff;  /* 改为纯白色提高对比度 */
    border: 2px solid #606060;  /* 增强边框颜色 */
    border-radius: 12px;
    margin-top: 12px;
    padding-top: 15px;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 rgba(255,255,255,0.08), 
                               stop:1 rgba(255,255,255,0.04));
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 15px;
    padding: 5px 15px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                               stop:0 #64b5f6, stop:1 #42a5f5);
    border-radius: 8px;
    color: #ffffff;
    font-weight: bold;
}

/* 按钮样式 - 修复尺寸问题 */
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #667eea, stop:1 #764ba2);
    border: none;
    border-radius: 6px;
    color: #ffffff;
    font-size: 10px;    /* 进一步减小字体 */
    font-weight: bold;
    padding: 2px 4px;   /* 大幅减小内边距 */
    min-height: 20px;   /* 减小最小高度 */
    min-width: 40px;    /* 减小最小宽度 */
    max-height: 26px;   /* 减小最大高度 */
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #7c4dff, stop:1 #8e24aa);
}

QPushButton:pressed {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #5e35b1, stop:1 #7b1fa2);
}

QPushButton:disabled {
    background: #424242;
    color: #757575;
}

/* 特殊按钮样式 - 安装按钮 */
QPushButton[objectName="install_btn"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #4caf50, stop:1 #2e7d32);
    font-size: 9px;     /* 更小的字体 */
    padding: 2px 4px;   /* 更小的内边距 */
}

QPushButton[objectName="install_btn"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #66bb6a, stop:1 #388e3c);
}

/* 特殊按钮样式 - 卸载按钮 */
QPushButton[objectName="uninstall_btn"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #f44336, stop:1 #c62828);
    font-size: 9px;     /* 更小的字体 */
    padding: 2px 4px;   /* 更小的内边距 */
}

QPushButton[objectName="uninstall_btn"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #ef5350, stop:1 #d32f2f);
}

/* 文本编辑器样式 - 增强对比度 */
QTextEdit {
    background: rgba(0, 0, 0, 0.3);  /* 增强背景对比度 */
    border: 2px solid #606060;
    border-radius: 10px;
    color: #ffffff;
    font-size: 14px;
    padding: 12px;
    selection-background-color: #64b5f6;
}

QTextEdit:focus {
    border: 2px solid #64b5f6;
}

/* 下拉框样式 */
QComboBox {
    background: rgba(0, 0, 0, 0.3);
    border: 2px solid #606060;
    border-radius: 8px;
    color: #ffffff;
    font-size: 14px;
    padding: 8px 12px;
    min-height: 20px;
}

QComboBox:hover {
    border: 2px solid #64b5f6;
}

QComboBox:focus {
    border: 2px solid #64b5f6;
}

QComboBox::drop-down {
    border: none;
    width: 30px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 8px solid #64b5f6;
    margin-right: 8px;
}

QComboBox QAbstractItemView {
    background: #2d2d30;
    border: 1px solid #64b5f6;
    border-radius: 5px;
    color: #ffffff;
    selection-background-color: #64b5f6;
    selection-color: #ffffff;
}

/* 标签样式 - 增强对比度 */
QLabel {
    color: #ffffff;  /* 改为纯白色 */
    font-size: 14px;
    font-weight: normal;
}

/* 输入框样式 */
QLineEdit {
    background: rgba(0, 0, 0, 0.3);
    border: 2px solid #606060;
    border-radius: 8px;
    color: #ffffff;
    font-size: 14px;
    padding: 8px 12px;
    min-height: 20px;
}

QLineEdit:focus {
    border: 2px solid #64b5f6;
}

QLineEdit:hover {
    border: 2px solid #64b5f6;
}

/* 列表框样式 */
QListWidget {
    background: rgba(0, 0, 0, 0.2);
    border: 2px solid #606060;
    border-radius: 10px;
    color: #ffffff;
    font-size: 14px;
    padding: 5px;
}

QListWidget::item {
    background: transparent;
    border-radius: 6px;
    padding: 8px 12px;
    margin: 2px;
    color: #ffffff;
}

QListWidget::item:hover {
    background: rgba(100, 181, 246, 0.2);
}

QListWidget::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #64b5f6, stop:1 #42a5f5);
    color: #ffffff;
}

/* 表格样式 - 修复按钮显示问题 */
QTableWidget {
    background: rgba(0, 0, 0, 0.2);
    border: 2px solid #606060;
    border-radius: 10px;
    color: #ffffff;
    gridline-color: #505050;
    font-size: 13px;
    alternate-background-color: rgba(255, 255, 255, 0.02);
}

QTableWidget::item {
    padding: 2px 3px;   /* 进一步减小内边距 */
    border-bottom: 1px solid #404040;
    color: #ffffff;
    min-height: 28px;   /* 减小最小行高 */
}

QTableWidget::item:selected {
    background: rgba(100, 181, 246, 0.3);
    color: #ffffff;
}

QHeaderView::section {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #505050, stop:1 #404040);
    color: #ffffff;
    padding: 8px;
    border: 1px solid #606060;
    font-weight: bold;
    font-size: 13px;
}

/* 滚动条样式 */
QScrollBar:vertical {
    background: rgba(255, 255, 255, 0.05);
    width: 12px;
    border-radius: 6px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #64b5f6;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #42a5f5;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: rgba(255, 255, 255, 0.05);
    height: 12px;
    border-radius: 6px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #64b5f6;
    border-radius: 6px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background: #42a5f5;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* 进度条样式 */
QProgressBar {
    background: rgba(0, 0, 0, 0.3);
    border: 2px solid #606060;
    border-radius: 8px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                               stop:0 #64b5f6, stop:1 #42a5f5);
    border-radius: 6px;
}

/* 选项卡样式 - 增强对比度 */
QTabWidget::pane {
    border: 2px solid #606060;
    border-radius: 10px;
    background: rgba(0, 0, 0, 0.1);
}

QTabBar::tab {
    background: rgba(255, 255, 255, 0.08);
    border: 2px solid #606060;
    padding: 10px 20px;
    margin: 2px;
    border-radius: 8px;
    color: #ffffff;  /* 改为纯白色 */
    font-weight: bold;
}

QTabBar::tab:selected {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #64b5f6, stop:1 #42a5f5);
    color: #ffffff;
}

QTabBar::tab:hover {
    background: rgba(100, 181, 246, 0.3);
    color: #ffffff;
}

/* 对话框样式 */
QDialog {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #1a1a2e, stop:1 #16213e);
    color: #ffffff;
}

/* 消息框样式 */
QMessageBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                               stop:0 #1a1a2e, stop:1 #16213e);
    color: #ffffff;
}

QMessageBox QPushButton {
    min-width: 80px;
    padding: 8px 16px;
    max-height: none;  /* 消息框按钮不限制高度 */
}

/* 工具提示样式 */
QToolTip {
    background: #2d2d30;
    color: #ffffff;
    border: 1px solid #64b5f6;
    border-radius: 5px;
    padding: 5px;
    font-size: 12px;
}

/* 状态栏样式 */
QStatusBar {
    background: rgba(0, 0, 0, 0.2);
    border-top: 1px solid #606060;
    color: #ffffff;
}

/* 菜单样式 */
QMenuBar {
    background: rgba(0, 0, 0, 0.2);
    color: #ffffff;
    font-weight: bold;
}

QMenuBar::item {
    padding: 8px 12px;
    background: transparent;
    color: #ffffff;
}

QMenuBar::item:selected {
    background: #64b5f6;
    border-radius: 4px;
}

QMenu {
    background: #2d2d30;
    border: 1px solid #64b5f6;
    border-radius: 5px;
    color: #ffffff;
}

QMenu::item {
    padding: 8px 20px;
    color: #ffffff;
}

QMenu::item:selected {
    background: #64b5f6;
}

/* 分割器样式 */
QSplitter::handle {
    background: #606060;
}

QSplitter::handle:horizontal {
    width: 3px;
}

QSplitter::handle:vertical {
    height: 3px;
}

QSplitter::handle:pressed {
    background: #64b5f6;
}

/* 滑块样式 */
QSlider::groove:horizontal {
    border: 1px solid #606060;
    height: 8px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 4px;
}

QSlider::handle:horizontal {
    background: #64b5f6;
    border: 1px solid #42a5f5;
    width: 18px;
    border-radius: 9px;
    margin: -5px 0;
}

QSlider::handle:horizontal:hover {
    background: #42a5f5;
}

/* 复选框样式 */
QCheckBox {
    color: #ffffff;
    font-size: 14px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 3px;
    border: 2px solid #606060;
    background: rgba(0, 0, 0, 0.3);
}

QCheckBox::indicator:hover {
    border: 2px solid #64b5f6;
}

QCheckBox::indicator:checked {
    background: #64b5f6;
    border: 2px solid #42a5f5;
}

/* 单选按钮样式 */
QRadioButton {
    color: #ffffff;
    font-size: 14px;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 9px;
    border: 2px solid #606060;
    background: rgba(0, 0, 0, 0.3);
}

QRadioButton::indicator:hover {
    border: 2px solid #64b5f6;
}

QRadioButton::indicator:checked {
    background: #64b5f6;
    border: 2px solid #42a5f5;
}
"""

# 修复后的 apply_modern_theme 函数
def apply_modern_theme(app):
    """
    应用现代化主题到整个应用程序
    """
    # 基础样式表
    style_sheet = MODERN_THEME_STYLES
    
    # Windows 特定调整
    if platform.system() == "Windows":
        windows_adjustments = """
        /* Windows 特定调整 */
        QPushButton {
            min-height: 30px;
            padding: 6px 10px;
            font-size: 11px;
        }
        
        QTreeWidget {
            font-size: 12px;
        }
        
        QLabel {
            font-size: 12px;
        }
        """
        style_sheet += windows_adjustments
    
    # 应用样式表
    app.setStyleSheet(style_sheet)
    
    # 设置应用程序属性
    try:
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except:
        pass

# 高DPI设置函数
def setup_high_dpi():
    """在创建QApplication之前设置高DPI支持"""
    import os
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'
    
    # 或者在创建QApplication之前设置属性
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# 修复上方显示区域文字颜色的函数
def fix_display_area_text_color(main_window):
    """
    修复上方显示区域的文字颜色为黑色
    """
    # 方法1: 查找所有浅色背景的QWidget并设置其子控件文字颜色
    for widget in main_window.findChildren(QWidget):
        # 检查背景色
        palette = widget.palette()
        bg_color = palette.color(palette.Window)
        
        # 如果背景是浅色的，设置文字为黑色
        if bg_color.lightness() > 200:  # 浅色背景
            widget.setStyleSheet("""
                QWidget {
                    color: #000000;
                }
                QLabel {
                    color: #000000;
                }
                QTextEdit {
                    color: #000000;
                }
            """)
    
    # 方法2: 直接查找所有QLabel和QTextEdit设置黑色字体
    for label in main_window.findChildren(QLabel):
        # 检查父控件背景
        parent = label.parent()
        if parent:
            palette = parent.palette()
            bg_color = palette.color(palette.Window)
            if bg_color.lightness() > 200:
                label.setStyleSheet("QLabel { color: #000000; }")
    
    for text_edit in main_window.findChildren(QTextEdit):
        # 如果是只读的文本编辑器且背景浅色
        if text_edit.isReadOnly():
            palette = text_edit.palette()
            bg_color = palette.color(palette.Base)
            if bg_color.lightness() > 200:
                text_edit.setStyleSheet("QTextEdit { color: #000000; }")

# 使用方法：在应用主题后调用
# fix_display_area_text_color(your_main_window)
def setup_table_buttons(table_widget):
    """
    为表格中的按钮设置合适的尺寸
    """
    for row in range(table_widget.rowCount()):
        for col in range(table_widget.columnCount()):
            item = table_widget.cellWidget(row, col)
            if isinstance(item, QPushButton):
                item.setMaximumHeight(24)  # 进一步限制最大高度
                item.setMinimumHeight(20)  # 减小最小高度
                item.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                item.setStyleSheet("""
                    QPushButton {
                        font-size: 9px;
                        padding: 1px 3px;
                        margin: 1px;
                    }
                """)
    
    # 设置行高
    table_widget.verticalHeader().setDefaultSectionSize(30)  # 减小行高
    
    # 如果需要，可以调整列宽
    # table_widget.setColumnWidth(列索引, 宽度)

# 动画效果类（可选）
class ButtonHoverEffect:
    """为按钮添加悬停动画效果"""
    
    def __init__(self, button):
        self.button = button
        self.original_style = button.styleSheet()
        
        # 连接悬停事件
        button.enterEvent = self.on_enter
        button.leaveEvent = self.on_leave
    
    def on_enter(self, event):
        """鼠标进入时的效果"""
        shadow_style = """
        QPushButton {
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1, 
                                       stop:0 #7c4dff, stop:1 #8e24aa);
            border: none;
            border-radius: 10px;
            color: #ffffff;
            font-size: 14px;
            font-weight: bold;
            padding: 12px 20px;
        }
        """
        self.button.setStyleSheet(shadow_style)
    
    def on_leave(self, event):
        """鼠标离开时的效果"""
        self.button.setStyleSheet(self.original_style)

try:
    from pynput import mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("警告: pynput 库未安装，全局右键监听功能将不可用")
    print("请运行: pip install pynput")


env_vars = [
    'QT_QPA_PLATFORM_PLUGIN_PATH',
    'QT_PLUGIN_PATH',
    'QT_AUTO_SCREEN_SCALE_FACTOR',
    'QT_SCALE_FACTOR',
    'QT_SCREEN_SCALE_FACTORS',
    'QT_QPA_PLATFORM'
]

for var in env_vars:
    if var in os.environ:
        del os.environ[var]

# 设置PyQt5的插件路径
try:
    from PyQt5 import QtCore
    pyqt_path = os.path.dirname(QtCore.__file__)
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(pyqt_path, "Qt5", "plugins")
except ImportError:
    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = os.path.join(sys.prefix, "Lib", "site-packages", "PyQt5", "Qt5", "plugins")

# 现在导入PyQt5
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QTextEdit,
    QComboBox, QHBoxLayout, QVBoxLayout, QGroupBox, QSizePolicy, QMessageBox, QDialog,
    QLineEdit, QListWidget, QListWidgetItem, QTabWidget, QFileDialog,
    QDialogButtonBox, QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QTreeWidget, QTreeWidgetItem, QRadioButton, QMenu, QDesktopWidget, QProgressDialog
)
from PyQt5.QtCore import Qt, QRect, QTimer, QPoint, QEvent, QThread, pyqtSignal, QLibraryInfo, QSize, QMetaType, QObject
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QKeyEvent, 
    QMouseEvent, QImage, QPixmap, QIcon, QTextCursor
)

# 处理不同PyQt5版本的兼容性问题和修复段错误
try:
    from PyQt5.QtCore import qRegisterMetaType
    # 注册所有必要的元类型以避免段错误
    qRegisterMetaType('QTextCursor')
    qRegisterMetaType('QTextCursor&')
    qRegisterMetaType('QVector<int>')
    qRegisterMetaType('QString')
    qRegisterMetaType('bool')
    qRegisterMetaType('float')
    qRegisterMetaType('double')
    print("✅ 主程序: 元类型注册成功")
except ImportError:
    # 尝试备用方式
    try:
        from PyQt5 import QtCore
        qRegisterMetaType = getattr(QtCore, 'qRegisterMetaType', None)
        if qRegisterMetaType:
            qRegisterMetaType('QTextCursor')
            qRegisterMetaType('QTextCursor&')
            qRegisterMetaType('QVector<int>')
            qRegisterMetaType('QString')
            qRegisterMetaType('bool')
            qRegisterMetaType('float')
            qRegisterMetaType('double')
            print("✅ 主程序: 备用元类型注册成功")
        else:
            print("ℹ️ 主程序: 使用自动元类型注册")
    except Exception as e:
        print(f"ℹ️ 主程序: 跳过元类型注册 - {e}")
except Exception as e:
    print(f"⚠️ 主程序: 元类型注册失败: {e}")

# --- 添加 argostranslate 可用性检查 ---
ARGOS_TRANSLATE_AVAILABLE = False
try:
    import argostranslate.package
    import argostranslate.translate
    ARGOS_TRANSLATE_AVAILABLE = True
except ImportError:
    print("警告: argostranslate 库未安装，翻译功能将不可用")

# 默认语言设置
SOURCE_LANG = "en"
TARGET_LANG = "zh"

# 支持的语言列表
SUPPORTED_LANGUAGES = [
    ("ar", "Arabic"),
    ("az", "Azerbaijani"),
    ("ca", "Catalan"),
    ("zh", "Chinese"),
    ("cs", "Czech"),
    ("da", "Danish"),
    ("nl", "Dutch"),
    ("en", "English"),
    ("eo", "Esperanto"),
    ("fi", "Finnish"),
    ("fr", "French"),
    ("de", "German"),
    ("el", "Greek"),
    ("he", "Hebrew"),
    ("hi", "Hindi"),
    ("hu", "Hungarian"),
    ("id", "Indonesian"),
    ("ga", "Irish"),
    ("it", "Italian"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("ms", "Malay"),
    ("fa", "Persian"),
    ("pl", "Polish"),
    ("pt", "Portuguese"),
    ("ru", "Russian"),
    ("sk", "Slovak"),
    ("es", "Spanish"),
    ("sv", "Swedish"),
    ("tr", "Turkish"),
    ("uk", "Ukrainian")
]

# OCR语言映射
OCR_LANG_MAP = {
    "ar": "ara",
    "az": "aze",
    "ca": "cat",
    "zh": "chi_sim",
    "cs": "ces",
    "da": "dan",
    "nl": "nld",
    "en": "eng",
    "eo": "epo",
    "fi": "fin",
    "fr": "fra",
    "de": "deu",
    "el": "ell",
    "he": "heb",
    "hi": "hin",
    "hu": "hun",
    "id": "ind",
    "ga": "gle",
    "it": "ita",
    "ja": "jpn",
    "ko": "kor",
    "ms": "msa",
    "fa": "fas",
    "pl": "pol",
    "pt": "por",
    "ru": "rus",
    "sk": "slk",
    "es": "spa",
    "sv": "swe",
    "tr": "tur",
    "uk": "ukr"
}

# 包大小信息（如果无法从网络获取，使用这些估计值）
PACKAGE_SIZE_ESTIMATES = {
    "ar": 150, "az": 120, "ca": 130, "zh": 300, "cs": 140,
    "da": 130, "nl": 140, "en": 200, "eo": 100, "fi": 140,
    "fr": 180, "de": 180, "el": 150, "he": 150, "hi": 160,
    "hu": 150, "id": 130, "ga": 120, "it": 170, "ja": 280,
    "ko": 260, "ms": 130, "fa": 150, "pl": 150, "pt": 170,
    "ru": 180, "sk": 140, "es": 180, "sv": 140, "tr": 150,
    "uk": 160
}

# 内置默认语言包列表（离线模式使用）
DEFAULT_LANGUAGE_PACKAGES = [
    {
        "from_code": "en", "to_code": "es", 
        "from_name": "English", "to_name": "Spanish",
        "file_name": "en_es.argosmodel", 
        "size": 130, "description": "英语到西班牙语翻译模型"
    },
    {
        "from_code": "en", "to_code": "fr", 
        "from_name": "English", "to_name": "French",
        "file_name": "en_fr.argosmodel", 
        "size": 140, "description": "英语到法语翻译模型"
    },
    {
        "from_code": "en", "to_code": "de", 
        "from_name": "English", "to_name": "German",
        "file_name": "en_de.argosmodel", 
        "size": 140, "description": "英语到德语翻译模型"
    },
    {
        "from_code": "en", "to_code": "it", 
        "from_name": "English", "to_name": "Italian",
        "file_name": "en_it.argosmodel", 
        "size": 140, "description": "英语到意大利语翻译模型"
    },
    {
        "from_code": "en", "to_code": "pt", 
        "from_name": "English", "to_name": "Portuguese",
        "file_name": "en_pt.argosmodel", 
        "size": 140, "description": "英语到葡萄牙语翻译模型"
    },
    {
        "from_code": "en", "to_code": "ru", 
        "from_name": "English", "to_name": "Russian",
        "file_name": "en_ru.argosmodel", 
        "size": 150, "description": "英语到俄语翻译模型"
    },
    {
        "from_code": "en", "to_code": "zh", 
        "from_name": "English", "to_name": "Chinese",
        "file_name": "en_zh.argosmodel", 
        "size": 180, "description": "英语到中文翻译模型"
    },
    {
        "from_code": "en", "to_code": "ja", 
        "from_name": "English", "to_name": "Japanese",
        "file_name": "en_ja.argosmodel", 
        "size": 190, "description": "英语到日语翻译模型"
    },
    {
        "from_code": "en", "to_code": "ko", 
        "from_name": "English", "to_name": "Korean",
        "file_name": "en_ko.argosmodel", 
        "size": 190, "description": "英语到韩语翻译模型"
    },
    {
        "from_code": "es", "to_code": "en", 
        "from_name": "Spanish", "to_name": "English",
        "file_name": "es_en.argosmodel", 
        "size": 130, "description": "西班牙语到英语翻译模型"
    },
    {
        "from_code": "fr", "to_code": "en", 
        "from_name": "French", "to_name": "English",
        "file_name": "fr_en.argosmodel", 
        "size": 140, "description": "法语到英语翻译模型"
    },
    {
        "from_code": "de", "to_code": "en", 
        "from_name": "German", "to_name": "English",
        "file_name": "de_en.argosmodel", 
        "size": 140, "description": "德语到英语翻译模型"
    },
    {
        "from_code": "zh", "to_code": "en", 
        "from_name": "Chinese", "to_name": "English",
        "file_name": "zh_en.argosmodel", 
        "size": 180, "description": "中文到英语翻译模型"
    },
    {
        "from_code": "ja", "to_code": "en", 
        "from_name": "Japanese", "to_name": "English",
        "file_name": "ja_en.argosmodel", 
        "size": 190, "description": "日语到英语翻译模型"
    },
    {
        "from_code": "ko", "to_code": "en", 
        "from_name": "Korean", "to_name": "English",
        "file_name": "ko_en.argosmodel", 
        "size": 190, "description": "韩语到英语翻译模型"
    }
]

class DownloadWorker(QObject):
    """下载工作线程类"""
    finished = pyqtSignal(bool, str, str)  # success, message, ocr_code
    progress = pyqtSignal(int)  # 下载进度百分比

    def __init__(self, ocr_code, download_url, output_path):
        super().__init__()
        self.ocr_code = ocr_code
        self.download_url = download_url
        self.output_path = output_path

    def run(self):
        try:
            import requests
            response = requests.get(self.download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(self.output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # 计算并发送进度
                        if total_size > 0:
                            progress = int(downloaded * 100 / total_size)
                            self.progress.emit(progress)
            
            self.finished.emit(True, f"下载成功: {os.path.basename(self.output_path)}", self.ocr_code)
        except Exception as e:
            self.finished.emit(False, f"下载失败: {e}", self.ocr_code)

class SystemDetector:
    """系统检测工具类，支持各种Linux发行版和Windows"""
    
    @staticmethod
    def get_system_info():
        """获取系统基本信息"""
        system = platform.system()
        if system == "Windows":
            return {
                'os_type': 'windows',
                'distro': 'windows',
                'version': platform.release(),
                'package_manager': 'none'
            }
        elif system == "Linux":
            return SystemDetector._get_linux_info()
        else:
            return {
                'os_type': system.lower(),
                'distro': 'unknown',
                'version': 'unknown',
                'package_manager': 'none'
            }
    
    @staticmethod
    def _get_linux_info():
        """获取Linux发行版信息 - 增强版"""
        try:
            with open('/etc/os-release', 'r') as f:
                lines = f.readlines()
            
            info = {}
            for line in lines:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    info[key] = value.strip('"')
            
            distro_id = info.get('ID', '').lower()
            distro_like = info.get('ID_LIKE', '').lower()
            version = info.get('VERSION_ID', 'unknown')
            
            # 更全面的发行版识别
            pkg_manager = 'unknown'
            distro_family = 'unknown'
            
            # Debian/Ubuntu 系列
            if distro_id in ['ubuntu', 'debian'] or 'debian' in distro_like:
                pkg_manager = 'apt'
                distro_family = 'debian'
            
            # RedHat/CentOS/Fedora 系列
            elif (distro_id in ['fedora', 'rhel', 'centos', 'rocky', 'almalinux'] or 
                  any(x in distro_like for x in ['fedora', 'rhel'])):
                # 检查是使用dnf还是yum
                if distro_id == 'fedora' or (distro_id in ['rhel', 'centos'] and 
                                             int(version.split('.')[0]) >= 8):
                    pkg_manager = 'dnf'
                else:
                    pkg_manager = 'yum'
                distro_family = 'redhat'
            
            # Arch Linux 系列
            elif distro_id in ['arch', 'manjaro'] or 'arch' in distro_like:
                pkg_manager = 'pacman'
                distro_family = 'arch'
            
            # openSUSE 系列
            elif distro_id in ['opensuse', 'sles'] or 'suse' in distro_like:
                pkg_manager = 'zypper'
                distro_family = 'suse'
            
            # Alpine Linux
            elif distro_id == 'alpine':
                pkg_manager = 'apk'
                distro_family = 'alpine'
            
            # Gentoo Linux
            elif distro_id == 'gentoo':
                pkg_manager = 'emerge'
                distro_family = 'gentoo'
            
            return {
                'os_type': 'linux',
                'distro': distro_id,
                'distro_family': distro_family,
                'version': version,
                'package_manager': pkg_manager
            }
            
        except Exception as e:
            print(f"无法检测Linux发行版: {e}")
            return {
                'os_type': 'linux',
                'distro': 'unknown',
                'version': 'unknown',
                'package_manager': 'unknown'
            }
    
    # 在 SystemDetector 类中更新各个命令获取方法，添加 yum 支持
    @staticmethod
    def get_tesseract_install_command():
        """获取安装Tesseract的命令 - 增强版"""
        sys_info = SystemDetector.get_system_info()
        
        if sys_info['os_type'] == 'windows':
            return None  # Windows需要手动安装
        
        pkg_manager = sys_info['package_manager']
        
        commands = {
            'apt': ['sudo', '-S', 'apt-get', 'update', '&&', 'sudo', '-S', 'apt-get', 'install', 'tesseract-ocr', '-y'],
            'dnf': ['sudo', '-S', 'dnf', 'install', 'tesseract', '-y'],
            'yum': ['sudo', '-S', 'yum', 'install', 'tesseract', '-y'],  # 添加yum支持
            'pacman': ['sudo', '-S', 'pacman', '-S', 'tesseract', '--noconfirm'],
            'zypper': ['sudo', '-S', 'zypper', 'install', 'tesseract-ocr', '-y'],
            'apk': ['sudo', '-S', 'apk', 'add', 'tesseract-ocr']
        }
        
        return commands.get(pkg_manager)
    
    @staticmethod
    def get_ocr_language_command(ocr_code, action='install'):
        """获取安装/卸载OCR语言包的命令 - 增强版"""
        sys_info = SystemDetector.get_system_info()
        
        if sys_info['os_type'] == 'windows':
            return None
        
        pkg_manager = sys_info['package_manager']
        
        if action == 'install':
            commands = {
                'apt': ['sudo', '-S', 'apt-get', 'install', f'tesseract-ocr-{ocr_code}', '-y'],
                'dnf': ['sudo', '-S', 'dnf', 'install', f'tesseract-langpack-{ocr_code}', '-y'],
                'yum': ['sudo', '-S', 'yum', 'install', f'tesseract-langpack-{ocr_code}', '-y'],  # 添加yum支持
                'pacman': ['sudo', '-S', 'pacman', '-S', f'tesseract-data-{ocr_code}', '--noconfirm'],
                'zypper': ['sudo', '-S', 'zypper', 'install', f'tesseract-ocr-traineddata-{ocr_code}', '-y'],
                'apk': ['sudo', '-S', 'apk', 'add', f'tesseract-ocr-data-{ocr_code}']
            }
        else:  # remove
            commands = {
                'apt': ['sudo', '-S', 'apt-get', 'remove', f'tesseract-ocr-{ocr_code}', '-y'],
                'dnf': ['sudo', '-S', 'dnf', 'remove', f'tesseract-langpack-{ocr_code}', '-y'],
                'yum': ['sudo', '-S', 'yum', 'remove', f'tesseract-langpack-{ocr_code}', '-y'],  # 添加yum支持
                'pacman': ['sudo', '-S', 'pacman', '-Rs', f'tesseract-data-{ocr_code}', '--noconfirm'],
                'zypper': ['sudo', '-S', 'zypper', 'remove', f'tesseract-ocr-traineddata-{ocr_code}', '-y'],
                'apk': ['sudo', '-S', 'apk', 'del', f'tesseract-ocr-data-{ocr_code}']
            }
        
        return commands.get(pkg_manager)
    
    @staticmethod
    def get_tesseract_uninstall_command():
        """获取卸载Tesseract的命令 - 增强版"""
        sys_info = SystemDetector.get_system_info()
        
        if sys_info['os_type'] == 'windows':
            return None
        
        pkg_manager = sys_info['package_manager']
        
        commands = {
            'apt': ['sudo', '-S', 'apt-get', 'remove', 'tesseract-ocr', '-y'],
            'dnf': ['sudo', '-S', 'dnf', 'remove', 'tesseract', '-y'],
            'yum': ['sudo', '-S', 'yum', 'remove', 'tesseract', '-y'],  # 添加yum支持
            'pacman': ['sudo', '-S', 'pacman', '-Rs', 'tesseract', '--noconfirm'],
            'zypper': ['sudo', '-S', 'zypper', 'remove', 'tesseract-ocr', '-y'],
            'apk': ['sudo', '-S', 'apk', 'del', 'tesseract-ocr']
        }
        
        return commands.get(pkg_manager)
    
    @staticmethod
    def get_complete_tesseract_uninstall_command():
        """获取完全卸载Tesseract和所有语言包的命令 - 增强版"""
        sys_info = SystemDetector.get_system_info()
        
        if sys_info['os_type'] == 'windows':
            return None
        
        pkg_manager = sys_info['package_manager']
        
        commands = {
            'apt': ['sudo', '-S', 'apt-get', 'remove', 'tesseract-ocr*', '-y'],
            'dnf': ['sudo', '-S', 'dnf', 'remove', 'tesseract*', '-y'],
            'yum': ['sudo', '-S', 'yum', 'remove', 'tesseract*', '-y'],  # 添加yum支持
            'pacman': ['sudo', '-S', 'pacman', '-Rs', 'tesseract', 'tesseract-data-*', '--noconfirm'],
            'zypper': ['sudo', '-S', 'zypper', 'remove', 'tesseract*', '-y'],
            'apk': ['sudo', '-S', 'apk', 'del', 'tesseract*']
        }
        
        return commands.get(pkg_manager)


class PasswordDialog(QDialog):
    """密码输入对话框"""
    def __init__(self, parent=None, title="需要管理员权限"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setFixedSize(300, 150)
        
        layout = QVBoxLayout()
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("输入管理员密码")
        
        layout.addWidget(QLabel("请输入管理员密码以继续:"))
        layout.addWidget(self.password_input)
        
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        
        layout.addWidget(btn_box)
        self.setLayout(layout)
    
    def get_password(self):
        return self.password_input.text()

class LanguagePackDialog(QDialog):
    """OCR语言包管理对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("OCR语言包管理器")
        self.setWindowIcon(QIcon("skylark.png"))
        self.setMinimumSize(550, 400)

        # Windows 特定设置
        if platform.system() == "Windows":
            # 增加对话框大小
            self.setMinimumSize(550, 400)
            # 设置 Windows 友好的字体
            self.setFont(QFont("Microsoft YaHei", 9))

        # 添加说明
        self.info_label = QLabel(
            "<b>OCR语言包管理</b><br>"
            "安装OCR语言包以提高文本识别准确率。<br>"
            "要使用完整功能，请确保您的设备连接到互联网。"
        )
        self.info_label.setStyleSheet("background-color: #FFF8DC; padding: 10px; color: #000000;")
        self.info_label.setWordWrap(True)
        
        # 创建顶部按钮布局
        top_button_layout = QHBoxLayout()
        
        # 添加关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        top_button_layout.addWidget(self.close_btn)
        
        # 添加弹性空间
        top_button_layout.addStretch()
        
        self.tab_widget = QTabWidget()
        
        # OCR语言包标签页
        self.ocr_tab = OCRLanguageTab(self, self.main_window)
        self.tab_widget.addTab(self.ocr_tab, "OCR语言包")
        
        # Tesseract安装标签页
        self.install_tab = TesseractInstallTab(self, self.main_window)
        self.tab_widget.addTab(self.install_tab, "安装Tesseract")
        
        layout = QVBoxLayout()
        layout.addWidget(self.info_label)
        layout.addLayout(top_button_layout)  # 添加按钮布局
        layout.addWidget(self.tab_widget)
        self.setLayout(layout)
        
        # 状态标签
        self.status_label = QLabel("就绪")
        layout.addWidget(self.status_label)
        
        # 添加状态更新定时器
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(500)
    
        # 添加 Google API 管理标签页
        self.google_api_tab = GoogleAPIDialog(self)
        self.tab_widget.addTab(self.google_api_tab, "Google API管理")

    def showEvent(self, event):
        """重写 showEvent 以在显示时调整布局"""
        super().showEvent(event)
        
        # Windows 特定调整
        if platform.system() == "Windows":
            QTimer.singleShot(100, self.adjust_windows_layout)
    
    def adjust_windows_layout(self):
        """Windows 特定的布局调整"""
        # 调整按钮大小
        for btn in [self.ocr_tab.install_btn, self.ocr_tab.remove_btn, self.ocr_tab.refresh_btn]:
            btn.setFixedHeight(35)
            
        # 强制更新布局
        self.layout().activate()
        self.updateGeometry()

    def update_status(self):
        """从状态队列更新状态标签"""
        try:
            while not self.main_window.status_queue.empty():
                message = self.main_window.status_queue.get_nowait()
                self.status_label.setText(message)
        except queue.Empty:
            pass


class OCRLanguageTab(QWidget):
    """OCR语言包管理标签页"""
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.parent = parent
        self.main_window = main_window
        self.setup_ui()

        # 初始化下载线程和进度对话框
        self.download_thread = None
        self.download_worker = None
        self.progress_dialog = None
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        self.lang_list = QTreeWidget()
        self.lang_list.setHeaderLabels(["语言", "OCR代码", "状态", "大小 (MB)"])
        self.lang_list.setColumnWidth(0, 200)
        self.populate_lang_list()
        layout.addWidget(QLabel("OCR语言包:"))
        layout.addWidget(self.lang_list)
        
        btn_layout = QHBoxLayout()
        
        # Windows 特定调整
        if platform.system() == "Windows":
            btn_layout.setContentsMargins(15, 15, 15, 15)  # 增加边距
            btn_layout.setSpacing(15)  # 增加间距
        
        self.install_btn = QPushButton("安装语言包")
        
        # Windows 特定按钮设置
        if platform.system() == "Windows":
            self.install_btn.setMinimumSize(120, 35)  # 增加按钮最小尺寸
            self.install_btn.setStyleSheet("""
                QPushButton {
                    padding: 6px;
                    font-size: 11px;
                    font-weight: bold;
                }
            """)
        
        self.install_btn.clicked.connect(lambda: self.install_ocr_language())
        btn_layout.addWidget(self.install_btn)
        
        self.remove_btn = QPushButton("删除选中语言包")
        
        # Windows 特定按钮设置
        if platform.system() == "Windows":
            self.remove_btn.setMinimumSize(120, 35)
            self.remove_btn.setStyleSheet("""
                QPushButton {
                    padding: 6px;
                    font-size: 11px;
                    font-weight: bold;
                }
            """)
        
        self.remove_btn.clicked.connect(self.remove_ocr_lang)
        btn_layout.addWidget(self.remove_btn)
        
        self.refresh_btn = QPushButton("刷新列表")
        
        # Windows 特定按钮设置
        if platform.system() == "Windows":
            self.refresh_btn.setMinimumSize(100, 35)
            self.refresh_btn.setStyleSheet("""
                QPushButton {
                    padding: 6px;
                    font-size: 11px;
                    font-weight: bold;
                }
            """)
        
        self.refresh_btn.clicked.connect(self.populate_lang_list)
        btn_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
    
    def populate_lang_list(self):
        """填充OCR语言包列表"""
        self.lang_list.clear()
        
        # 获取自定义的tessdata目录
        tessdata_dir = self.get_tessdata_dir()
        
        try:
            import pytesseract
            # 获取系统安装的语言包
            installed_langs = pytesseract.get_languages()
            self.main_window.status_queue.put(f"已检测到系统安装的语言包: {installed_langs}")
            
            # 检查自定义目录中的语言包
            custom_langs = []
            if os.path.exists(tessdata_dir):
                for file in os.listdir(tessdata_dir):
                    if file.endswith('.traineddata'):
                        lang_code = file.replace('.traineddata', '')
                        custom_langs.append(lang_code)
                self.main_window.status_queue.put(f"已检测到自定义目录的语言包: {custom_langs}")
            
            # 合并两个列表
            all_installed_langs = list(set(installed_langs + custom_langs))
            self.main_window.status_queue.put(f"所有可用的语言包: {all_installed_langs}")
            
        except Exception as e:
            all_installed_langs = []
            self.main_window.status_queue.put(f"获取已安装语言包失败: {e}")
        
        for code, name in SUPPORTED_LANGUAGES:
            ocr_code = OCR_LANG_MAP.get(code, "")
            if not ocr_code:
                self.main_window.status_queue.put(f"跳过语言 {code}: 无对应 OCR 代码")
                continue
            
            size = 20 if code in ['zh', 'ja', 'ko'] else (15 if code in ['ar', 'he'] else 5)
            
            item = QTreeWidgetItem(self.lang_list)
            item.setText(0, f"{name} ({code})")
            item.setText(1, ocr_code)
            item.setText(3, str(size))
            
            if ocr_code in all_installed_langs:
                item.setText(2, "已安装")
                item.setForeground(2, QColor(0, 128, 0))
            else:
                item.setText(2, "未安装")
                item.setForeground(2, QColor(255, 0, 0))
            
            item.setData(0, Qt.UserRole, ocr_code)

    def get_tessdata_dir(self):
        """获取 Tesseract tessdata 目录 - 优先使用环境变量TESSDATA_PREFIX"""
        # 如果环境变量TESSDATA_PREFIX已设置，则使用它
        if 'TESSDATA_PREFIX' in os.environ:
            tessdata_dir = os.environ['TESSDATA_PREFIX']
            try:
                os.makedirs(tessdata_dir, exist_ok=True)
                # 测试写入权限
                test_file = os.path.join(tessdata_dir, "test_write")
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
                self.main_window.status_queue.put(f"使用环境变量TESSDATA_PREFIX目录存储OCR语言包: {tessdata_dir}")
                return tessdata_dir
            except (OSError, IOError) as e:
                self.main_window.status_queue.put(f"环境变量TESSDATA_PREFIX目录不可写({e})，尝试其他目录")
        
        # 否则，使用原来的逻辑
        # 首先尝试获取应用程序所在目录
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 创建应用程序目录下的 tessdata 目录
        tessdata_dir = os.path.join(app_dir, "tessdata")
        
        # 检查应用程序目录是否可写
        try:
            os.makedirs(tessdata_dir, exist_ok=True)
            # 测试写入权限
            test_file = os.path.join(tessdata_dir, "test_write")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            
            self.main_window.status_queue.put(f"使用应用程序目录存储OCR语言包: {tessdata_dir}")
            return tessdata_dir
        except (OSError, IOError) as e:
            self.main_window.status_queue.put(f"应用程序目录不可写({e})，回退到系统目录")
            
            # 使用系统默认的 tessdata 目录
            try:
                import pytesseract
                default_dir = os.path.join(os.path.dirname(pytesseract.tesseract_cmd), "..", "tessdata")
                default_dir = os.path.abspath(default_dir)
                if os.path.exists(default_dir):
                    return default_dir
            except:
                pass
            
            # 如果无法获取默认目录，使用常见的系统目录
            system = platform.system()
            if system == "Linux":
                return "/usr/share/tesseract-ocr/5/tessdata"
            elif system == "Darwin":
                return "/usr/local/share/tessdata"
            else:  # Windows
                program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
                return os.path.join(program_files, "Tesseract-OCR", "tessdata")

    def install_ocr_language(self, ocr_code=None):
        """安装指定OCR语言包到自定义目录 - 使用线程避免卡死"""
        # 如果 ocr_code 未提供，从当前选中的项获取
        if ocr_code is None:
            selected_item = self.lang_list.currentItem()
            if not selected_item:
                self.main_window.status_queue.put("请先选择一个语言包")
                QMessageBox.warning(self, "错误", "请先从列表中选择一个语言包")
                return
            ocr_code = selected_item.data(0, Qt.UserRole)
        
        # 获取自定义的 tessdata 目录
        tessdata_dir = self.get_tessdata_dir()
        if not os.path.exists(tessdata_dir):
            try:
                os.makedirs(tessdata_dir, exist_ok=True)
            except OSError as e:
                self.main_window.status_queue.put(f"创建 tessdata 目录失败: {e}")
                QMessageBox.warning(self, "错误", f"无法创建 tessdata 目录: {e}")
                return
        
        # 设置 TESSDATA_PREFIX 环境变量
        os.environ['TESSDATA_PREFIX'] = tessdata_dir
        
        # 下载语言包文件
        download_url = f"https://github.com/tesseract-ocr/tessdata_best/raw/main/{ocr_code}.traineddata"
        output_path = os.path.join(tessdata_dir, f"{ocr_code}.traineddata")
        
        # 创建进度对话框
        self.progress_dialog = QProgressDialog(f"正在下载 {ocr_code}.traineddata...", "取消", 0, 100, self)
        self.progress_dialog.setWindowTitle("下载语言包")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)
        self.progress_dialog.canceled.connect(self.cancel_download)
        
        # 创建下载线程
        self.download_thread = QThread()
        self.download_worker = DownloadWorker(ocr_code, download_url, output_path)
        self.download_worker.moveToThread(self.download_thread)
        
        # 连接信号和槽
        self.download_thread.started.connect(self.download_worker.run)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.finished.connect(self.download_thread.quit)
        self.download_worker.finished.connect(self.download_worker.deleteLater)
        self.download_worker.progress.connect(self.progress_dialog.setValue)
        self.download_thread.finished.connect(self.download_thread.deleteLater)
        
        # 启动下载线程
        self.download_thread.start()
        self.progress_dialog.show()
    
    def cancel_download(self):
        """取消下载"""
        if hasattr(self, 'download_thread') and self.download_thread.isRunning():
            self.download_thread.terminate()
            self.download_thread.wait()
            self.main_window.status_queue.put("下载已取消")
            QMessageBox.information(self, "信息", "下载已取消")
    
    def on_download_finished(self, success, message, ocr_code):
        """下载完成处理"""
        # 断开取消信号连接，防止自动关闭时触发取消
        try:
            self.progress_dialog.canceled.disconnect()
        except:
            pass
        
        self.progress_dialog.close()
        
        if success:
            self.main_window.status_queue.put(message)
            QMessageBox.information(self, "成功", f"{ocr_code} OCR语言包安装成功")
        else:
            error_msg = f"下载 {ocr_code}.traineddata 失败: {message}"
            self.main_window.status_queue.put(error_msg)
            QMessageBox.warning(self, "下载失败", error_msg)
        
        # 刷新语言包列表
        self.populate_lang_list()
        
        # 刷新语言包列表
        self.populate_lang_list()
    
    def remove_ocr_lang(self):
        """删除选中的OCR语言包"""
        selected = self.lang_list.currentItem()
        if not selected:
            self.main_window.status_queue.put("请先选择一个语言包")
            QMessageBox.warning(self, "错误", "请先从列表中选择一个语言包")
            return
        
        ocr_code = selected.data(0, Qt.UserRole)
        
        # 获取自定义的 tessdata 目录
        tessdata_dir = self.get_tessdata_dir()
        lang_file = os.path.join(tessdata_dir, f"{ocr_code}.traineddata")
        
        if not os.path.exists(lang_file):
            self.main_window.status_queue.put(f"语言包文件不存在: {lang_file}")
            QMessageBox.warning(self, "错误", f"找不到语言包文件: {ocr_code}.traineddata")
            return
        
        try:
            # 尝试删除文件
            os.remove(lang_file)
            self.main_window.status_queue.put(f"已删除语言包: {ocr_code}.traineddata")
            QMessageBox.information(self, "成功", f"已删除语言包: {ocr_code}")
        except PermissionError:
            # 如果是权限问题，尝试使用管理员权限删除
            self.main_window.status_queue.put(f"权限不足，尝试使用管理员权限删除 {ocr_code}.traineddata")
            self._remove_with_sudo(lang_file, ocr_code)
        except Exception as e:
            error_msg = f"删除语言包失败: {e}"
            self.main_window.status_queue.put(error_msg)
            QMessageBox.warning(self, "删除失败", error_msg)
        
        # 刷新语言包列表
        self.populate_lang_list()
    
    def _remove_with_sudo(self, file_path, ocr_code):
        """使用管理员权限删除文件"""
        password_dialog = PasswordDialog(self, f"删除 {ocr_code}.traineddata")
        if password_dialog.exec_() != QDialog.Accepted:
            return
        
        password = password_dialog.get_password()
        if not password:
            return
        
        try:
            # 使用 sudo 删除文件
            command = f'echo "{password}" | sudo -S rm -f "{file_path}"'
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.main_window.status_queue.put(f"已使用管理员权限删除 {ocr_code}.traineddata")
                QMessageBox.information(self, "成功", f"已删除语言包: {ocr_code}")
            else:
                error_msg = f"使用管理员权限删除失败: {result.stderr}"
                self.main_window.status_queue.put(error_msg)
                QMessageBox.warning(self, "删除失败", error_msg)
                
        except Exception as e:
            error_msg = f"使用管理员权限删除时出错: {e}"
            self.main_window.status_queue.put(error_msg)
            QMessageBox.warning(self, "删除错误", error_msg)

class TesseractInstallTab(QWidget):
    """Tesseract OCR安装标签页"""
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.parent = parent
        self.main_window = main_window
        self.setup_ui()
        self.check_tesseract_installed()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        self.status_label = QLabel("状态: 检查中...")
        self.status_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.status_label)
        
        self.instructions = QTextEdit()
        self.instructions.setReadOnly(True)
        self.instructions.setFont(QFont("Arial", 10))
        layout.addWidget(self.instructions)
        
        # 按钮布局
        btn_layout = QHBoxLayout()

        # 安装按钮
        self.install_btn = QPushButton("安装Tesseract OCR")
        self.install_btn.clicked.connect(self.install_tesseract)
        btn_layout.addWidget(self.install_btn)

        # 卸载按钮
        self.uninstall_btn = QPushButton("卸载Tesseract OCR")
        self.uninstall_btn.clicked.connect(self.uninstall_tesseract)
        btn_layout.addWidget(self.uninstall_btn)

        # 验证按钮
        self.verify_btn = QPushButton("验证安装")
        self.verify_btn.clicked.connect(self.check_tesseract_installed)
        btn_layout.addWidget(self.verify_btn)

        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def check_tesseract_installed(self):
        """检查Tesseract是否安装"""
        try:
            result = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                version = version_line.split()[1]
                self.status_label.setText(f"状态: 已安装 (版本 {version})")
                self.status_label.setStyleSheet("color: green; font-weight: bold; font-size: 14px;")
                self.install_btn.setEnabled(False)
                self.instructions.setHtml("""
                    <h3>Tesseract OCR已安装</h3>
                    <p>您可以在OCR语言包标签页中安装和管理语言包。</p>
                """)
                return True
        except Exception:
            pass
        
        self.status_label.setText("状态: 未安装")
        self.status_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        self.install_btn.setEnabled(True)
        
        system = platform.system()
        if system == "Linux":
            # 使用SystemDetector获取更准确的系统信息
            sys_info = SystemDetector.get_system_info()
            pkg_manager = sys_info['package_manager']
            
            # 根据包管理器提供更具体的说明
            pkg_manager_names = {
                'apt': 'APT (Debian/Ubuntu)',
                'dnf': 'DNF (Fedora)',
                'yum': 'YUM (CentOS/RHEL)',  # 添加yum支持
                'pacman': 'Pacman (Arch Linux)',
                'zypper': 'Zypper (openSUSE)',  # 添加zypper支持
                'apk': 'APK (Alpine Linux)'
            }
            
            manager_name = pkg_manager_names.get(pkg_manager, '系统包管理器')
            
            self.instructions.setHtml(f"""
                <h3>在Linux上安装Tesseract OCR</h3>
                <p>检测到系统: {sys_info['distro'].upper()} (使用 {manager_name})</p>
                <p>点击下面的按钮安装Tesseract OCR。安装需要管理员权限。</p>
                <p>将使用 {pkg_manager} 包管理器进行安装。</p>
            """)
        elif system == "Windows":
            self.instructions.setHtml("""
                <h3>在Windows上安装Tesseract OCR</h3>
                <p>点击下面的按钮自动下载并安装 Tesseract OCR。</p>
            """)
        elif system == "Darwin":
            self.instructions.setHtml("""
                <h3>在macOS上安装Tesseract OCR</h3>
                <p>点击下面的按钮安装 Tesseract OCR。安装需要管理员权限。</p>
                <p>安装命令: <code>brew install tesseract</code></p>
            """)
        else:
            self.instructions.setHtml("""
                <h3>不支持的操作系统</h3>
                <p>您的操作系统不支持自动安装Tesseract OCR。</p>
                <p>请参考官方文档手动安装: <a href="https://github.com/tesseract-ocr/tesseract">https://github.com/tesseract-ocr/tesseract</a></p>
            """)
        
        return False
    
    def install_tesseract(self):
        """安装Tesseract OCR - 增强版，支持所有主流Linux发行版"""
        # 获取系统信息
        sys_info = SystemDetector.get_system_info()
        
        if sys_info['os_type'] == 'windows':
            # Windows手动安装提示
            QMessageBox.information(
                self, "Windows安装说明",
                "请从以下链接下载Tesseract安装程序:\n"
                "https://github.com/UB-Mannheim/tesseract/wiki\n\n"
                "安装时请确保勾选'Add to PATH'选项。"
            )
            return
        
        # Linux系统安装
        install_command = SystemDetector.get_tesseract_install_command()
        
        if not install_command:
            QMessageBox.warning(
                self, "不支持的系统",
                f"暂不支持自动安装在 {sys_info['distro']} 系统上。\n"
                f"请手动安装Tesseract OCR。"
            )
            return
        
        # 请求管理员权限
        password_dialog = PasswordDialog(self, "安装Tesseract OCR")
        if password_dialog.exec_() != QDialog.Accepted:
            return
        
        password = password_dialog.get_password()
        if not password:
            return
        
        self.main_window.status_queue.put(f"开始在 {sys_info['distro']} 上安装Tesseract OCR...")
        
        try:
            # 对于不同的包管理器，可能需要不同的预处理
            pkg_manager = sys_info['package_manager']
            
            if pkg_manager == 'apt':
                # 第一步：更新包列表
                update_process = subprocess.Popen(
                    ['sudo', '-S', 'apt-get', 'update'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                update_process.communicate(input=f"{password}\n", timeout=120)
                
                # 第二步：安装tesseract
                install_process = subprocess.Popen(
                    ['sudo', '-S', 'apt-get', 'install', 'tesseract-ocr', '-y'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout_output, stderr_output = install_process.communicate(input=f"{password}\n", timeout=300)
                return_code = install_process.returncode
            
            elif pkg_manager in ['dnf', 'yum']:
                # 对于dnf/yum，可能需要先启用EPEL仓库（CentOS/RHEL）
                if pkg_manager == 'yum' and sys_info['distro'] in ['centos', 'rhel']:
                    # 尝试安装EPEL仓库
                    epel_command = ['sudo', '-S', 'yum', 'install', 'epel-release', '-y']
                    epel_process = subprocess.Popen(
                        epel_command,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    epel_process.communicate(input=f"{password}\n", timeout=120)
                
                # 安装tesseract
                process = subprocess.Popen(
                    install_command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout_output, stderr_output = process.communicate(input=f"{password}\n", timeout=300)
                return_code = process.returncode
            
            else:
                # 其他包管理器（pacman, zypper, apk等）
                process = subprocess.Popen(
                    install_command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                stdout_output, stderr_output = process.communicate(input=f"{password}\n", timeout=300)
                return_code = process.returncode
            
            if return_code == 0:
                self.main_window.status_queue.put("Tesseract OCR安装成功")
                # 安装成功后，设置TESSDATA_PREFIX环境变量
                tessdata_dir = self.get_tessdata_dir()
                if tessdata_dir:
                    os.environ['TESSDATA_PREFIX'] = tessdata_dir
                    self.main_window.status_queue.put(f"设置TESSDATA_PREFIX={tessdata_dir}")
            else:
                error_msg = f"安装失败: {stderr_output if stderr_output else '未知错误'}"
                self.main_window.status_queue.put(error_msg)
                QMessageBox.warning(self, "安装失败", error_msg)
            
        except subprocess.TimeoutExpired:
            self.main_window.status_queue.put("安装超时，请检查网络连接")
            QMessageBox.warning(self, "安装超时", "安装过程超时，请检查网络连接")
            
        except Exception as e:
            error_msg = f"安装过程中出错: {e}"
            self.main_window.status_queue.put(error_msg)
            QMessageBox.warning(self, "安装错误", error_msg)
        
        # 重新检查安装状态
        self.check_tesseract_installed()

    def get_tessdata_dir(self):
        """获取 Tesseract tessdata 目录（与 OCRLanguageTab 共享） - 增强版"""
        # 首先尝试应用程序目录
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        
        app_tessdata_dir = os.path.join(app_dir, "tessdata")
        
        # 检查应用程序目录是否可写
        try:
            os.makedirs(app_tessdata_dir, exist_ok=True)
            test_file = os.path.join(app_tessdata_dir, "test_write")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            return app_tessdata_dir
        except (OSError, IOError):
            pass  # 应用程序目录不可写，继续尝试其他位置
        
        # 尝试获取系统默认的tessdata目录
        try:
            import pytesseract
            default_dir = os.path.join(os.path.dirname(pytesseract.tesseract_cmd), "..", "tessdata")
            default_dir = os.path.abspath(default_dir)
            if os.path.exists(default_dir):
                return default_dir
        except:
            pass
        
        # 根据系统类型提供默认目录
        system = platform.system()
        sys_info = SystemDetector.get_system_info()
        
        if system == "Windows":
            program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
            tessdata_dir = os.path.join(program_files, "Tesseract-OCR", "tessdata")
        elif system == "Linux":
            # 根据发行版提供不同的默认路径
            if sys_info['distro_family'] == 'debian':
                tessdata_dir = "/usr/share/tesseract-ocr/5/tessdata"
            elif sys_info['distro_family'] == 'redhat':
                tessdata_dir = "/usr/share/tesseract-ocr/tessdata"
            elif sys_info['distro_family'] == 'arch':
                tessdata_dir = "/usr/share/tessdata"
            elif sys_info['distro_family'] == 'suse':
                tessdata_dir = "/usr/share/tesseract-ocr/tessdata"
            else:
                tessdata_dir = "/usr/share/tesseract-ocr/tessdata"  # 通用路径
        elif system == "Darwin":
            tessdata_dir = "/usr/local/share/tessdata"
        else:
            tessdata_dir = os.path.expanduser("~/.tessdata")
        
        # 确保目录存在
        try:
            os.makedirs(tessdata_dir, exist_ok=True)
            return tessdata_dir
        except OSError as e:
            self.main_window.status_queue.put(f"错误: 无法创建 tessdata 目录 {tessdata_dir}: {e}")
            return None

    def uninstall_tesseract(self):
        """卸载Tesseract OCR"""
        # 创建自定义对话框让用户选择卸载方式
        dialog = QDialog(self)
        dialog.setWindowTitle("卸载选项")
        dialog.setFixedSize(400, 200)
        
        layout = QVBoxLayout(dialog)
        
        # 说明文字
        info_label = QLabel("请选择卸载方式:")
        info_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(info_label)
        
        # 选项1：仅卸载主程序
        self.uninstall_main_only = QRadioButton("仅卸载Tesseract主程序 (保留语言包)")
        self.uninstall_main_only.setChecked(True)
        layout.addWidget(self.uninstall_main_only)
        
        # 选项2：完全卸载
        self.uninstall_complete = QRadioButton("完全卸载 (包括所有语言包)")
        layout.addWidget(self.uninstall_complete)
        
        # 警告文字
        warning_label = QLabel("注意: 完全卸载将删除所有OCR语言包！")
        warning_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(warning_label)
        
        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        if dialog.exec_() != QDialog.Accepted:
            return
        
        # 根据用户选择执行相应的卸载
        complete_uninstall = self.uninstall_complete.isChecked()
        
        if complete_uninstall:
            self._perform_complete_uninstall()
        else:
            self._perform_main_uninstall()
    
    def _perform_main_uninstall(self):
        """执行主程序卸载"""
        # 获取系统信息
        sys_info = SystemDetector.get_system_info()
        
        if sys_info['os_type'] == 'windows':
            QMessageBox.information(
                self, "Windows卸载说明",
                "请通过控制面板卸载Tesseract OCR主程序"
            )
            return
        
        self._execute_uninstall_command(SystemDetector.get_tesseract_uninstall_command(), "Tesseract主程序")
    
    def _perform_complete_uninstall(self):
        """执行完全卸载"""
        # 获取系统信息
        sys_info = SystemDetector.get_system_info()
        
        if sys_info['os_type'] == 'windows':
            QMessageBox.information(
                self, "Windows完全卸载说明",
                "请手动删除以下内容:\n"
                "1. 卸载Tesseract主程序\n"
                "2. 删除安装目录下的tessdata文件夹\n"
                "3. 清理环境变量PATH中的Tesseract路径"
            )
            return
        
        # 获取完全卸载命令
        complete_uninstall_command = SystemDetector.get_complete_tesseract_uninstall_command()
        
        if not complete_uninstall_command:
            QMessageBox.warning(self, "错误", "无法获取完全卸载命令")
            return
        
        self._execute_uninstall_command(complete_uninstall_command, "Tesseract和所有语言包")
    
    def _execute_uninstall_command(self, command, description):
        """执行卸载命令的通用方法"""
        if not command:
            QMessageBox.warning(self, "不支持的系统", f"暂不支持自动卸载 {description}")
            return
        
        # 请求管理员权限
        password_dialog = PasswordDialog(self, f"卸载{description}")
        if password_dialog.exec_() != QDialog.Accepted:
            return
        
        password = password_dialog.get_password()
        if not password:
            return
        
        self.main_window.status_queue.put(f"开始卸载 {description}...")
        
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout_output, stderr_output = process.communicate(input=f"{password}\n", timeout=180)
            
            if process.returncode == 0:
                self.main_window.status_queue.put(f"{description} 卸载成功")
                QMessageBox.information(self, "卸载成功", f"{description} 已成功卸载")
            else:
                error_msg = f"卸载失败: {stderr_output if stderr_output else '未知错误'}"
                self.main_window.status_queue.put(error_msg)
                QMessageBox.warning(self, "卸载失败", error_msg)
            
        except Exception as e:
            error_msg = f"卸载过程中出错: {e}"
            self.main_window.status_queue.put(error_msg)
            QMessageBox.warning(self, "卸载错误", error_msg)
        
        # 重新检查安装状态
        self.check_tesseract_installed()

class SelectionOverlay(QWidget):
    """区域选择覆盖层，支持半透明效果"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 获取屏幕尺寸并设置全屏
        screen_geometry = QApplication.desktop().screenGeometry()
        self.setGeometry(0, 0, screen_geometry.width(), screen_geometry.height())
        
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.selection_rect = QRect()
        self.dragging = False
        self.show_size = True
        
        # 设置半透明效果
        self.setStyleSheet("background-color: rgba(0, 0, 0, 100);")
        
        # 添加提示标签
        self.info_label = QLabel("拖动鼠标选择屏幕字幕区域 (按 ESC 取消)", self)
        self.info_label.setStyleSheet("""
            background-color: #FFFF00;
            color: black;
            font-weight: bold;
            padding: 10px;
            border-radius: 5px;
        """)
        self.info_label.setFont(QFont("Arial", 16))
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.adjustSize()
        
        # 确保标签在屏幕中央
        self.update_label_position()
    
    def update_label_position(self):
        """更新标签位置到屏幕中央"""
        if self.info_label:
            self.info_label.move(
                (self.width() - self.info_label.width()) // 2, 
                50
            )
    
    def resizeEvent(self, event):
        """窗口大小改变时更新标签位置"""
        super().resizeEvent(event)
        self.update_label_position()

    
    def paintEvent(self, event):
        """绘制选择区域"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制半透明背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 100))
        
        if not self.selection_rect.isEmpty():
            # 绘制透明选择区域
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(self.selection_rect, Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            
            # 绘制选择框边框
            pen = QPen(Qt.red, 3, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.selection_rect)
            
            # 显示尺寸
            if self.show_size:
                width = self.selection_rect.width()
                height = self.selection_rect.height()
                size_text = f"{width} x {height}"
                
                font = QFont("Arial", 12, QFont.Bold)
                painter.setFont(font)
                painter.setPen(QPen(Qt.red))
                
                # 在矩形顶部居中显示尺寸
                text_rect = QFontMetrics(font).boundingRect(size_text)
                text_x = self.selection_rect.x() + (self.selection_rect.width() - text_rect.width()) // 2
                text_y = self.selection_rect.y() - 10
                
                if text_y < 30:  # 如果太靠近顶部，显示在矩形内部
                    text_y = self.selection_rect.y() + 20
                
                painter.drawText(text_x, text_y, size_text)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.selection_rect = QRect(self.start_point, self.end_point)
            self.update()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.dragging:
            self.end_point = event.pos()
            self.selection_rect = QRect(
                min(self.start_point.x(), self.end_point.x()),
                min(self.start_point.y(), self.end_point.y()),
                abs(self.start_point.x() - self.end_point.x()),
                abs(self.start_point.y() - self.end_point.y())
            )
            self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self.dragging:
            self.dragging = False
            
            # 确保选择区域足够大
            if self.selection_rect.width() > 10 and self.selection_rect.height() > 10:
                self.close()
            else:
                self.selection_rect = QRect()
                self.update()
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            self.selection_rect = QRect()
            self.close()

class TranslatorOverlay(QWidget):
    """翻译框覆盖层，显示在选定区域上，支持鼠标滚轮手动滚动"""
    def __init__(self, capture_rect, parent=None):
        super().__init__(parent)
        self.capture_rect = capture_rect
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 设置覆盖层位置和大小
        self.setGeometry(capture_rect)
        
        # 初始文本
        self.text = "双击翻译 | 右键隐藏翻译框"
        self.overlay_visible = True
        self.setWindowOpacity(0.2)  # 初始透明度
        
        # 设置跨平台兼容的字体 - 16px固定大小
        self.font = self.get_cross_platform_font(16)
        self.font.setBold(True)
        self.font_metrics = QFontMetrics(self.font)
        
        # 滚动相关属性
        self.scroll_offset = 0  # 垂直滚动偏移量
        self.scroll_step = 20   # 每次滚动的像素数
        
        # 文本显示相关
        self.text_lines = []  # 分割后的文本行
        self.line_height = self.font_metrics.height()
        self.text_rect = QRect()  # 文本显示区域
        self.total_text_height = 0  # 总文本高度
        self.visible_height = 0  # 可见区域高度
        self.max_scroll_offset = 0  # 最大滚动偏移量
        
        # 启用鼠标事件追踪
        self.setMouseTracking(True)
        
        if parent:
            parent.update_ui_signal.connect(self.handle_update_signal)
    
    def toggle_visibility(self):
        """切换翻译框可见性"""
        if self.isVisible():
            self.hide()  # 完全隐藏
        else:
            self.show()  # 显示
            self.setWindowOpacity(0.8)
    
    def mousePressEvent(self, event):
        """处理鼠标按下事件"""
        if event.button() == Qt.RightButton:
            # 右键点击切换可见性
            self.toggle_visibility()
            event.accept()  # 标记事件已处理
        else:
            super().mousePressEvent(event)
    
    def contextMenuEvent(self, event):
        """处理右键菜单事件（Windows上的备用方案）"""
        # 在Windows上，有时mousePressEvent可能不够，使用contextMenuEvent作为备用
        self.toggle_visibility()
        event.accept()
    
    def get_cross_platform_font(self, size):
        """获取跨平台兼容的字体，优先选择平台特定的字体"""
        system = platform.system()
        
        # 平台特定的字体优先级
        font_families = {
            "Windows": [
                "Segoe UI",         # Windows 10/11 默认字体，优化多语言支持
                "Arial",            # Windows 常见字体
                "Noto Sans CJK SC", # 中日韩支持
                "sans-serif"        # 通用后备
            ],
            "Linux": [
                "DejaVu Sans",      # Linux 常见字体
                "Liberation Sans",  # Linux 开源字体
                "Ubuntu",           # Ubuntu 系统
                "Noto Sans CJK SC", # 中日韩支持
                "sans-serif"        # 通用后备
            ],
            "Darwin": [
                "Helvetica",        # macOS 默认字体
                "Arial",            # macOS 常见字体
                "Noto Sans CJK SC", # 中日韩支持
                "sans-serif"        # 通用后备
            ]
        }.get(system, [
            "Noto Sans CJK SC", # 默认中日韩支持
            "Arial",            # 跨平台常见
            "Helvetica",        # 跨平台常见
            "sans-serif"        # 通用后备
        ])
        
        for family in font_families:
            font = QFont(family, size)
            font.setWeight(QFont.Normal)
            # 测试字体是否可用
            if QFontMetrics(font).width("测试") > 0:
                if hasattr(self, 'main_window') and hasattr(self.main_window, 'status_queue'):
                    self.main_window.status_queue.put(f"选择字体: {family}")
                return font
        
        # 如果都不可用，使用系统默认字体
        font = QFont()
        font.setPointSize(size)
        if hasattr(self, 'main_window') and hasattr(self.main_window, 'status_queue'):
            self.main_window.status_queue.put("所有字体不可用，使用系统默认字体")
        return font
    
    def handle_update_signal(self, status_text, overlay_text):
        """处理主窗口发送的更新信号"""
        # 更新显示文本
        self.text = overlay_text
        self.prepare_text_display()
        self.setWindowOpacity(0.8)  # 确保结果可见
        self.overlay_visible = True
        self.update()
    
    def prepare_text_display(self):
        """准备文本显示，计算滚动参数"""
        # 计算文本显示区域（减去边距）
        self.text_rect = self.rect().adjusted(15, 15, -15, -15)
        self.visible_height = self.text_rect.height()
        
        # 将文本按行分割
        self.text_lines = self.wrap_text(self.text, self.text_rect.width())
        
        # 计算总文本高度
        self.total_text_height = len(self.text_lines) * self.line_height
        
        # 计算最大滚动偏移量
        self.max_scroll_offset = max(0, self.total_text_height - self.visible_height)
        
        # 重置滚动位置
        self.scroll_offset = 0
    
    def wrap_text(self, text, width):
        """将文本按指定宽度换行，并保留原始换行符"""
        if not text:
            return []
    
        lines = []
        paragraphs = text.splitlines()  # 保留原始段落分行
    
        for para in paragraphs:
            words = para.split()
            current_line = ""
            for word in words:
                test_line = current_line + (" " if current_line else "") + word
                line_width = self.font_metrics.width(test_line)
    
                if line_width <= width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    # 如果单词太长，字符级别分行
                    if self.font_metrics.width(word) > width:
                        lines.extend(self.break_long_word(word, width))
                        current_line = ""
                    else:
                        current_line = word
    
            if current_line:
                lines.append(current_line)
    
            lines.append("")  # 段落之间添加空行
    
        return lines if lines else [""]
    
    def break_long_word(self, word, width):
        """将过长的单词按字符分割"""
        lines = []
        current_line = ""
        
        for char in word:
            test_line = current_line + char
            if self.font_metrics.width(test_line) <= width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                    current_line = char
                else:
                    # 如果单个字符都太宽，强制添加
                    lines.append(char)
        
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def wheelEvent(self, event):
        """鼠标滚轮事件 - 手动滚动"""
        if self.max_scroll_offset <= 0:
            # 文本不需要滚动
            return
            
        # 获取滚轮滚动方向
        delta = event.angleDelta().y()
        
        if delta > 0:
            # 向上滚动
            self.scroll_offset = max(0, self.scroll_offset - self.scroll_step)
        else:
            # 向下滚动
            self.scroll_offset = min(self.max_scroll_offset, self.scroll_offset + self.scroll_step)
        
        self.update()
    
    def paintEvent(self, event):
        """绘制覆盖层内容"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制半透明背景
        painter.fillRect(self.rect(), QColor(0, 0, 0, 250))
        
        # 绘制边框
        pen = QPen(QColor(255, 85, 85), 2, Qt.DashLine)
        painter.setPen(pen)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
        
        # 绘制文本
        painter.setFont(self.font)
        painter.setPen(QPen(Qt.white))
        
        # 设置裁剪区域，确保文本不会超出边界
        painter.setClipRect(self.text_rect)
        
        # 如果文本行为空，处理简单文本显示
        if not self.text_lines:
            painter.drawText(self.text_rect, Qt.AlignCenter | Qt.TextWordWrap, self.text)
            return
        
        # 绘制滚动文本
        y_position = self.text_rect.top() - self.scroll_offset
        
        for line in self.text_lines:
            # 只绘制在可见区域内的文本行
            if y_position + self.line_height > self.text_rect.top() and y_position < self.text_rect.bottom():
                painter.drawText(self.text_rect.left(), y_position + self.font_metrics.ascent(), line)
            
            y_position += self.line_height
            
            # 如果已经超出可见区域下方，可以停止绘制
            if y_position > self.text_rect.bottom() + self.line_height:
                break
        
        # 绘制滚动指示器（如果需要滚动）
        if self.max_scroll_offset > 0:
            self.draw_scroll_indicator(painter)
    
    def draw_scroll_indicator(self, painter):
        """绘制滚动指示器"""
        # 计算滚动条位置和大小
        scrollbar_width = 4
        scrollbar_x = self.rect().right() - scrollbar_width - 5
        scrollbar_top = self.text_rect.top()
        scrollbar_height = self.text_rect.height()
        
        # 绘制滚动条背景
        painter.setPen(QPen(QColor(100, 100, 100, 100)))
        painter.drawRect(scrollbar_x, scrollbar_top, scrollbar_width, scrollbar_height)
        
        # 计算滚动指示器位置
        if self.max_scroll_offset > 0:
            indicator_height = max(10, scrollbar_height * self.visible_height // self.total_text_height)
            indicator_y = scrollbar_top + (scrollbar_height - indicator_height) * self.scroll_offset // self.max_scroll_offset
            
            # 绘制滚动指示器
            painter.fillRect(scrollbar_x, int(indicator_y), scrollbar_width, int(indicator_height), QColor(255, 255, 255, 150))
    
    def mouseDoubleClickEvent(self, event):
        """双击事件 - 执行翻译"""
        if event.button() == Qt.LeftButton:
            # 更新文本为"正在翻译..."
            self.text = "正在翻译..."
            self.text_lines = []  # 清空文本行，使用简单显示
            self.scroll_offset = 0  # 重置滚动
                
            # 增加透明度使其更可见
            self.setWindowOpacity(0.8)
            # 强制立即重绘界面
            self.update()
            # 确保界面更新完成
            QApplication.processEvents()
                
            # 使用QTimer在主线程中执行翻译
            QTimer.singleShot(0, self.parent().process_translation)
    
    
    def enterEvent(self, event):
        """鼠标进入事件 - 增加透明度"""
        if self.overlay_visible:
            self.setWindowOpacity(0.8)
            self.update()
    
    def leaveEvent(self, event):
        """鼠标离开事件 - 恢复低透明度"""
        if self.overlay_visible and self.text != "正在翻译..." and not self.text.startswith("翻译结果"):
            self.setWindowOpacity(0.2)
            self.update()
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        # 重新计算文本显示
        if self.text:
            self.prepare_text_display()
    
    def set_scroll_step(self, step):
        """设置滚动步长"""
        self.scroll_step = max(5, step)
    
    def reset_scroll(self):
        """重置滚动位置到顶部"""
        self.scroll_offset = 0
        self.update()
    
    def update_font_size(self):
        """保持与原有代码兼容的方法 - 现在用于重新准备文本显示"""
        self.prepare_text_display()
        self.update()

class ScreenTranslator(QMainWindow):
    # 定义线程安全的UI更新信号
    update_ui_signal = QtCore.pyqtSignal(str, str)
    # 新增信号用于安全更新文本编辑框
    update_text_edit_signal = QtCore.pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        
        # 确定应用程序目录
        if getattr(sys, 'frozen', False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Windows 专用设置
        if platform.system() == "Windows":
            # 始终使用用户目录存储OCR语言包
            user_tessdata_dir = os.path.join(os.environ['LOCALAPPDATA'], "SkylarkTranslator", "tessdata")
            os.makedirs(user_tessdata_dir, exist_ok=True)
            os.environ['TESSDATA_PREFIX'] = user_tessdata_dir
            print(f"Windows: 使用用户目录存储OCR语言包: {user_tessdata_dir}")
                
        else:
            # 非 Windows 系统使用原有逻辑
            tessdata_dir = os.path.join(app_dir, "tessdata")
            os.makedirs(tessdata_dir, exist_ok=True)
            os.environ['TESSDATA_PREFIX'] = tessdata_dir
            print(f"设置 Tesseract 数据目录: {tessdata_dir}")
        
        self.capture_area = None
        self.translator_overlay = None
        self.translation_in_progress = False
        self.translation_ready = True  # 在线翻译总是就绪
        
        # 添加全局鼠标监听相关属性
        self.global_mouse_listener = None
        self.overlay_hidden = False  # 跟踪翻译框的隐藏状态
        
        self.status_queue = queue.Queue()
        
        # 只保留在线翻译器
        self.online_translator = OnlineTranslator()
        
        self.init_ui()
        self.init_global_mouse_listener()
        
        # 设置窗口属性
        self.setWindowTitle("Skylark Translation V3.1 - 在线版扫描屏幕翻译软件")
        self.setup_cross_platform_window_size()  # 新增方法

        # Windows特定的DPI缩放处理
        if platform.system() == "Windows":
            self.setup_windows_dpi_scaling()
        
        # 窗口激活状态跟踪
        self.is_active = True
        
        # 连接信号
        self.update_text_edit_signal.connect(self.safe_append_translation)
        self.update_ui_signal.connect(self._update_ui_slot)
        # 添加线程锁
        self.translation_lock = Lock()
        # 添加图标
        self.setWindowIcon(QIcon("skylark.png"))

        # 添加点击时间跟踪
        self.last_right_click_time = 0
        self.click_delay = 0.3  # 300毫秒的点击延迟

    def init_global_mouse_listener(self):
        """初始化全局鼠标监听器"""
        if PYNPUT_AVAILABLE:
            try:
                self.global_mouse_listener = mouse.Listener(on_click=self.on_global_mouse_click)
                self.global_mouse_listener.start()
                print("全局鼠标监听器已启动")
            except Exception as e:
                print(f"启动全局鼠标监听器失败: {e}")
                self.global_mouse_listener = None
        else:
            print("pynput不可用，全局右键监听功能禁用")

    def on_global_mouse_click(self, x, y, button, pressed):
        """全局鼠标点击事件处理 - 使用事件ID防止重复处理"""
        current_time = time.time()
        
        # 只在鼠标按下时处理，避免按下和释放都被处理
        if button == mouse.Button.right and pressed:
            # 检查点击延迟
            if current_time - self.last_right_click_time < self.click_delay:
                print(f"忽略快速点击: {current_time - self.last_right_click_time:.3f}s")
                return  # 忽略快速连续点击
            
            self.last_right_click_time = current_time
            print(f"处理右键点击: ({x}, {y}), pressed: {pressed}")
            
            # 如果翻译框不存在，直接返回
            if not self.translator_overlay:
                print("翻译框不存在，忽略点击")
                return
                
            # 获取翻译框的位置信息
            overlay_rect = self.translator_overlay.geometry()
            
            print(f"覆盖层位置: {overlay_rect.x()}, {overlay_rect.y()}, {overlay_rect.width()}x{overlay_rect.height()}")
            print(f"覆盖层状态: {'显示' if not self.overlay_hidden else '隐藏'}")
            
            # 检查点击是否在覆盖层区域内
            click_in_overlay = (
                overlay_rect.x() <= x <= overlay_rect.x() + overlay_rect.width() and
                overlay_rect.y() <= y <= overlay_rect.y() + overlay_rect.height()
            )
            
            print(f"点击在覆盖层内: {click_in_overlay}")
            
            # 只在点击在覆盖层内时才切换状态
            if click_in_overlay:
                # 使用事件ID确保只处理一次
                event_id = f"{x}_{y}_{current_time}"
                if not hasattr(self, '_last_event_id') or self._last_event_id != event_id:
                    self._last_event_id = event_id
                    QTimer.singleShot(0, self.toggle_overlay_visibility)
    
    def handle_right_click(self, click_in_overlay):
        """在主线程中处理右键点击，避免竞态条件"""
        try:
            if click_in_overlay:
                # 点击在覆盖层上，切换隐藏状态
                print("切换覆盖层显示状态")
                self.toggle_overlay_visibility()
            elif self.overlay_hidden:
                # 覆盖层已隐藏，且点击在覆盖层外部，显示覆盖层
                print("显示覆盖层")
                self.show_overlay()
            else:
                print("点击在覆盖层外部，但覆盖层已显示，不执行操作")
        except Exception as e:
            print(f"处理右键点击时出错: {e}")

    def toggle_overlay_visibility(self):
        """切换翻译框显示/隐藏状态"""
        try:
            if self.overlay_hidden:
                self.show_overlay()
            else:
                self.hide_overlay()
        except Exception as e:
            print(f"切换翻译框状态时出错: {e}")
        finally:
            # 确保处理标志被重置
            self._processing_click = False
    
    def hide_overlay(self):
        """完全隐藏翻译框 - 线程安全版"""
        if self.translator_overlay and not self.overlay_hidden:
            try:
                self.translator_overlay.hide()
                self.overlay_hidden = True
                self.update_status("翻译框已隐藏 (右键任意位置可唤醒)")
                print("翻译框已隐藏")
            except Exception as e:
                print(f"隐藏翻译框时出错: {e}")
    
    def show_overlay(self):
        """显示翻译框 - 线程安全版"""
        if self.translator_overlay and self.overlay_hidden:
            try:
                self.translator_overlay.show()
                self.translator_overlay.setWindowOpacity(0.8)
                self.overlay_hidden = False
                self.update_status("翻译框已显示")
                print("翻译框已显示")
            except Exception as e:
                print(f"显示翻译框时出错: {e}")

    def safe_append_translation(self, text):
        """线程安全的文本添加方法"""
        self.result_text.append(text)
        self.result_text.verticalScrollBar().setValue(self.result_text.verticalScrollBar().maximum())

    def _update_ui_slot(self, status_text, overlay_text):
        """线程安全的UI更新槽函数"""
        self.update_status(status_text)
        self.update_overlay_text(overlay_text)

    def init_ui(self):
        """初始化用户界面"""
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # 🆕 翻译引擎选择区域
        engine_group = QGroupBox("翻译引擎设置")
        engine_layout = QVBoxLayout()
        
        engine_type_layout = QHBoxLayout()
        
        self.online_radio = QRadioButton("在线翻译")
        self.online_radio.setChecked(True)
        self.online_radio.setEnabled(False)  # 禁用选择，因为现在只有在线翻译
        engine_type_layout.addWidget(self.online_radio)
        
        engine_layout.addLayout(engine_type_layout)
        
        online_engine_layout = QHBoxLayout()
        online_engine_layout.addWidget(QLabel("在线引擎:"))
        
        self.online_engine_combo = QComboBox()
        available_engines = self.online_translator.get_available_translators()
        engine_names = {
            'google': 'Google翻译',
            'deepl': 'DeepL翻译',
            'baidu': '百度翻译',
            'microsoft': '微软翻译'
        }
        
        for engine in available_engines:
            self.online_engine_combo.addItem(engine_names.get(engine, engine), engine)
        
        self.online_engine_combo.currentTextChanged.connect(self.on_online_engine_changed)
        online_engine_layout.addWidget(self.online_engine_combo)
        
        self.api_settings_btn = QPushButton("API设置")
        self.api_settings_btn.clicked.connect(self.configure_api_settings)
        online_engine_layout.addWidget(self.api_settings_btn)
        
        engine_layout.addLayout(online_engine_layout)
        engine_group.setLayout(engine_layout)
        main_layout.addWidget(engine_group)
        
        control_layout = QHBoxLayout()
        
        self.select_area_btn = QPushButton("选择翻译区域")
        self.select_area_btn.clicked.connect(self.select_capture_area_interactive)
        control_layout.addWidget(self.select_area_btn)
        
        self.lang_btn = QPushButton("设置语言")
        self.lang_btn.clicked.connect(self.configure_languages)
        control_layout.addWidget(self.lang_btn)
        
        self.toggle_overlay_btn = QPushButton("隐藏/显示翻译框")
        self.toggle_overlay_btn.clicked.connect(self.toggle_overlay_visibility)
        control_layout.addWidget(self.toggle_overlay_btn)
        
        # 语言包管理按钮
        self.lang_pack_btn = QPushButton("语言包管理")
        self.lang_pack_btn.clicked.connect(self.manage_language_packs)
        control_layout.addWidget(self.lang_pack_btn)
        
        self.quit_btn = QPushButton("退出")
        self.quit_btn.clicked.connect(self.close)
        control_layout.addWidget(self.quit_btn)
        
        main_layout.addLayout(control_layout)
        
        self.status_label = QLabel("正在准备...")
        self.status_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(self.status_label)
        
        result_group = QGroupBox("翻译历史记录")
        result_layout = QVBoxLayout()
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Arial", 10))
        result_layout.addWidget(self.result_text)
        
        self.clear_btn = QPushButton("清空历史")
        self.clear_btn.clicked.connect(self.clear_results)
        result_layout.addWidget(self.clear_btn)
        
        result_group.setLayout(result_layout)
        main_layout.addWidget(result_group)
        
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.check_status_queue)
        self.status_timer.start(500)
        
        self.activation_timer = QTimer(self)
        self.activation_timer.timeout.connect(self.check_window_activation)
        self.activation_timer.start(1000)
        
        # 移除离线翻译相关初始化
        self.update_status("在线翻译已就绪！双击选择框进行翻译。")

    def on_online_engine_changed(self):
        current_engine = self.online_engine_combo.currentData()
        if current_engine:
            self.online_translator.set_translator(current_engine)
            engine_name = self.online_engine_combo.currentText()
            self.update_status(f"已切换到 {engine_name}")

    def configure_api_settings(self):
        current_engine = self.online_engine_combo.currentData()
        engine_name = self.online_engine_combo.currentText()
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{engine_name} API设置")
        dialog.setFixedSize(400, 200)
        
        layout = QVBoxLayout(dialog)
        
        if current_engine == 'deepl':
            layout.addWidget(QLabel("DeepL API密钥:"))
            api_key_input = QLineEdit()
            api_key_input.setPlaceholderText("输入您的DeepL API密钥")
            layout.addWidget(api_key_input)
            
            def save_deepl_settings():
                api_key = api_key_input.text().strip()
                if api_key:
                    self.online_translator.translators['deepl'].set_api_key(api_key)
                    QMessageBox.information(dialog, "成功", "DeepL API密钥已保存")
                    dialog.accept()
                else:
                    QMessageBox.warning(dialog, "警告", "请输入有效的API密钥")
            
            save_btn = QPushButton("保存")
            save_btn.clicked.connect(save_deepl_settings)
            layout.addWidget(save_btn)
            
        elif current_engine == 'baidu':
            layout.addWidget(QLabel("百度翻译设置:"))
            layout.addWidget(QLabel("APP ID:"))
            app_id_input = QLineEdit()
            layout.addWidget(app_id_input)
            
            layout.addWidget(QLabel("密钥:"))
            secret_key_input = QLineEdit()
            secret_key_input.setEchoMode(QLineEdit.Password)
            layout.addWidget(secret_key_input)
            
            def save_baidu_settings():
                app_id = app_id_input.text().strip()
                secret_key = secret_key_input.text().strip()
                if app_id and secret_key:
                    self.online_translator.translators['baidu'].set_credentials(app_id, secret_key)
                    QMessageBox.information(dialog, "成功", "百度翻译API设置已保存")
                    dialog.accept()
                else:
                    QMessageBox.warning(dialog, "警告", "请输入完整的API信息")
            
            save_btn = QPushButton("保存")
            save_btn.clicked.connect(save_baidu_settings)
            layout.addWidget(save_btn)
            
        elif current_engine == 'microsoft':
            layout.addWidget(QLabel("微软翻译设置:"))
            layout.addWidget(QLabel("API密钥:"))
            api_key_input = QLineEdit()
            layout.addWidget(api_key_input)
            
            layout.addWidget(QLabel("区域 (可选):"))
            region_input = QLineEdit()
            region_input.setPlaceholderText("例如: eastus")
            layout.addWidget(region_input)
            
            def save_microsoft_settings():
                api_key = api_key_input.text().strip()
                region = region_input.text().strip() or "global"
                if api_key:
                    self.online_translator.translators['microsoft'].set_credentials(api_key, region)
                    QMessageBox.information(dialog, "成功", "微软翻译API设置已保存")
                    dialog.accept()
                else:
                    QMessageBox.warning(dialog, "警告", "请输入有效的API密钥")
            
            save_btn = QPushButton("保存")
            save_btn.clicked.connect(save_microsoft_settings)
            layout.addWidget(save_btn)
            
        else:  # Google翻译
            layout.addWidget(QLabel("Google翻译使用免费服务，无需API密钥。"))
            layout.addWidget(QLabel("如果遇到访问问题，请检查网络连接。"))
            
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
        
        dialog.exec_()

    def check_status_queue(self):
        try:
            while not self.status_queue.empty():
                message = self.status_queue.get_nowait()
                # 不再处理离线翻译的状态消息
        except queue.Empty:
            pass

    def check_window_activation(self):
        if self.isMinimized():
            return
        if not self.isActiveWindow() and self.is_active:
            if not self.isMinimized():
                self.is_active = False
                self.update_status("窗口失去焦点，正在尝试恢复...")
                self.restore_window()
        elif self.isActiveWindow() and not self.is_active:
            self.is_active = True
            self.update_status("窗口焦点已恢复")

    def restore_window(self):
        if self.isMinimized():
            return
        if not self.isActiveWindow():
            self.show()
            self.raise_()
            self.activateWindow()
            if self.windowState() & Qt.WindowMinimized:
                self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
            QApplication.processEvents()

    def update_status(self, text):
        self.status_label.setText(text)

    def clear_results(self):
        self.result_text.clear()

    def append_translation(self, text):
        timestamp = time.strftime("[%H:%M:%S]")
        full_text = f"{timestamp}\n{text}\n"
        self.update_text_edit_signal.emit(full_text)

    def select_capture_area_interactive(self):
        QTimer.singleShot(100, self.hide)
        self.selection_overlay = SelectionOverlay()
        self.selection_overlay.showMaximized()
        self.selection_overlay.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.selection_overlay and event.type() == QEvent.Close:
            self.on_selection_complete()
            return True
        return super().eventFilter(obj, event)

    def on_selection_complete(self):
        try:
            with self.translation_lock:
                if hasattr(self.selection_overlay, 'selection_rect') and not self.selection_overlay.selection_rect.isEmpty():
                    rect = self.selection_overlay.selection_rect
                    self.capture_area = (rect.x(), rect.y(), rect.x() + rect.width(), rect.y() + rect.height())
                    self.update_status(f"已选择区域: {self.capture_area}")
                    self.create_translator_overlay()
            self.show()
            self.restore_window()
            QApplication.processEvents()
            QTimer.singleShot(100, lambda: self.setFocus(Qt.ActiveWindowFocusReason))
        except Exception as e:
            import traceback
            self.update_status(f"选择完成错误: {e}\n{traceback.format_exc()}")
            self.show()

    def create_translator_overlay(self):
        if self.translator_overlay:
            try:
                self.update_ui_signal.disconnect(self.translator_overlay.handle_update_signal)
            except TypeError:
                pass
            self.translator_overlay.deleteLater()
            self.translator_overlay = None
        if self.capture_area:
            x1, y1, x2, y2 = self.capture_area
            rect = QRect(x1, y1, x2 - x1, y2 - y1)
            self.translator_overlay = TranslatorOverlay(rect, self)
            self.update_ui_signal.connect(self.translator_overlay.handle_update_signal)
            self.translator_overlay.show()
            self.overlay_hidden = False

    def close_overlay(self):
        if self.translator_overlay:
            try:
                self.update_ui_signal.disconnect(self.translator_overlay.handle_update_signal)
            except TypeError:
                pass
            self.translator_overlay.close()
            self.translator_overlay.deleteLater()
            self.translator_overlay = None
            self.overlay_hidden = False
            self.update_status("翻译框已关闭")

    def configure_languages(self):
        global SOURCE_LANG, TARGET_LANG
        
        # 获取可用的语言列表
        available_languages = SUPPORTED_LANGUAGES
        
        dialog = QDialog(self)
        dialog.setWindowTitle("选择语言")
        dialog.setFixedSize(300, 200)
        
        layout = QVBoxLayout(dialog)
        src_label = QLabel("源语言:")
        src_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(src_label)
        
        src_combo = QComboBox()
        for code, name in available_languages:
            src_combo.addItem(f"{code} - {name}", code)
        src_combo.setCurrentText(f"{SOURCE_LANG} - {self.get_language_name(SOURCE_LANG)}")
        layout.addWidget(src_combo)
        
        tgt_label = QLabel("目标语言:")
        tgt_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(tgt_label)
        
        tgt_combo = QComboBox()
        for code, name in available_languages:
            tgt_combo.addItem(f"{code} - {name}", code)
        tgt_combo.setCurrentText(f"{TARGET_LANG} - {self.get_language_name(TARGET_LANG)}")
        layout.addWidget(tgt_combo)
        
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)
        
        if dialog.exec_() == QDialog.Accepted:
            with self.translation_lock:
                SOURCE_LANG = src_combo.currentData()
                TARGET_LANG = tgt_combo.currentData()
                lang_map = {"ja": "jpn", "en": "eng", "zh": "chi_sim", "ko": "kor", "ms": "msa"}
                ocr_lang = lang_map.get(SOURCE_LANG, "eng")
                self.update_status(f"语言设置已更新: 源语言={SOURCE_LANG}, 目标语言={TARGET_LANG}, OCR语言={ocr_lang}, 翻译模式=在线")

    def get_language_name(self, code):
        for lang_code, lang_name in SUPPORTED_LANGUAGES:
            if lang_code == code:
                return lang_name
        return code

    def preprocess_image(self, image):
        try:
            if image.mode != 'L':
                image = image.convert('L')
            np_img = np.array(image, dtype=np.uint8)
            mean_brightness = np.mean(np_img)
            std_brightness = np.std(np_img)
            
            # 动态调整预处理策略
            if std_brightness < 25:  # 低对比度图像
                p_low, p_high = np.percentile(np_img, (5, 95))
                np_img = np.clip((np_img - p_low) * 255.0 / (p_high - p_low), 0, 255).astype(np.uint8)
                # 使用更大的 block_size 以适应更多场景
                block_size = max(15, int(min(np_img.shape[:2]) * 0.1)) | 1
                thresh_img = cv2.adaptiveThreshold(np_img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, 5)
            elif mean_brightness < 50 or mean_brightness > 200:  # 过暗或过亮
                thresh_img = cv2.equalizeHist(np_img)
                # 适度去噪，保持细节
                thresh_img = cv2.fastNlMeansDenoising(thresh_img, None, 7, 7, 21)
            else:  # 正常光照
                _, thresh_img = cv2.threshold(np_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 调整形态学操作，增强字符连接
            kernel = np.ones((2, 2), np.uint8)  # 恢复到 (2, 2) 以连接字符
            thresh_img = cv2.morphologyEx(thresh_img, cv2.MORPH_CLOSE, kernel)
            # 恢复适当的锐化，增强边缘
            thresh_img = cv2.filter2D(thresh_img, -1, np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]]))
            
            del np_img  # 释放原始数组
            return Image.fromarray(thresh_img)
        except Exception as e:
            print(f"高级处理失败: {e}, 使用回退方案")
            return image

    def capture_screen_region(self):
        """截图方法 - 改进版，不隐藏翻译框"""
        if not self.capture_area:
            print("错误：尚未选择截图区域。")
            self.update_status("错误：尚未选择截图区域")
            return None
        
        try:
            # 不再隐藏翻译框，而是设置其为完全透明
            if self.translator_overlay:
                # 保存当前透明度
                current_opacity = self.translator_overlay.windowOpacity()
                # 设置为完全透明
                self.translator_overlay.setWindowOpacity(0.0)
                # 强制立即重绘
                self.translator_overlay.repaint()
                QApplication.processEvents()
            
            # 短暂延迟确保透明度生效
            time.sleep(0.05)
            
            # 截图
            image = ImageGrab.grab(bbox=self.capture_area, all_screens=True)
            image = image.convert('RGB').convert('L')
            
            # 恢复翻译框透明度
            if self.translator_overlay:
                self.translator_overlay.setWindowOpacity(current_opacity)
                self.translator_overlay.repaint()
            
            return image
        except Exception as e:
            print(f"截图失败: {e}")
            self.update_status(f"截图失败: {e}")
            
            # 确保翻译框透明度恢复
            if self.translator_overlay:
                self.translator_overlay.setWindowOpacity(0.8)
                self.translator_overlay.repaint()
            
            return None

    def check_ocr_language_support(self, lang_code):
        """检查OCR语言支持情况"""
        # 使用全局的OCR_LANG_MAP而不是硬编码的映射
        ocr_code = OCR_LANG_MAP.get(lang_code)
        
        if not ocr_code:
            return False, f"语言 {lang_code} 没有对应的OCR语言包"
        
        # 检查是否已安装该语言包
        try:
            installed_langs = pytesseract.get_languages()
            if ocr_code not in installed_langs:
                return False, f"OCR语言包 {ocr_code} 未安装"
            return True, f"OCR语言包 {ocr_code} 已安装"
        except Exception as e:
            return False, f"检查OCR语言包时出错: {e}"
    
    def ensure_ocr_language_installed(self, lang_code):
        """确保OCR语言包已安装"""
        ocr_code = OCR_LANG_MAP.get(lang_code)
        if not ocr_code:
            return False, f"语言 {lang_code} 没有对应的OCR语言包"
        
        try:
            installed_langs = pytesseract.get_languages()
            if ocr_code in installed_langs:
                return True, f"OCR语言包 {ocr_code} 已安装"
            
            # 语言包未安装，尝试安装
            self.update_status(f"正在安装OCR语言包: {ocr_code}")
            
            # 获取系统信息
            sys_info = SystemDetector.get_system_info()
            
            if sys_info['os_type'] == 'windows':
                # Windows需要手动安装
                return False, f"请在Windows上手动安装 {ocr_code} OCR语言包"
            
            # 获取安装命令
            install_cmd = SystemDetector.get_ocr_language_command(ocr_code, 'install')
            if not install_cmd:
                return False, f"无法获取 {ocr_code} 语言包的安装命令"
            
            # 请求管理员权限
            password_dialog = PasswordDialog(self, f"安装 {ocr_code} OCR语言包")
            if password_dialog.exec_() != QDialog.Accepted:
                return False, "用户取消安装"
            
            password = password_dialog.get_password()
            if not password:
                return False, "未提供密码"
            
            # 执行安装命令
            process = subprocess.Popen(
                install_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout_output, stderr_output = process.communicate(input=f"{password}\n", timeout=300)
            
            if process.returncode == 0:
                return True, f"成功安装 {ocr_code} OCR语言包"
            else:
                return False, f"安装 {ocr_code} OCR语言包失败: {stderr_output}"
        
        except Exception as e:
            return False, f"安装OCR语言包时出错: {e}"
    
    def ocr_image(self, image):
        """OCR识别图像文本 - 增强版，支持语言检查和自动安装"""
        if image is None:
            return ""
        
        try:
            # 检查语言支持
            supported, message = self.check_ocr_language_support(SOURCE_LANG)
            
            if not supported:
                # 尝试安装语言包
                installed, install_message = self.ensure_ocr_language_installed(SOURCE_LANG)
                
                if not installed:
                    # 安装失败，使用英语作为后备
                    self.update_status(f"{install_message}，使用英语OCR作为后备")
                    ocr_lang = "eng"
                else:
                    # 安装成功，使用安装的语言
                    ocr_lang = OCR_LANG_MAP[SOURCE_LANG]
            else:
                # 语言已支持，直接使用
                ocr_lang = OCR_LANG_MAP[SOURCE_LANG]
            
            print(f"OCR 使用语言: {ocr_lang}")
            
            # 尝试不同的PSM配置
            config_options = [
                '--psm 6 --oem 3',  # 单行文本
                '--psm 11 --oem 3'  # 稀疏文本
            ]
            
            best_text = ""
            max_confidence = 0
            
            for config in config_options:
                text = pytesseract.image_to_string(image, lang=ocr_lang, config=config)
                # 估计置信度 (简单方法: 字符数)
                confidence = len(text.strip())
                if confidence > max_confidence:
                    max_confidence = confidence
                    best_text = text.strip()
            
            print(f"OCR 识别结果: {best_text}")
            return best_text if best_text else ""
        
        except Exception as e:
            print(f"OCR 识别失败: {e}")
            self.update_status(f"OCR 识别失败: {e}")
            return ""

    def process_translation(self):
        if self.translation_in_progress:
            self.update_status("翻译已在进行中，请稍候...")
            return
        
        self.translation_lock.acquire()
        self.translation_in_progress = True
        background_thread_started = False
        
        try:
            self.update_ui_signal.emit("正在处理翻译...", "正在处理...")
            print("开始处理翻译...")
            
            image = self.capture_screen_region()
            if not image:
                self.update_ui_signal.emit("截图失败，请重新选择区域", "截图失败")
                return
        
            original_text = self.ocr_image(image)
            if not original_text:
                self.update_ui_signal.emit("OCR 未识别到文本，请检查图像质量", "OCR 未识别到文本")
                return
        
            if len(original_text) < 5 or not any(c.isalnum() for c in original_text):
                self.update_ui_signal.emit("OCR 结果可能为乱码，请检查图像质量", "OCR 结果可能为乱码")
                self.append_translation(f"原文 (可能无效): {original_text}")
                return
            
            self.append_translation(f"原文: {original_text}")
    
            self.update_ui_signal.emit("正在在线翻译文本...", "正在在线翻译...")
            def online_translate_and_update():
                try:
                    if not self.check_network():
                        self.update_ui_signal.emit("无网络连接，无法在线翻译", "无网络")
                        return
                    translated_text = self.online_translator.translate(original_text, SOURCE_LANG, TARGET_LANG)
                    engine_name = self.online_engine_combo.currentText()
                    self.append_translation(f"翻译 ({engine_name}): {translated_text}")
                    self.update_ui_signal.emit("在线翻译完成", translated_text)
                except Exception as e:
                    import traceback
                    error_msg = f"在线翻译错误: {e}"
                    print(f"{error_msg}\n{traceback.format_exc()}")
                    self.update_ui_signal.emit(error_msg, f"翻译失败: {e}")
                finally:
                    self.translation_in_progress = False
                    self.translation_lock.release()
            threading.Thread(target=online_translate_and_update, daemon=True).start()
            background_thread_started = True
    
        except Exception as e:
            import traceback
            error_msg = f"翻译过程中出错: {e}"
            print(f"{error_msg}\n{traceback.format_exc()}")
            self.append_translation(error_msg)
            self.update_ui_signal.emit(error_msg, f"错误: {e}")
            self.translation_in_progress = False
            self.translation_lock.release()
    
        finally:
            if not background_thread_started and self.translation_lock.locked():
                self.translation_in_progress = False
                self.translation_lock.release()

    def check_network(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except socket.error:
            return False

    def update_overlay_text(self, text):
        if self.translator_overlay:
            self.translator_overlay.text = text
            self.translator_overlay.update_font_size()
            self.translator_overlay.update()

    def closeEvent(self, event):
        if self.global_mouse_listener:
            try:
                self.global_mouse_listener.stop()
                print("全局鼠标监听器已停止")
            except Exception as e:
                print(f"停止全局鼠标监听器时出错: {e}")
        
        # 停止 Google API 管理器（如果正在运行）
        try:
            if hasattr(self, 'language_pack_dialog') and self.language_pack_dialog:
                if hasattr(self.language_pack_dialog, 'google_api_tab'):
                    google_api_tab = self.language_pack_dialog.google_api_tab
                    if hasattr(google_api_tab, 'api_manager'):
                        google_api_tab.api_manager.stop_monitoring()
                        print("Google API 管理器已停止")
        except Exception as e:
            print(f"停止 Google API 管理器时出错: {e}")
        
        if self.translator_overlay:
            try:
                self.update_ui_signal.disconnect(self.translator_overlay.handle_update_signal)
            except TypeError:
                pass
            self.translator_overlay.close()
            self.translator_overlay.deleteLater()
            self.translator_overlay = None
        event.accept()

    def manage_language_packs(self):
        """打开语言包管理对话框"""
        dialog = LanguagePackDialog(self)
        dialog.exec_()

    def get_screen_info(self):
        """获取屏幕信息"""
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        screen_dpi = screen.logicalDotsPerInch()
        device_pixel_ratio = screen.devicePixelRatio()
        
        return {
            'width': screen_geometry.width(),
            'height': screen_geometry.height(),
            'dpi': screen_dpi,
            'device_pixel_ratio': device_pixel_ratio
        }

    def calculate_optimal_window_size(self):
        """计算最适合的窗口大小"""
        screen_info = self.get_screen_info()
        system = platform.system()
        
        print(f"屏幕信息: {screen_info}")
        print(f"操作系统: {system}")
        
        # 基础窗口大小（逻辑像素）
        base_width = 550
        base_height = 350
        
        # 根据操作系统和DPI调整
        if system == "Windows":
            # Windows高DPI处理
            if screen_info['dpi'] > 180:  # 高DPI屏幕
                scale_factor = min(screen_info['dpi'] / 96, 2.0)  # 限制最大缩放比例
                width = int(base_width / scale_factor)
                height = int(base_height / scale_factor)
            else:
                width = base_width
                height = base_height
        elif system == "Linux":
            # Linux通常DPI处理较好，但可能需要微调
            if screen_info['device_pixel_ratio'] > 1:
                width = int(base_width * 0.9)  # Linux下稍微缩小
                height = int(base_height * 0.9)
            else:
                width = base_width
                height = base_height
        else:  # macOS 或其他
            width = base_width
            height = base_height
        
        # 确保窗口不会超出屏幕
        max_width = int(screen_info['width'] * 0.4)  # 最大占屏幕40%宽度
        max_height = int(screen_info['height'] * 0.5)  # 最大占屏幕50%高度
        
        width = min(width, max_width)
        height = min(height, max_height)
        
        # 确保最小尺寸
        width = max(width, 400)
        height = max(height, 300)
        
        print(f"计算得出的窗口大小: {width}x{height}")
        return width, height

    def setup_cross_platform_window_size(self):
        """设置跨平台兼容的窗口大小"""
        try:
            # 获取主屏幕的可用几何区域（减去任务栏等）
            screen = QApplication.primaryScreen()
            available_geometry = screen.availableGeometry()
            
            # 计算窗口大小 - 使用可用区域的百分比
            width = int(available_geometry.width() * 0.4)  # 屏幕宽度的40%
            height = int(available_geometry.height() * 0.6)  # 屏幕高度的60%
            
            # 设置最小和最大限制
            width = max(400, min(width, 800))
            height = max(300, min(height, 600))
            
            # 计算居中位置
            x = available_geometry.x() + (available_geometry.width() - width) // 2
            y = available_geometry.y() + (available_geometry.height() - height) // 2
            
            self.setGeometry(x, y, width, height)
            self.setMinimumSize(400, 300)
            self.setMaximumSize(800, 600)
            
            print(f"窗口已设置为: {width}x{height} 位置: ({x}, {y})")
            print(f"屏幕可用区域: {available_geometry.width()}x{available_geometry.height()}")
            
        except Exception as e:
            print(f"设置窗口大小时出错: {e}")
            # 回退到固定大小
            self.setGeometry(100, 100, 550, 350)

    def setup_windows_dpi_scaling(self):
        """Windows特定的DPI缩放处理"""
        if platform.system() != "Windows":
            return
            
        try:
            # 获取实际DPI缩放比例
            screen = self.screen()
            dpi = screen.logicalDotsPerInch()
            scale_factor = dpi / 96.0  # 96是标准DPI
            
            # 如果缩放比例过高，调整窗口大小
            if scale_factor > 1.5:
                current_size = self.size()
                new_width = int(current_size.width() / scale_factor)
                new_height = int(current_size.height() / scale_factor)
                self.resize(new_width, new_height)
                
        except Exception as e:
            print(f"调整Windows DPI缩放时出错: {e}")

    def check_tesseract_installation(self):
        """检查 Tesseract 是否正确安装"""
        try:
            # 尝试运行 tesseract 命令
            result = subprocess.run(['tesseract', '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version_line = result.stdout.split('\n')[0]
                self.update_status(f"Tesseract 已安装: {version_line}")
                return True
            else:
                self.update_status("Tesseract 安装存在问题")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            self.update_status(f"Tesseract 未正确安装: {e}")
            return False

def setup_qt_plugins():
    """
    动态设置QT插件路径以兼容Windows和Linux发行版
    """
    if 'QT_QPA_PLATFORM_PLUGIN_PATH' in os.environ:
        del os.environ['QT_QPA_PLATFORM_PLUGIN_PATH']
    
    # 尝试使用PyQt5的路径来设置插件路径，而不是使用QLibraryInfo
    try:
        from PyQt5 import QtCore
        pyqt_path = os.path.dirname(QtCore.__file__)
        plugins_path = os.path.join(pyqt_path, "Qt5", "plugins")
        
        if os.path.exists(plugins_path):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugins_path
            print(f"设置QT插件路径: {plugins_path}")
        else:
            # 如果标准路径不存在，尝试其他可能的位置
            possible_paths = [
                os.path.join(sys.prefix, "Lib", "site-packages", "PyQt5", "Qt5", "plugins"),
                os.path.join(sys.prefix, "share", "qt5", "plugins"),
                "/usr/lib/x86_64-linux-gnu/qt5/plugins",
                "/usr/lib/qt5/plugins",
                "/usr/local/qt5/plugins"
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = path
                    print(f"设置QT插件路径: {path}")
                    break
            else:
                print("警告: 无法找到QT插件路径")
                
    except ImportError as e:
        print(f"警告: 无法设置QT插件路径: {e}")
    except Exception as e:
        print(f"设置QT插件路径时出错: {e}")

def main():
    # 在创建QApplication之前设置高DPI支持
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    # Windows特定设置
    if platform.system() == "Windows":
        # 设置高DPI感知模式
        try:
            from ctypes import windll
            # 尝试设置每监视器DPI感知（Windows 10 1703+）
            windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
            print("Windows: 设置了Per-Monitor DPI Aware")
        except Exception as e:
            try:
                # 回退到系统DPI感知
                windll.user32.SetProcessDPIAware()
                print("Windows: 设置了System DPI Aware")
            except Exception as e2:
                print(f"Windows: 无法设置DPI Aware: {e}, {e2}")
    
    # 设置QT插件路径 - 在创建QApplication之前
    setup_qt_plugins()

    # Linux特定设置
    if sys.platform == "linux":
        os.environ['QT_QPA_PLATFORM'] = 'xcb'
        print("设置 QT_QPA_PLATFORM = xcb")

    # 设置OpenCV
    os.environ['OPENCV_VIDEOIO_PRIORITY'] = '0'

    # 创建应用
    app = QApplication(sys.argv)
    
    # 打印实际的DPI信息
    screen = app.primaryScreen()
    if screen:
        print(f"屏幕DPI: {screen.logicalDotsPerInch()}")
        print(f"设备像素比: {screen.devicePixelRatio()}")
        print(f"屏幕尺寸: {screen.geometry().width()}x{screen.geometry().height()}")
    else:
        print("警告: 无法获取屏幕信息")

    # 打印环境信息
    print("=== 环境信息 ===")
    print(f"Python版本: {sys.version}")
    print(f"系统: {sys.platform}")
    print(f"QT_QPA_PLATFORM_PLUGIN_PATH: {os.environ.get('QT_QPA_PLATFORM_PLUGIN_PATH', '未设置')}")
    print(f"QT_QPA_PLATFORM: {os.environ.get('QT_QPA_PLATFORM', '未设置')}")

    # 应用主题
    try:
        apply_modern_theme(app)
        print("✅ 现代化主题已应用")
    except Exception as e:
        print(f"⚠️ 应用主题时出错: {e}")

    # 打印Qt插件路径（现在可以安全地使用QLibraryInfo）
    try:
        plugins_path = QLibraryInfo.location(QLibraryInfo.PluginsPath)
        print(f"Qt插件位置: {plugins_path}")
        if sys.platform == "linux":
            xcb_plugin = os.path.join(plugins_path, "platforms", "libqxcb.so")
            if os.path.exists(xcb_plugin):
                print(f"找到XCB插件: {xcb_plugin}")
            else:
                print(f"错误: 未找到XCB插件: {xcb_plugin}")
    except Exception as e:
        print(f"无法获取Qt插件位置: {e}")

    # 创建主窗口
    try:
        translator = ScreenTranslator()
        translator.show()
        print("✅ 主窗口已创建并显示")
    except Exception as e:
        print(f"❌ 创建主窗口时出错: {e}")
        return

    # 运行应用
    print("🚀 应用程序启动中...")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()