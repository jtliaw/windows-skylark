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


def get_argos_package_dir():
    """
    动态获取 Argos Translate 的默认包目录。
    优先使用环境变量，然后是平台特定路径，最后回退到应用目录。
    """
    # 方法1: 检查是否设置了 ARGOS_PACKAGES_DIR 环境变量
    argos_env_dir = os.environ.get('ARGOS_PACKAGES_DIR')
    if argos_env_dir and os.path.isdir(argos_env_dir):
        return Path(argos_env_dir)
    
    # 方法2: 根据平台获取默认目录
    system = platform.system()
    default_dirs = []
    
    if system == "Windows":
        # Windows 默认路径
        appdata = os.environ.get('APPDATA')
        if appdata:
            default_dirs.append(Path(appdata) / "argos-translate" / "packages")
        
        localappdata = os.environ.get('LOCALAPPDATA')
        if localappdata:
            default_dirs.append(Path(localappdata) / "argos-translate" / "packages")
    
    elif system == "Darwin":  # macOS
        default_dirs.append(Path.home() / "Library" / "Application Support" / "argos-translate" / "packages")
    
    else:  # Linux 和其他 Unix-like 系统
        # 检查 XDG_DATA_HOME 环境变量
        xdg_data_home = os.environ.get('XDG_DATA_HOME')
        if xdg_data_home:
            default_dirs.append(Path(xdg_data_home) / "argos-translate" / "packages")
        
        # 标准 Linux 路径
        default_dirs.append(Path.home() / ".local" / "share" / "argos-translate" / "packages")
        
        # 其他可能的 Linux 路径
        default_dirs.append(Path.home() / ".argos-translate" / "packages")
    
    # 遍历所有可能的默认目录，返回第一个存在的
    for dir_path in default_dirs:
        if dir_path.exists() and dir_path.is_dir():
            return dir_path
    
    # 方法3: 如果以上都不存在，尝试创建一个最可能的标准路径
    if default_dirs:
        most_likely_dir = default_dirs[0]
        try:
            most_likely_dir.mkdir(parents=True, exist_ok=True)
            return most_likely_dir
        except (PermissionError, OSError) as e:
            print(f"无法创建目录 {most_likely_dir}: {e}")
    
    # 方法4: 作为最后的备选，返回当前工作目录下的一个子目录
    fallback_dir = Path.cwd() / "argos_packages"
    fallback_dir.mkdir(exist_ok=True)
    return fallback_dir

def setup_custom_package_dir(custom_dir):
    """
    设置自定义包目录，并确保 Argos Translate 使用它
    """
    custom_path = Path(custom_dir)
    
    # 确保自定义目录存在
    custom_path.mkdir(parents=True, exist_ok=True)
    
    # 获取默认目录
    default_dir = get_argos_package_dir()
    
    # 如果默认目录已经是自定义目录，直接返回
    if default_dir == custom_path:
        return custom_path
    
    # 如果默认目录存在且不是符号链接，创建备份
    if default_dir.exists() and not default_dir.is_symlink():
        backup_dir = default_dir.parent / (default_dir.name + ".backup")
        try:
            if default_dir.is_dir():
                import shutil
                shutil.move(str(default_dir), str(backup_dir))
                print(f"已备份原有包目录到: {backup_dir}")
        except Exception as e:
            print(f"备份目录失败: {e}")
    
    # 创建符号链接/ junction point
    try:
        # 移除可能存在的旧链接
        if default_dir.exists() or default_dir.is_symlink():
            if default_dir.is_symlink() or (hasattr(os, 'is_junction') and os.path.is_junction(default_dir)):
                default_dir.unlink()  # 移除符号链接或 junction
        
        # 根据平台创建链接
        if platform.system() == "Windows":
            # 在 Windows 上创建目录联接 (junction)
            import _winapi
            _winapi.CreateJunction(str(custom_path), str(default_dir))
            print(f"已创建目录联接: {default_dir} -> {custom_path}")
        else:
            # 在 Linux/macOS 上创建符号链接
            default_dir.symlink_to(custom_path, target_is_directory=True)
            print(f"已创建符号链接: {default_dir} -> {custom_path}")
            
    except Exception as e:
        print(f"创建链接失败: {e}")
        # 如果创建链接失败，设置环境变量作为备选方案
        os.environ['ARGOS_PACKAGES_DIR'] = str(custom_path)
        print(f"已设置环境变量 ARGOS_PACKAGES_DIR = {custom_path}")
    
    return custom_path

# 修复AppImage网络问题
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
if 'LD_PRELOAD' in os.environ:
    del os.environ['LD_PRELOAD']
os.makedirs(os.path.expanduser("~/.local/share/argos-translate/packages"), exist_ok=True)

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
    # 应用样式表
    app.setStyleSheet(MODERN_THEME_STYLES)
    
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
    QAbstractItemView, QTreeWidget, QTreeWidgetItem, QRadioButton, QMenu, QDesktopWidget
)
from PyQt5.QtCore import Qt, QRect, QTimer, QPoint, QEvent, QThread, pyqtSignal, QLibraryInfo, QSize
from PyQt5.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics, QKeyEvent, 
    QMouseEvent, QImage, QPixmap, QIcon
)

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

class Translator:
    """
    封装翻译功能，支持直接翻译和自动中转翻译。
    """
    def __init__(self, status_queue):
        self.status_queue = status_queue
        # 您可以在这里设置默认的源语言和目标语言
        # self.from_code = SOURCE_LANG 
        # self.to_code = TARGET_LANG
        self.ready = False
        self.lang_map = {}  # 用于快速查找已安装的语言对象
        self.diagnostic_log = [] # 用于存储诊断日志
        self.available_languages = [] # <--- 新增：恢复此属性以兼容UI

    def log(self, message):
        """记录日志到队列和控制台"""
        self.diagnostic_log.append(message)
        if self.status_queue:
            self.status_queue.put(message)
        print(f"[Translator] {message}")

    def initialize(self):
        """
        初始化翻译引擎，加载语言模型并构建速查表。
        """
        self.log("开始初始化翻译引擎...")
        try:
            from argostranslate import package, translate
            
            # 确保使用正确的包目录
            if 'ARGOS_PACKAGES_DIR' in os.environ:
                custom_dir = os.environ['ARGOS_PACKAGES_DIR']
                self.log(f"使用自定义包目录: {custom_dir}")
                
                # 尝试设置包目录（如果库提供了相应的API）
                try:
                    # 尝试设置包目录（如果库提供了相应的API）
                    if hasattr(package, 'set_packages_dir'):
                        package.set_packages_dir(custom_dir)
                        self.log(f"已设置包目录: {custom_dir}")
                except Exception as e:
                    self.log(f"设置包目录失败: {e}")
            
            package.update_package_index()
            installed_languages = translate.get_installed_languages()
            
            if not installed_languages:
                self.log("警告: 未找到任何已安装的 argostranslate 语言包。")
                self.log("请先运行 python -m argostranslate.cli.install_package --from-code <lang> --to-code <lang>")
                self.ready = False  # 明确设置为未就绪
                return False  # 返回 False 表示初始化失败
    
            # 构建语言代码到语言对象的映射，方便内部快速查找
            self.lang_map = {lang.code: lang for lang in installed_languages}
            
            # 填充 available_languages 列表
            self.available_languages = []
            for lang in installed_languages:
                self.available_languages.append((lang.code, lang.name))
            # 对列表进行排序，让UI显示更友好
            self.available_languages.sort(key=lambda x: x[1]) 
    
            installed_codes = list(self.lang_map.keys())
            self.log(f"已成功加载的语言包: {', '.join(installed_codes)}")
            
            self.ready = True
            self.log("翻译引擎初始化完成，随时可用。")
            return True  # 返回 True 表示初始化成功
    
        except Exception as e:
            self.log(f"翻译引擎初始化失败: {str(e)}")
            self.log(traceback.format_exc())
            self.ready = False
            return False  # 返回 False 表示初始化失败

    def _get_direct_translation(self, text, from_code, to_code):
        """
        【内部方法】尝试进行直接翻译。
        返回 (翻译结果, 错误信息)
        """
        from_lang = self.lang_map.get(from_code)
        to_lang = self.lang_map.get(to_code)

        if not from_lang:
            return None, f"未安装源语言包: {from_code}"
        if not to_lang:
            return None, f"未安装目标语言包: {to_code}"
        
        translation = from_lang.get_translation(to_lang)
        
        if not translation:
            return None, f"没有可用的直接翻译路径: {from_code} -> {to_code}"
            
        try:
            result = translation.translate(text)
            self.log(f"直接翻译成功: {from_code} -> {to_code}")
            return result, None
        except Exception as e:
            return None, f"翻译执行时发生错误: {str(e)}"

    def _get_pivot_translation(self, text, from_code, to_code, pivot_code='en'):
        """
        【内部方法】通过中转语言进行翻译。
        返回 (翻译结果, 错误信息)
        """
        self.log(f"尝试中转翻译: {from_code} -> {pivot_code} -> {to_code}")

        if pivot_code not in self.lang_map:
            return None, f"中转失败：未安装中转语言包: {pivot_code}"

        self.log(f"中转第一步: {from_code} -> {pivot_code}")
        step1_result, error = self._get_direct_translation(text, from_code, pivot_code)
        if error:
            return None, f"中转第一步失败: {error}"
            
        self.log(f"中转第二步: {pivot_code} -> {to_code}")
        step2_result, error = self._get_direct_translation(step1_result, pivot_code, to_code)
        if error:
            return None, f"中转第二步失败: {error}"
        
        self.log("中转翻译成功！")
        return step2_result, None

    def translate(self, text, from_code, to_code):
        """
        智能翻译文本。优先尝试直接翻译，失败后自动尝试中转翻译。
        """
        if not self.ready:
            error_msg = "翻译引擎未就绪，请先调用 initialize()"
            self.log(error_msg)
            return error_msg
        
        if not text or not text.strip():
            return ""

        self.log(f"开始翻译任务: 从 {from_code} 到 {to_code}")

        result, error = self._get_direct_translation(text, from_code, to_code)
        if result is not None:
            return result
        
        self.log(f"直接翻译失败: {error}")

        if from_code != 'en' and to_code != 'en':
            result, error = self._get_pivot_translation(text, from_code, to_code, pivot_code='en')
            if result is not None:
                return result
        
        final_error_msg = f"翻译彻底失败: {from_code} -> {to_code}. 原因: {error}"
        self.log(final_error_msg)
        return final_error_msg


class PackageManager:
    """
    管理Argos Translate语言包的安装、卸载和存储，兼容Windows、Linux、macOS和AppImage环境。
    """
    def __init__(self, status_queue):
        self.status_queue = status_queue
        self.package_index = []
        self.package_dir = self._get_package_dir()  # 这里调用了 _get_package_dir

        try:
            os.makedirs(self.package_dir, exist_ok=True)
            self.status_queue.put(f"语言包目录已就绪: {self.package_dir}")
        except Exception as e:
            self.status_queue.put(f"[错误] 创建语言包目录失败: {e}")
            return

        self._load_package_index()

    def _get_package_dir(self):
        """
        获取语言包存储目录，使用动态检测的目录
        """
        # 确定应用程序目录
        if getattr(sys, 'frozen', False):
            app_dir = Path(sys.executable).parent
        else:
            app_dir = Path(__file__).parent
        
        # 设置自定义包目录
        custom_package_dir = app_dir / "argos_packages"
        
        # 使用 setup_custom_package_dir 确保目录正确设置
        package_dir = setup_custom_package_dir(custom_package_dir)
        
        self.status_queue.put(f"使用包目录: {package_dir}")
        return str(package_dir)

    def _load_package_index(self):
        """加载包索引 - 只加载官方实际提供的语言包"""
        cache_path = os.path.join(self.package_dir, "package_index.json")
        
        # 尝试加载缓存
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_index = json.load(f)
                # 验证缓存是否基于官方包列表
                if self._is_valid_cache(cached_index):
                    self.package_index = cached_index
                    self.status_queue.put(f"从缓存加载了 {len(self.package_index)} 个官方语言包。")
                    return
                else:
                    self.status_queue.put("缓存版本过旧或无效，重新生成...")
            except (json.JSONDecodeError, IOError) as e:
                self.status_queue.put(f"加载缓存失败: {e}")
        
        # 只生成官方实际提供的语言包
        self.package_index = self.generate_official_language_packages()
        self.status_queue.put(f"生成 {len(self.package_index)} 个官方语言包")
        
        # 保存到缓存
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.package_index, f, indent=4)
            self.status_queue.put(f"官方语言包索引已保存到: {cache_path}")
        except IOError as e:
            self.status_queue.put(f"保存语言包索引失败: {e}")
    
    def _is_valid_cache(self, cached_index):
        """验证缓存是否有效（基于官方包列表）"""
        if not isinstance(cached_index, list) or len(cached_index) == 0:
            return False
        # 简单检查：如果缓存包数量过多（>100），可能是旧版本生成的
        if len(cached_index) > 100:
            return False
        return True
    
    def get_official_packages(self):
        """返回官方提供的语言包列表"""
        return [
            # 英语作为源语言的包
            "en_es", "en_fr", "en_de", "en_it", "en_pt", "en_ru", "en_zh", "en_ja", 
            "en_ko", "en_ar", "en_az", "en_ca", "en_cs", "en_da", "en_nl", "en_eo", 
            "en_fi", "en_el", "en_he", "en_hi", "en_hu", "en_id", "en_ga", "en_ms", 
            "en_fa", "en_pl", "en_sk", "en_sv", "en_tr", "en_uk",
            # 英语作为目标语言的包
            "es_en", "fr_en", "de_en", "it_en", "pt_en", "ru_en", "zh_en", "ja_en", 
            "ko_en", "ar_en", "az_en", "ca_en", "cs_en", "da_en", "nl_en", "eo_en", 
            "fi_en", "el_en", "he_en", "hi_en", "hu_en", "id_en", "ga_en", "ms_en", 
            "fa_en", "pl_en", "sk_en", "sv_en", "tr_en", "uk_en",
            # 其他一些官方提供的直接语言对（不通过英语）
            "es_fr", "fr_es", "de_fr", "fr_de", "es_pt", "pt_es",
        ]
    
    def generate_official_language_packages(self):
        """只生成官方实际提供的语言包"""
        packages = []
        official_packages = self.get_official_packages()
        
        for package_code in official_packages:
            parts = package_code.split('_')
            if len(parts) != 2:
                continue
                
            from_code, to_code = parts
            from_name = self.get_language_name(from_code)
            to_name = self.get_language_name(to_code)
            
            # 估计包大小
            size = PACKAGE_SIZE_ESTIMATES.get(from_code, 150) + PACKAGE_SIZE_ESTIMATES.get(to_code, 150)
            
            packages.append({
                "from_code": from_code,
                "to_code": to_code,
                "from_name": from_name,
                "to_name": to_name,
                "file_name": f"{from_code}_{to_code}.argosmodel",
                "size": size,
                "description": f"{from_name}到{to_name}翻译模型"
            })
        
        return packages

    def get_available_packages(self):
        """返回可用的语言包列表"""
        return self.package_index

    def get_package_info(self, from_code, to_code):
        """获取特定语言包信息"""
        for package in self.package_index:
            if package['from_code'] == from_code and package['to_code'] == to_code:
                return package
        
        # 如果在索引中找不到，检查是否是官方包
        if self.is_package_available(from_code, to_code):
            return {
                'from_code': from_code, 
                'to_code': to_code, 
                'from_name': self.get_language_name(from_code), 
                'to_name': self.get_language_name(to_code), 
                'size': self.get_package_size(from_code, to_code), 
                'description': f'{self.get_language_name(from_code)}到{self.get_language_name(to_code)}翻译模型'
            }
        else:
            return None

    def get_language_name(self, code):
        """获取语言代码对应的名称"""
        for lang_code, lang_name in SUPPORTED_LANGUAGES:
            if lang_code == code:
                return lang_name
        return code

    def get_package_size(self, from_code, to_code):
        """获取语言包大小估计"""
        package = self.get_package_info(from_code, to_code)
        if package and 'size' in package:
            return package['size']
        return PACKAGE_SIZE_ESTIMATES.get(from_code, 150) + PACKAGE_SIZE_ESTIMATES.get(to_code, 150)

    def get_ocr_info(self, lang_code):
        """获取OCR信息"""
        ocr_code = OCR_LANG_MAP.get(lang_code, "")
        if not ocr_code:
            return "不支持OCR", 0
        size = 20 if lang_code in ['zh', 'ja', 'ko'] else (15 if lang_code in ['ar', 'he'] else 5)
        return f"tesseract-ocr-{ocr_code}", size

    def is_package_installed(self, from_code, to_code):
        """检查语言包是否已安装 - 适配AppImage环境"""
        marker_file = f"{from_code}_{to_code}.argosmodel"
        package_path = os.path.join(self.package_dir, marker_file)
        if os.path.exists(package_path):
            return True
        
        try:
            import argostranslate.package
            installed_packages = argostranslate.package.get_installed_packages()
            for package in installed_packages:
                if hasattr(package, 'from_code') and hasattr(package, 'to_code'):
                    if package.from_code == from_code and package.to_code == to_code:
                        with open(package_path, 'w', encoding='utf-8') as f:
                            f.write(f"Found via API for {from_code}_{to_code}")
                        return True
        except Exception as e:
            self.status_queue.put(f"[调试] 通过API检查安装状态失败: {e}")
        
        return False

    def is_package_available(self, from_code, to_code):
        """检查语言包是否官方提供"""
        official_packages = self.get_official_packages()
        package_code = f"{from_code}_{to_code}"
        return package_code in official_packages

    def _get_argospm_executable(self):
        """获取argospm可执行文件路径 - 增强版AppImage环境适配"""
        # Windows平台没有argospm，直接返回None
        if platform.system() == "Windows":
            self.status_queue.put("Windows平台使用Python API安装语言包")
            return None
        
        possible_paths = []
        
        if 'APPIMAGE' in os.environ:
            app_dir = os.path.dirname(os.environ['APPIMAGE'])
            possible_paths.extend([
                os.path.join(app_dir, 'argospm'),
                os.path.join(app_dir, 'usr', 'bin', 'argospm'),
                os.path.join(app_dir, 'bin', 'argospm'),
            ])
        
        if 'APPDIR' in os.environ:
            app_dir = os.environ['APPDIR']
            possible_paths.extend([
                os.path.join(app_dir, 'usr', 'bin', 'argospm'),
                os.path.join(app_dir, 'usr', 'bin', '_internal', 'argospm'),
                os.path.join(app_dir, 'usr', 'bin', '_internal', 'bin', 'argospm'),
                os.path.join(app_dir, 'bin', 'argospm'),
                os.path.join(app_dir, '_internal', 'argospm'),
            ])
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths.extend([
            os.path.join(current_dir, 'argospm'),
            os.path.join(current_dir, '_internal', 'argospm'),
            os.path.join(current_dir, '_internal', 'bin', 'argospm'),
            os.path.join(current_dir, '..', 'bin', 'argospm'),
            os.path.join(current_dir, 'bin', 'argospm'),
            os.path.join(sys.prefix, 'bin', 'argospm'),
            os.path.join(sys.exec_prefix, 'bin', 'argospm'),
        ])
        
        system_paths = [
            '/usr/local/bin/argospm',
            '/usr/bin/argospm',
            '/opt/argos/bin/argospm',
        ]
        possible_paths.extend(system_paths)
        
        for path in possible_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                self.status_queue.put(f"✅ 找到argospm: {path}")
                return path
        
        system_argospm = shutil.which('argospm')
        if system_argospm:
            self.status_queue.put(f"✅ 使用系统argospm: {system_argospm}")
            return system_argospm
        
        self.status_queue.put("⚠️ 未找到argospm，将使用fallback方式")
        return 'argospm'

    def _install_via_python_api(self, from_code, to_code, progress_callback=None):
        """通过Python API安装语言包（增强错误诊断版）"""
        import requests
        from urllib.parse import urljoin
    
        def log(message):
            self.status_queue.put(f"[Python API] {message}")
            print(f"[Python API] {message}")
    
        max_retries = 3
        retry_delay = 5  # seconds
    
        for attempt in range(1, max_retries + 1):
            try:
                import argostranslate.package
                import argostranslate.translate
    
                log(f"开始安装 {from_code}->{to_code} (尝试 {attempt}/{max_retries})")
                if progress_callback:
                    progress_callback(10)
    
                # 1. 设置包目录环境变量（确保安装到正确位置）
                os.environ['ARGOS_PACKAGES_DIR'] = self.package_dir
                log(f"设置包目录: {self.package_dir}")
    
                # 2. 更新包索引 (增加超时和重试)
                log("正在更新包索引...")
                try:
                    argostranslate.package.update_package_index()
                except requests.exceptions.RequestException as e:
                    log(f"更新包索引网络错误: {e}. 将在 {retry_delay} 秒后重试...")
                    if attempt < max_retries:
                        time.sleep(retry_delay)
                        continue # 重试循环
                    else:
                        raise Exception(f"更新包索引失败 after {max_retries} 次尝试: {e}")
                except Exception as e:
                    log(f"更新包索引失败: {e}")
                    if "SSL" in str(e).upper():
                        log("SSL错误，尝试使用 certifi 的 CA 包...")
                        # 修复AppImage网络问题 (确保certifi可用)
                        os.environ['SSL_CERT_FILE'] = certifi.where()
                        os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
                        if attempt < max_retries:
                            time.sleep(retry_delay)
                            continue
                    raise e # 如果不是SSL或重试用完，重新抛出异常
    
                if progress_callback:
                    progress_callback(30)
    
                # 3. 获取可用包列表
                log("正在获取可用包列表...")
                available_packages = argostranslate.package.get_available_packages()
                if progress_callback:
                    progress_callback(50)
    
                log(f"找到 {len(available_packages)} 个可用包")
    
                # 4. 查找目标包
                target_package = None
                package_code = f"{from_code}_{to_code}"
    
                for package in available_packages:
                    if hasattr(package, 'from_code') and hasattr(package, 'to_code'):
                        if package.from_code == from_code and package.to_code == to_code:
                            target_package = package
                            break
                    # 兼容旧版本API
                    elif hasattr(package, 'package_code'):
                        if package.package_code == package_code:
                            target_package = package
                            break
    
                if not target_package:
                    error_msg = f"错误: 未找到 {from_code}->{to_code} 语言包"
                    log(error_msg)
                    # 列出所有可用包用于调试
                    for i, pkg in enumerate(available_packages[:10]):  # 只显示前10个避免信息过多
                        if hasattr(pkg, 'from_code') and hasattr(pkg, 'to_code'):
                            log(f"  可用包 {i+1}: {pkg.from_code}->{pkg.to_code}")
                        elif hasattr(pkg, 'package_code'):
                            log(f"  可用包 {i+1}: {pkg.package_code}")
                    # 检查这个包是否在官方列表中
                    if not self.is_package_available(from_code, to_code):
                        log(f"额外提示: {from_code}->{to_code} 不在已知的官方包列表中。")
                    return False # 不是网络错误，重试没用
    
                log(f"找到目标包: {from_code}->{to_code}")
                if progress_callback:
                    progress_callback(70)
    
                # 5. 下载包 (增加超时)
                log("开始下载包...")
                try:
                    download_path = target_package.download()
                except requests.exceptions.RequestException as e:
                    log(f"下载包网络错误: {e}. 将在 {retry_delay} 秒后重试...")
                    if attempt < max_retries:
                        time.sleep(retry_delay)
                        continue # 重试循环
                    else:
                        raise Exception(f"下载包失败 after {max_retries} 次尝试: {e}")
                log(f"下载完成: {download_path}")
                if progress_callback:
                    progress_callback(85)
    
                # 6. 安装包
                log("开始安装包...")
                argostranslate.package.install_from_path(download_path)
                if progress_callback:
                    progress_callback(95)
    
                # 7. 创建标记文件
                marker_file = f"{from_code}_{to_code}.argosmodel"
                marker_path = os.path.join(self.package_dir, marker_file)
                try:
                    with open(marker_path, 'w', encoding='utf-8') as f:
                        f.write(f"Installed via Python API at {datetime.now()}\n")
                        f.write(f"Package: {from_code}_{to_code}\n")
                    log(f"标记文件已创建: {marker_path}")
                except OSError as e:
                    log(f"警告: 无法创建标记文件 {marker_path}: {e}. 但包可能已安装。")
    
                if progress_callback:
                    progress_callback(100)
    
                log(f"成功安装 {from_code}->{to_code}")
                return True # 成功！
    
            except Exception as e:
                import traceback
                error_detail = traceback.format_exc()
                log(f"安装失败 (尝试 {attempt}/{max_retries}): {str(e)}")
                log(f"详细错误:\n{error_detail}")
    
                if attempt == max_retries:
                    # 最后一次尝试也失败了
                    log(f"❌ 安装 {from_code}->{to_code} 彻底失败 after {max_retries} 次尝试。")
    
                    # 检查网络连接
                    try:
                        test_url = "http://www.google.com"
                        response = requests.get(test_url, timeout=10)
                        log("网络连接测试: 正常")
                    except requests.exceptions.RequestException as net_err:
                        log(f"网络连接测试: 失败 ({net_err})")
                        log("请检查您的互联网连接。")
                    except Exception as net_err:
                        log(f"网络连接测试: 发生意外错误 ({net_err})")
    
                    # 检查包目录权限
                    test_file_path = os.path.join(self.package_dir, "write_test.tmp")
                    try:
                        with open(test_file_path, 'w') as f:
                            f.write("test")
                        os.remove(test_file_path)
                        log("包目录写入权限: 正常")
                    except OSError as perm_err:
                        log(f"包目录写入权限: 失败 ({perm_err})")
                        log(f"请确保程序有权限写入目录: {self.package_dir}")
                        log("尝试以管理员身份运行程序可能解决此问题。")
    
                    return False
                else:
                    # 等待后重试
                    log(f"将在 {retry_delay} 秒后重试...")
                    time.sleep(retry_delay)

    def install_package(self, from_code, to_code, progress_callback=None):
        """安装语言包 - 使用argospm并设置正确的包目录"""
        if not self.is_package_available(from_code, to_code):
            self.status_queue.put(f"错误: {from_code}->{to_code} 语言包官方未提供")
            return False
    
        if self.is_package_installed(from_code, to_code):
            self.status_queue.put(f"语言包 {from_code}->{to_code} 已经安装")
            if progress_callback: progress_callback(100)
            return True
        
        # Windows平台使用Python API安装
        if platform.system() == "Windows":
            self.status_queue.put(f"Windows平台使用Python API安装 {from_code}->{to_code}")
            return self._install_via_python_api(from_code, to_code, progress_callback)
        
        # 其他平台使用argospm
        package_name = f"translate-{from_code}_{to_code}"
        executable = self._get_argospm_executable()
        
        # 如果找不到argospm，回退到Python API
        if not executable or executable == 'argospm':
            self.status_queue.put(f"未找到argospm，使用Python API安装 {from_code}->{to_code}")
            return self._install_via_python_api(from_code, to_code, progress_callback)
        
        # 设置环境变量，告诉argospm将包安装到我们的自定义目录
        env = os.environ.copy()
        env['ARGOS_PACKAGES_DIR'] = self.package_dir
        
        command = [executable, "install", package_name]
        
        self.status_queue.put(f"执行安装命令: {' '.join(command)}")
        self.status_queue.put(f"包将安装到: {self.package_dir}")
        if progress_callback: progress_callback(10)
    
        try:
            process = subprocess.Popen(
                command,
                env=env,  # 传递修改后的环境变量
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True, 
                encoding='utf-8', 
                bufsize=1,
            )
    
            self.status_queue.put(f"正在安装 {package_name}...")
            if progress_callback: progress_callback(30)
    
            stdout_lines = []
            stderr_lines = []
            
            while True:
                output = process.stdout.readline()
                if not output and process.poll() is not None: 
                    break
                if output: 
                    line = output.strip()
                    stdout_lines.append(line)
                    self.status_queue.put(f"[argospm]: {line}")
            
            return_code = process.wait()
            stderr_output = process.stderr.read()
            if stderr_output: 
                stderr_lines.append(stderr_output.strip())
                self.status_queue.put(f"[argospm-ERROR]: {stderr_output.strip()}")
    
            if progress_callback: progress_callback(90)
    
            if return_code == 0:
                self.status_queue.put(f"语言包 {package_name} 安装成功！")
                # 创建标记文件
                marker_file = f"{from_code}_{to_code}.argosmodel"
                marker_path = os.path.join(self.package_dir, marker_file)
                with open(marker_path, 'w', encoding='utf-8') as f:
                    f.write(f"Installed via argospm for {package_name}")
                if progress_callback: progress_callback(100)
                return True
            else:
                self.status_queue.put(f"argospm安装失败，返回码: {return_code}")
                return False
    
        except FileNotFoundError:
            self.status_queue.put(f"错误: '{executable}' 命令未找到")
            return False
        except Exception as e:
            self.status_queue.put(f"安装时发生未知错误: {e}")
            return False

    def uninstall_package(self, from_code, to_code):
        """卸载语言包 - 完全适配AppImage环境的方法"""
        package_name = f"translate-{from_code}_{to_code}"
        
        if not self.is_package_installed(from_code, to_code):
            self.status_queue.put(f"语言包 {package_name} 未安装，无需卸载")
            return True
        
        if self._try_uninstall_with_argospm(from_code, to_code, package_name):
            return True
        
        return self._uninstall_manually(from_code, to_code, package_name)
    
    def _try_uninstall_with_argospm(self, from_code, to_code, package_name):
        """尝试使用argospm卸载"""
        executable = self._get_argospm_executable()
        
        if executable == 'argospm':
            try:
                test_process = subprocess.Popen(
                    [executable, '--help'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5
                )
                test_process.communicate()
                if test_process.returncode != 0:
                    self.status_queue.put("argospm不可用，跳过")
                    return False
            except:
                self.status_queue.put("argospm不可用，跳过")
                return False
        
        command = [executable, "remove", package_name]
        self.status_queue.put(f"尝试argospm卸载: {' '.join(command)}")
    
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            stdout_output, stderr_output = process.communicate(input='y\n', timeout=30)
    
            if stdout_output:
                self.status_queue.put(f"[argospm]: {stdout_output.strip()}")
            if stderr_output:
                self.status_queue.put(f"[argospm-stderr]: {stderr_output.strip()}")
    
            if process.returncode == 0:
                self.status_queue.put(f"✅ argospm卸载成功: {package_name}")
                self._cleanup_marker_file(from_code, to_code)
                return True
            else:
                self.status_queue.put(f"❌ argospm卸载失败，返回码: {process.returncode}")
                return False
    
        except FileNotFoundError:
            self.status_queue.put("argospm命令未找到")
            return False
        except subprocess.TimeoutExpired:
            self.status_queue.put("argospm卸载超时")
            return False
        except Exception as e:
            self.status_queue.put(f"argospm卸载出错: {e}")
            return False
    
    def _uninstall_manually(self, from_code, to_code, package_name):
        """手动删除语言包文件（AppImage友好方式）"""
        self.status_queue.put(f"尝试手动删除语言包: {package_name}")
        
        try:
            deleted_items = []
            
            standard_locations = [
                os.path.expanduser("~/.local/share/argos-translate/packages"),
                "/usr/local/share/argos-translate/packages",
                "/usr/share/argos-translate/packages",
            ]
            
            if 'ARGOS_PACKAGES_DIR' in os.environ:
                standard_locations.insert(0, os.environ['ARGOS_PACKAGES_DIR'])
            
            if 'APPDIR' in os.environ:
                appdir_packages = os.path.join(os.environ['APPDIR'], 'usr', 'bin', '_internal', 'argos_packages')
                if os.path.exists(appdir_packages):
                    standard_locations.append(appdir_packages)
            
            for packages_dir in standard_locations:
                if not os.path.exists(packages_dir):
                    continue
                    
                try:
                    for item in os.listdir(packages_dir):
                        item_path = os.path.join(packages_dir, item)
                        patterns = [
                            f"{from_code}_{to_code}",
                            f"{from_code}-{to_code}",
                            f"translate-{from_code}_{to_code}",
                            package_name,
                        ]
                        
                        if any(pattern in item for pattern in patterns):
                            try:
                                if os.path.isdir(item_path):
                                    shutil.rmtree(item_path)
                                    deleted_items.append(f"目录: {item}")
                                else:
                                    os.remove(item_path)
                                    deleted_items.append(f"文件: {item}")
                            except OSError as e:
                                self.status_queue.put(f"⚠️ 删除 {item} 失败: {e}")
                                
                except OSError as e:
                    self.status_queue.put(f"⚠️ 访问目录 {packages_dir} 失败: {e}")
            
            marker_cleaned = self._cleanup_marker_file(from_code, to_code)
            if marker_cleaned:
                deleted_items.append("标记文件")
            
            try:
                import argostranslate.package
                installed_packages = argostranslate.package.get_installed_packages()
                for package in installed_packages:
                    if (hasattr(package, 'from_code') and hasattr(package, 'to_code') and
                        package.from_code == from_code and package.to_code == to_code):
                        try:
                            if hasattr(package, 'uninstall'):
                                package.uninstall()
                                deleted_items.append("Python API卸载")
                        except:
                            pass
                        break
            except Exception as e:
                self.status_queue.put(f"Python API卸载尝试失败: {e}")
            
            if deleted_items:
                self.status_queue.put(f"✅ 手动卸载成功，已删除: {', '.join(deleted_items)}")
                return True
            else:
                self.status_queue.put(f"⚠️ 未找到 {package_name} 的相关文件，可能已经被删除")
                return True
                
        except Exception as e:
            self.status_queue.put(f"❌ 手动卸载失败: {e}")
            return False
    
    def _cleanup_marker_file(self, from_code, to_code):
        """清理标记文件"""
        marker_file = f"{from_code}_{to_code}.argosmodel"
        marker_path = os.path.join(self.package_dir, marker_file)
        
        if os.path.exists(marker_path):
            try:
                os.remove(marker_path)
                self.status_queue.put(f"✅ 已清理标记文件: {marker_file}")
                return True
            except OSError as e:
                self.status_queue.put(f"⚠️ 清理标记文件失败: {e}")
                return False
        return False

    def check_package_environment(self):
        """检查包环境状态"""
        self.status_queue.put("=== 包环境诊断 ===")
        self.status_queue.put(f"包目录: {self.package_dir}")
        self.status_queue.put(f"目录存在: {os.path.exists(self.package_dir)}")
        self.status_queue.put(f"目录可写: {os.access(self.package_dir, os.W_OK)}")
        
        if os.path.exists(self.package_dir):
            packages = os.listdir(self.package_dir)
            self.status_queue.put(f"目录中的文件: {len(packages)} 个")
            for pkg in packages[:10]:  # 显示前10个文件
                self.status_queue.put(f"  - {pkg}")
        
        # 检查环境变量
        self.status_queue.put(f"ARGOS_PACKAGES_DIR: {os.environ.get('ARGOS_PACKAGES_DIR', '未设置')}")
        
        # 检查argostranslate版本
        try:
            import argostranslate
            self.status_queue.put(f"Argos Translate 版本: {argostranslate.__version__}")
        except:
            self.status_queue.put("无法获取Argos Translate版本信息")
        
        self.status_queue.put("=== 诊断结束 ===")

    def diagnose_package_issues(self, from_code, to_code):
        """诊断语言包问题"""
        self.status_queue.put("=== 语言包问题诊断 ===")
        
        # 检查包目录
        self.status_queue.put(f"包目录: {self.package_dir}")
        self.status_queue.put(f"目录存在: {os.path.exists(self.package_dir)}")
        self.status_queue.put(f"目录可写: {os.access(self.package_dir, os.W_OK)}")
        
        # 检查特定语言包
        package_code = f"{from_code}_{to_code}"
        package_dir = os.path.join(self.package_dir, f"translate-{package_code}-1_9")
        self.status_queue.put(f"语言包目录: {package_dir}")
        self.status_queue.put(f"语言包目录存在: {os.path.exists(package_dir)}")
        
        if os.path.exists(package_dir):
            # 列出目录内容
            contents = os.listdir(package_dir)
            self.status_queue.put(f"语言包目录内容: {len(contents)} 个文件")
            for item in contents[:10]:  # 只显示前10个文件
                self.status_queue.put(f"  - {item}")
                
            # 检查必要的文件
            required_files = ["model.bin", "config.json", "vocab.txt"]
            for file in required_files:
                file_path = os.path.join(package_dir, file)
                self.status_queue.put(f"{file} 存在: {os.path.exists(file_path)}")
        
        # 检查环境变量
        self.status_queue.put(f"ARGOS_PACKAGES_DIR: {os.environ.get('ARGOS_PACKAGES_DIR', '未设置')}")
        
        self.status_queue.put("=== 诊断结束 ===")

class InstallWorker(QThread):
    """后台安装工作线程"""
    progress_updated = pyqtSignal(int)
    finished = pyqtSignal(bool, str, str)
    
    def __init__(self, package_manager, from_code, to_code):
        super().__init__()
        self.package_manager = package_manager
        self.from_code = from_code
        self.to_code = to_code
    
    def run(self):
        # 进度回调函数
        def progress_callback(progress):
            self.progress_updated.emit(progress)
        
        # 执行安装
        success = self.package_manager.install_package(
            self.from_code, self.to_code, progress_callback
        )
        
        # 发送完成信号
        self.finished.emit(success, self.from_code, self.to_code)

class UninstallWorker(QThread):
    """用于在后台执行语言包卸载的线程"""
    # 信号定义：
    # 完成信号 (布尔值表示成功与否, from_code, to_code)
    finished = pyqtSignal(bool, str, str)

    def __init__(self, package_manager, from_code, to_code):
        super().__init__()
        self.package_manager = package_manager
        self.from_code = from_code
        self.to_code = to_code
        self.success = False

    def run(self):
        """线程执行的入口点"""
        try:
            # 调用 PackageManager 中真正的卸载方法
            self.success = self.package_manager.uninstall_package(
                self.from_code,
                self.to_code
            )
        except Exception as e:
            self.package_manager.status_queue.put(f"卸载工作线程出错: {e}")
            self.success = False
        finally:
            # 任务完成后，发射 finished 信号
            self.finished.emit(self.success, self.from_code, self.to_code)

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

class PackageInfoDialog(QDialog):
    """显示语言包详细信息的对话框"""
    def __init__(self, package_manager, from_code, to_code, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{from_code.upper()} -> {to_code.upper()} 语言包信息")
        self.setFixedSize(500, 400)
        
        # 获取语言包信息
        package_info = package_manager.get_package_info(from_code, to_code)
        package_size = package_manager.get_package_size(from_code, to_code)
        ocr_package, ocr_size = package_manager.get_ocr_info(from_code)
        
        layout = QVBoxLayout()
        
        # 语言包基本信息
        info_group = QGroupBox("翻译语言包信息")
        info_layout = QVBoxLayout()
        
        info_text = QTextEdit()
        info_text.setReadOnly(True)
        
        if package_info:
            info_content = f"""
            <b>源语言:</b> {package_info['from_name']} ({from_code})<br>
            <b>目标语言:</b> {package_info['to_name']} ({to_code})<br>
            <b>包大小:</b> {package_size} MB<br>
            <b>版本:</b> {package_info.get('version', '未知')}<br>
            <b>发布日期:</b> {package_info.get('date', '未知')}<br>
            <b>模型类型:</b> {package_info.get('type', '未知')}<br>
            <b>描述:</b> {package_info.get('description', '暂无描述')}
            """
        else:
            info_content = f"""
            <b>源语言:</b> {from_code.upper()}<br>
            <b>目标语言:</b> {to_code.upper()}<br>
            <b>包大小:</b> {package_size} MB (估计值)<br>
            <b>版本:</b> 未知<br>
            <b>发布日期:</b> 未知<br>
            <b>模型类型:</b> 未知<br>
            <b>描述:</b> 没有可用的详细信息
            """
        
        info_text.setHtml(info_content)
        info_layout.addWidget(info_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # OCR语言包信息
        ocr_group = QGroupBox("OCR支持")
        ocr_layout = QVBoxLayout()
        
        ocr_text = QTextEdit()
        ocr_text.setReadOnly(True)
        
        if ocr_package:
            ocr_content = f"""
            <b>OCR语言包:</b> {ocr_package}<br>
            <b>大小:</b> {ocr_size} MB (估计值)<br>
            <b>安装状态:</b> {self.get_ocr_status(from_code)}<br>
            <b>说明:</b> 此翻译语言包需要安装对应的OCR语言包才能正确识别文本
            """
        else:
            ocr_content = f"""
            <b>OCR支持:</b> 不支持<br>
            <b>说明:</b> 此语言没有可用的OCR语言包
            """
        
        ocr_text.setHtml(ocr_content)
        ocr_layout.addWidget(ocr_text)
        ocr_group.setLayout(ocr_layout)
        layout.addWidget(ocr_group)
        
        # 确定按钮
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)
        
        self.setLayout(layout)

        # 添加可用性信息
        available = package_manager.is_package_available(from_code, to_code)
        availability_text = "官方提供" if available else "官方未提供"
        availability_color = "green" if available else "red"
        
        if package_info:
            info_content = f"""
            <b>源语言:</b> {package_info['from_name']} ({from_code})<br>
            <b>目标语言:</b> {package_info['to_name']} ({to_code})<br>
            <b>包大小:</b> {package_size} MB<br>
            <b>可用性:</b> <span style='color:{availability_color};'>{availability_text}</span><br>
            <b>版本:</b> {package_info.get('version', '未知')}<br>
            <b>发布日期:</b> {package_info.get('date', '未知')}<br>
            <b>模型类型:</b> {package_info.get('type', '未知')}<br>
            <b>描述:</b> {package_info.get('description', '暂无描述')}
            """
        else:
            info_content = f"""
            <b>源语言:</b> {from_code.upper()}<br>
            <b>目标语言:</b> {to_code.upper()}<br>
            <b>包大小:</b> {package_size} MB (估计值)<br>
            <b>可用性:</b> <span style='color:{availability_color};'>{availability_text}</span><br>
            <b>版本:</b> 未知<br>
            <b>发布日期:</b> 未知<br>
            <b>模型类型:</b> 未知<br>
            <b>描述:</b> 没有可用的详细信息
            """
    
    def get_ocr_status(self, lang_code):
        """获取OCR语言包安装状态"""
        try:
            langs = pytesseract.get_languages()
            ocr_code = OCR_LANG_MAP.get(lang_code, "")
            if ocr_code and ocr_code in langs:
                return "已安装"
            return "未安装"
        except:
            return "未知"

class LanguagePackDialog(QDialog):
    """语言包管理对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setWindowTitle("Argos Translate 语言包管理器 (离线模式)")
        self.setWindowIcon(QIcon("skylark.png"))
        self.setMinimumSize(800, 600)

        
        # 添加离线模式说明
        self.offline_info = QLabel(
            "<b>注意: 当前语言包是可选择下载</b><br>"
            "由于Argos Translate是单向翻译，有很多语言是不可直接翻译，<br>"
            "比如需要日语翻译中文，需要下载（日语到英语）（英语到中文）软件会自动中转翻译。<br>"
            "要使用完整功能，请确保您的设备连接到互联网。"
        )
        self.offline_info.setStyleSheet("background-color: #FFF8DC; padding: 10px; color: #000000;")
        self.offline_info.setWordWrap(True)
        
        # 创建包管理器 - 使用主窗口的状态队列
        self.package_manager = PackageManager(parent.status_queue)
        
        # 创建顶部按钮布局
        top_button_layout = QHBoxLayout()
        
        # 添加刷新按钮
        self.refresh_btn = QPushButton("刷新语言包")
        self.refresh_btn.clicked.connect(self.refresh_language_packs)
        self.refresh_btn.setToolTip("重新加载语言包列表并刷新翻译器状态")
        top_button_layout.addWidget(self.refresh_btn)
        
        # 添加诊断按钮
        self.diagnose_btn = QPushButton("诊断信息")
        self.diagnose_btn.clicked.connect(self.show_diagnostic_info)
        self.diagnose_btn.setToolTip("显示语言包环境诊断信息")
        top_button_layout.addWidget(self.diagnose_btn)
        
        # 添加关闭按钮
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        top_button_layout.addWidget(self.close_btn)
        
        # 添加弹性空间
        top_button_layout.addStretch()
        
        self.tab_widget = QTabWidget()
        
        # 翻译语言包标签页
        self.translate_tab = TranslateLanguageTab(self, self.package_manager)
        self.tab_widget.addTab(self.translate_tab, "翻译语言包")
        
        # OCR语言包标签页
        self.ocr_tab = OCRLanguageTab(self, self.main_window)
        self.tab_widget.addTab(self.ocr_tab, "OCR语言包")
        
        # Tesseract安装标签页
        self.install_tab = TesseractInstallTab(self, self.main_window)
        self.tab_widget.addTab(self.install_tab, "安装Tesseract")
        
        layout = QVBoxLayout()
        layout.addWidget(self.offline_info)
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
    
    def update_status(self):
        """从状态队列更新状态标签"""
        try:
            while not self.main_window.status_queue.empty():
                message = self.main_window.status_queue.get_nowait()
                self.status_label.setText(message)
        except queue.Empty:
            pass
    
    def refresh_language_packs(self):
        """刷新语言包列表并重新初始化翻译器"""
        self.main_window.status_queue.put("正在刷新语言包...")
        
        # 重新初始化翻译器
        if self.main_window.translator:
            self.main_window.translator.ready = False
            self.main_window.translation_ready = False
            
            # 在单独的线程中重新初始化
            def reinitialize_translator():
                try:
                    # 确保使用正确的包目录
                    if 'ARGOS_PACKAGES_DIR' in os.environ:
                        custom_dir = os.environ['ARGOS_PACKAGES_DIR']
                        self.main_window.status_queue.put(f"使用包目录: {custom_dir}")
                        
                        # 尝试设置包目录
                        try:
                            from argostranslate import package
                            if hasattr(package, 'set_packages_dir'):
                                package.set_packages_dir(custom_dir)
                                self.main_window.status_queue.put(f"已设置包目录: {custom_dir}")
                        except Exception as e:
                            self.main_window.status_queue.put(f"设置包目录失败: {e}")
                    
                    # 重新初始化翻译器
                    success = self.main_window.translator.initialize()
                    self.main_window.translator.ready = success
                    self.main_window.translation_ready = success
                    
                    if success:
                        self.main_window.status_queue.put("离线翻译器刷新成功")
                    else:
                        self.main_window.status_queue.put("离线翻译器刷新失败，请检查语言包")
                        
                except Exception as e:
                    self.main_window.status_queue.put(f"刷新翻译器时出错: {e}")
            
            # 启动重新初始化线程
            threading.Thread(target=reinitialize_translator, daemon=True).start()
        
        # 刷新语言包列表
        self.translate_tab.load_package_data()
        
        self.main_window.status_queue.put("语言包刷新完成")
    
    def show_diagnostic_info(self):
        """显示诊断信息"""
        # 检查包目录
        self.main_window.status_queue.put("=== 语言包诊断信息 ===")
        self.main_window.status_queue.put(f"包目录: {self.package_manager.package_dir}")
        self.main_window.status_queue.put(f"目录存在: {os.path.exists(self.package_manager.package_dir)}")
        self.main_window.status_queue.put(f"目录可写: {os.access(self.package_manager.package_dir, os.W_OK)}")
        
        # 列出包目录中的文件
        if os.path.exists(self.package_manager.package_dir):
            packages = os.listdir(self.package_manager.package_dir)
            self.main_window.status_queue.put(f"包目录中的文件: {len(packages)} 个")
            for pkg in packages[:10]:  # 只显示前10个文件
                self.main_window.status_queue.put(f"  - {pkg}")
        
        # 检查环境变量
        self.main_window.status_queue.put(f"ARGOS_PACKAGES_DIR: {os.environ.get('ARGOS_PACKAGES_DIR', '未设置')}")
        
        # 检查翻译器状态
        if self.main_window.translator:
            self.main_window.status_queue.put(f"翻译器就绪: {self.main_window.translator.ready}")
            if hasattr(self.main_window.translator, 'lang_map'):
                self.main_window.status_queue.put(f"已加载语言: {list(self.main_window.translator.lang_map.keys())}")
        
        self.main_window.status_queue.put("=== 诊断信息结束 ===")

class TranslateLanguageTab(QWidget):
    """翻译语言包管理标签页 (已清理)"""
    def __init__(self, parent, package_manager):
        super().__init__(parent)
        self.parent = parent
        self.package_manager = package_manager
        
        # 简化状态变量
        self.current_filter = "installable"  # 默认显示可安装包
        
        self.setup_ui()
        
        # 添加网络状态检测
        self.network_available = self.check_network_connection()
        
        # 加载语言包数据
        self.load_package_data()
    
    def check_network_connection(self):
        """检查网络连接状态 - 安全实现"""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            return True
        except (socket.gaierror, socket.timeout, ConnectionRefusedError, OSError):
            return False
        except Exception:
            return False
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # 添加状态信息区域
        self.info_box = QGroupBox("语言包状态")
        info_layout = QVBoxLayout()
        
        self.status_label = QLabel("正在加载语言包信息...")
        self.status_label.setStyleSheet("font-weight: bold; color: blue;")
        info_layout.addWidget(self.status_label)
        
        self.detail_label = QLabel("")
        self.detail_label.setWordWrap(True)
        info_layout.addWidget(self.detail_label)
        
        self.info_box.setLayout(info_layout)
        layout.addWidget(self.info_box)
        
        # 搜索和过滤区域
        filter_layout = QHBoxLayout()
        
        # 搜索框
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索语言包...")
        self.search_input.textChanged.connect(self.filter_packages)
        filter_layout.addWidget(self.search_input)
        
        # 显示选项下拉菜单 - 只保留有用的选项
        self.filter_combo = QComboBox()
        self.filter_combo.addItem("所有语言包", "all")
        self.filter_combo.addItem("仅可安装包", "installable")  # 默认选项
        self.filter_combo.addItem("仅已安装包", "installed")
        self.filter_combo.setCurrentIndex(1)  # 默认选择"仅可安装包"
        self.filter_combo.currentIndexChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_combo)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.load_package_data)
        filter_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(filter_layout)
        
        # 语言包表格
        self.package_table = QTableWidget()
        self.package_table.setColumnCount(5)
        self.package_table.setHorizontalHeaderLabels([
            "源语言", "目标语言", "大小 (MB)", "状态", "操作"
        ])
        self.package_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.package_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.package_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        layout.addWidget(self.package_table)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
    
    def get_visible_packages(self):
        """根据当前过滤选项获取可见的包 - 只返回官方支持的包"""
        packages = self.package_manager.get_available_packages()
        
        if self.current_filter == "installable":
            # 仅显示可安装包（未安装但官方支持）
            return [pkg for pkg in packages 
                    if (self.package_manager.is_package_available(pkg['from_code'], pkg['to_code']) 
                    and not self.package_manager.is_package_installed(pkg['from_code'], pkg['to_code']))]
        
        elif self.current_filter == "installed":
            # 仅显示已安装包
            return [pkg for pkg in packages 
                    if self.package_manager.is_package_installed(pkg['from_code'], pkg['to_code'])]
        
        else:  # "all" - 但只显示官方支持的包
            # 显示所有官方支持的包
            return [pkg for pkg in packages 
                    if self.package_manager.is_package_available(pkg['from_code'], pkg['to_code'])]
    
    def on_filter_changed(self, index):
        """当过滤选项改变时"""
        self.current_filter = self.filter_combo.currentData()
        self.load_package_data()
    
    def load_package_data(self):
        """加载语言包数据到表格 - 只显示官方支持的包"""
        # 禁用UI更新以提高性能
        self.package_table.setUpdatesEnabled(False)
        self.package_table.setSortingEnabled(False)
        
        try:
            # 刷新时重新检查网络状态
            self.network_available = self.check_network_connection()
            
            self.package_table.setRowCount(0)
            
            # 更新状态信息
            self.status_label.setText("正在加载语言包数据...")
            self.detail_label.setText("请稍候...")
            
            # 获取过滤后的包 - 只获取官方支持的包
            packages = self.get_visible_packages()
            
            # 更新状态信息
            if packages:
                # 获取过滤状态描述
                filter_text = {
                    "all": "所有官方语言包",
                    "installable": "可安装的官方包",
                    "installed": "已安装包"
                }.get(self.current_filter, "")
                
                status_text = f"已加载 {len(packages)} 个语言包 (显示: {filter_text})"
                
                if not self.network_available:
                    status_text += " (离线模式)"
                    self.detail_label.setText("离线模式下无法安装新语言包，请连接互联网后刷新")
                    self.detail_label.setStyleSheet("color: red;")
                else:
                    self.detail_label.setText("点击操作按钮安装/卸载语言包。")
                    self.detail_label.setStyleSheet("")
                
                self.status_label.setText(status_text)
                self.status_label.setStyleSheet("font-weight: bold; color: green;")
            else:
                self.status_label.setText("没有可用的语言包")
                self.status_label.setStyleSheet("font-weight: bold; color: red;")
                self.detail_label.setText("无法加载语言包信息，请检查本地缓存或内置列表。")
                return
            
            # 显示语言包
            for idx, package in enumerate(packages):
                from_code = package['from_code']
                to_code = package['to_code']
                from_name = package.get('from_name', from_code)
                to_name = package.get('to_name', to_code)
                
                package_size = self.package_manager.get_package_size(from_code, to_code)
                installed = self.package_manager.is_package_installed(from_code, to_code)
                
                # 设置状态文本 - 只有已安装和未安装两种状态
                status = "已安装" if installed else "未安装"
                
                # 创建行
                self.package_table.insertRow(idx)
                
                # 源语言列
                from_item = QTableWidgetItem(f"{from_name} ({from_code})")
                self.package_table.setItem(idx, 0, from_item)
                
                # 目标语言列
                to_item = QTableWidgetItem(f"{to_name} ({to_code})")
                self.package_table.setItem(idx, 1, to_item)
                
                # 大小列
                size_item = QTableWidgetItem(str(package_size))
                self.package_table.setItem(idx, 2, size_item)
                
                # 状态列
                status_item = QTableWidgetItem(status)
                
                # 设置状态项颜色
                if status == "已安装":
                    status_item.setForeground(QColor(0, 128, 0))  # 绿色
                else:
                    status_item.setForeground(QColor(0, 0, 255))  # 蓝色
                
                self.package_table.setItem(idx, 3, status_item)
                
                # 创建操作按钮
                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                
                # 信息按钮始终可用
                info_btn = QPushButton("信息")
                info_btn.clicked.connect(lambda _, f=from_code, t=to_code: self.show_package_info(f, t))
                btn_layout.addWidget(info_btn)
                
                # 根据状态添加操作按钮
                if installed:
                    uninstall_btn = QPushButton("卸载")
                    uninstall_btn.clicked.connect(lambda _, f=from_code, t=to_code: self.uninstall_package(f, t))
                    btn_layout.addWidget(uninstall_btn)
                else:
                    install_btn = QPushButton("安装")
                    
                    # 离线模式下禁用安装按钮
                    if not self.network_available:
                        install_btn.setEnabled(False)
                        install_btn.setToolTip("离线模式下无法安装新语言包")
                    else:
                        install_btn.clicked.connect(lambda _, f=from_code, t=to_code: self.install_package(f, t))
                    
                    btn_layout.addWidget(install_btn)
                
                btn_layout.setContentsMargins(5, 2, 5, 2)
                btn_widget.setLayout(btn_layout)
                self.package_table.setCellWidget(idx, 4, btn_widget)
            
            # 应用当前的搜索过滤
            self.filter_packages()
            
        finally:
            # 重新启用UI更新
            self.package_table.setUpdatesEnabled(True)
            self.package_table.setSortingEnabled(True)
            self.package_table.resizeColumnsToContents()
    
    def filter_packages(self):
        """根据过滤条件筛选语言包"""
        search_text = self.search_input.text().lower()
        
        for row in range(self.package_table.rowCount()):
            from_text = self.package_table.item(row, 0).text().lower()
            to_text = self.package_table.item(row, 1).text().lower()
            
            search_match = (search_text in from_text or search_text in to_text or not search_text)
            self.package_table.setRowHidden(row, not search_match)
    
    def show_package_info(self, from_code, to_code):
        """显示包信息"""
        try:
            dialog = PackageInfoDialog(self.package_manager, from_code, to_code, self)
            dialog.exec_()
        except Exception as e:
            QMessageBox.warning(
                self, 
                "错误", 
                f"无法显示包信息: {e}\n\n请尝试刷新列表或检查网络连接。"
            )
    
    def install_package(self, from_code, to_code):
        """安装语言包"""
        try:
            # 检查网络连接
            if not self.check_network_connection():
                self.status_label.setText("安装失败：无网络连接，请检查网络后重试")
                self.status_label.setStyleSheet("font-weight: bold; color: red;")
                QMessageBox.warning(
                    self, 
                    "网络连接失败", 
                    "无法安装语言包，请确保您的设备已连接到互联网。\n"
                    "离线模式下只能使用已安装的语言包。"
                )
                return
            
            # 禁用所有按钮，防止重复操作
            self.set_buttons_enabled(False)
            
            # 显示进度条
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            
            # 创建并启动工作线程
            self.worker = InstallWorker(self.package_manager, from_code, to_code)
            self.worker.progress_updated.connect(self.progress_bar.setValue)
            self.worker.finished.connect(self.on_install_finished)
            self.worker.start()
        except Exception as e:
            self.status_label.setText(f"安装失败: {str(e)}")
            self.status_label.setStyleSheet("font-weight: bold; color: red;")
            self.set_buttons_enabled(True)
            self.progress_bar.setVisible(False)
    
    def uninstall_package(self, from_code, to_code):
        """卸载语言包（通过后台线程执行）"""
        try:
            # 禁用所有按钮
            self.set_buttons_enabled(False)
            
            # 更新状态标签，提示用户
            self.status_label.setText(f"正在卸载 {from_code}->{to_code} ...")
            self.status_label.setStyleSheet("font-weight: bold; color: orange;")
            
            # 创建并启动卸载工作线程
            self.uninstall_worker = UninstallWorker(self.package_manager, from_code, to_code)
            self.uninstall_worker.finished.connect(self.on_uninstall_finished)
            self.uninstall_worker.start()
        except Exception as e:
            self.status_label.setText(f"卸载失败: {str(e)}")
            self.status_label.setStyleSheet("font-weight: bold; color: red;")
            self.set_buttons_enabled(True)
    
    def on_install_finished(self, success, from_code, to_code):
        """安装完成后的处理"""
        try:
            # 隐藏进度条并恢复按钮
            self.progress_bar.setVisible(False)
            self.set_buttons_enabled(True)
            
            if success:
                self.status_label.setText(f"成功安装 {from_code}->{to_code}！")
                self.status_label.setStyleSheet("font-weight: bold; color: green;")
                # 刷新表格
                self.load_package_data()
            else:
                self.status_label.setText(f"安装 {from_code}->{to_code} 失败。")
                self.status_label.setStyleSheet("font-weight: bold; color: red;")
                QMessageBox.warning(self, "安装失败", f"安装包 {from_code}->{to_code} 失败。\n请查看状态日志获取详细信息。")
        except Exception as e:
            pass
    
    def on_uninstall_finished(self, success, from_code, to_code):
        """卸载完成后的处理"""
        try:
            # 恢复按钮可用状态
            self.set_buttons_enabled(True)
            
            if success:
                self.status_label.setText(f"成功卸载 {from_code}->{to_code}！")
                self.status_label.setStyleSheet("font-weight: bold; color: green;")
            else:
                self.status_label.setText(f"卸载 {from_code}->{to_code} 失败。")
                self.status_label.setStyleSheet("font-weight: bold; color: red;")
                QMessageBox.warning(self, "卸载失败", f"卸载包 {from_code}->{to_code} 失败。\n请查看状态日志获取详细信息。")
            
            # 刷新表格以更新状态
            self.load_package_data()
        except Exception as e:
            pass
    
    def set_buttons_enabled(self, enabled):
        """辅助函数，用于启用/禁用表格中的所有操作按钮和刷新按钮"""
        try:
            self.refresh_btn.setEnabled(enabled)
            
            # 遍历表格中的所有行
            for row in range(self.package_table.rowCount()):
                # 获取操作列的控件
                widget = self.package_table.cellWidget(row, 4)
                if widget:
                    # 遍历容器内的所有QPushButton并设置其状态
                    buttons = widget.findChildren(QPushButton)
                    for button in buttons:
                        button.setEnabled(enabled)
        except Exception as e:
            pass

class OCRLanguageTab(QWidget):
    """OCR语言包管理标签页"""
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.parent = parent
        self.main_window = main_window
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        self.lang_list = QTreeWidget()
        self.lang_list.setHeaderLabels(["语言", "OCR代码", "状态", "大小 (MB)"])
        self.lang_list.setColumnWidth(0, 200)
        self.populate_lang_list()
        layout.addWidget(QLabel("OCR语言包:"))
        layout.addWidget(self.lang_list)
        
        btn_layout = QHBoxLayout()
        self.install_btn = QPushButton("安装语言包")
        self.install_btn.clicked.connect(lambda: self.install_ocr_language())
        btn_layout.addWidget(self.install_btn)
        
        self.remove_btn = QPushButton("删除选中语言包")
        self.remove_btn.clicked.connect(self.remove_ocr_lang)
        btn_layout.addWidget(self.remove_btn)
        
        self.refresh_btn = QPushButton("刷新列表")
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
    
    def get_package_manager(self):
        """动态检测包管理器 - 增强版，支持所有主要Linux发行版"""
        system = platform.system()
        if system == "Linux":
            # 使用SystemDetector来获取正确的包管理器
            sys_info = SystemDetector.get_system_info()
            pkg_manager = sys_info['package_manager']
            
            # 映射包管理器到安装命令
            pkg_manager_commands = {
                'apt': ["apt-get", "install", "-y"],
                'dnf': ["dnf", "install", "-y"],
                'yum': ["yum", "install", "-y"],  # 添加yum支持
                'pacman': ["pacman", "-S", "--noconfirm"],
                'zypper': ["zypper", "install", "-y"],  # 添加zypper支持
                'apk': ["apk", "add"]  # Alpine Linux
            }
            
            if pkg_manager in pkg_manager_commands:
                command = pkg_manager_commands[pkg_manager]
                self.main_window.status_queue.put(f"检测到包管理器: {pkg_manager}")
                return command
            
            # 如果SystemDetector无法识别，回退到旧方法
            for cmd, pkg_mgr in [
                ("apt-get", ["apt-get", "install", "-y"]),
                ("dnf", ["dnf", "install", "-y"]),
                ("yum", ["yum", "install", "-y"]),  # 添加yum支持
                ("pacman", ["pacman", "-S", "--noconfirm"]),
                ("zypper", ["zypper", "install", "-y"])  # 添加zypper支持
            ]:
                if shutil.which(cmd):
                    self.main_window.status_queue.put(f"检测到包管理器: {cmd}")
                    return pkg_mgr
            
            self.main_window.status_queue.put("错误: 未找到支持的包管理器")
            return None
        elif system == "Darwin":
            if shutil.which("brew"):
                self.main_window.status_queue.put("检测到包管理器: brew")
                return ["brew", "install"]
            self.main_window.status_queue.put("错误: 未找到 Homebrew")
            return None
        self.main_window.status_queue.put(f"不支持的操作系统: {system}")
        return None

    def get_tessdata_dir(self):
        """获取 Tesseract tessdata 目录 - 使用应用程序目录"""
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
            # 如果应用程序目录不可写，回退到系统目录
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
            else:
                return os.path.expanduser("~/.tessdata")

    def update_package_cache(self, pkg_manager, password):
        """更新包管理器缓存 - 增强版，支持多种包管理器"""
        if platform.system() != "Linux":
            return True
        
        update_commands = {
            'apt': ["sudo", "-S", "apt-get", "update", "--allow-releaseinfo-change"],
            'dnf': ["sudo", "-S", "dnf", "check-update"],  # dnf没有专门的update命令
            'yum': ["sudo", "-S", "yum", "check-update"],  # yum没有专门的update命令
            'zypper': ["sudo", "-S", "zypper", "refresh"],  # zypper的更新命令
            'pacman': ["sudo", "-S", "pacman", "-Sy"]  # Arch的同步命令
        }
        
        if pkg_manager not in update_commands:
            self.main_window.status_queue.put(f"不支持使用 {pkg_manager} 更新包缓存")
            return True
        
        self.main_window.status_queue.put(f"更新 {pkg_manager} 包缓存...")
        
        try:
            process = subprocess.run(
                update_commands[pkg_manager],
                input=password + '\n',
                text=True,
                capture_output=True,
                # 对于check-update命令，即使有更新可用也会返回非零退出码
                check=False if pkg_manager in ['dnf', 'yum'] else True
            )
            
            # 对于dnf和yum，check-update在有更新时返回非零是正常的
            if pkg_manager in ['dnf', 'yum'] and process.returncode == 100:
                self.main_window.status_queue.put(f"{pkg_manager} 包缓存更新成功，有可用更新")
                return True
            elif process.returncode == 0:
                self.main_window.status_queue.put(f"{pkg_manager} 包缓存更新成功")
                return True
            else:
                error_msg = f"更新 {pkg_manager} 包缓存失败: {process.stderr}"
                self.main_window.status_queue.put(error_msg)
                return False
                
        except subprocess.CalledProcessError as e:
            self.main_window.status_queue.put(f"更新 {pkg_manager} 包缓存失败: {e.stderr}")
            return False
        except Exception as e:
            self.main_window.status_queue.put(f"更新 {pkg_manager} 包缓存时未知错误: {e}")
            return False

    def install_ocr_language(self, ocr_code=None):
        """安装指定OCR语言包到自定义目录"""
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
        download_url = f"https://github.com/tesseract-ocr/tessdata/raw/main/{ocr_code}.traineddata"
        output_path = os.path.join(tessdata_dir, f"{ocr_code}.traineddata")
        
        self.main_window.status_queue.put(f"开始下载 {ocr_code}.traineddata...")
        
        try:
            import requests
            response = requests.get(download_url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
            
            self.main_window.status_queue.put(f"{ocr_code}.traineddata 下载成功")
            QMessageBox.information(self, "成功", f"{ocr_code} OCR语言包安装成功")
            
        except Exception as e:
            error_msg = f"下载 {ocr_code}.traineddata 失败: {e}"
            self.main_window.status_queue.put(error_msg)
            QMessageBox.warning(self, "下载失败", error_msg)
        
        # 刷新语言包列表
        self.populate_lang_list()
    
    def _get_correct_package_name(self, ocr_code):
        """根据OCR代码获取正确的包名"""
        # 基于你的终端测试结果，我们知道正确的包名格式
        package_mapping = {
            'chi_sim': 'tesseract-ocr-chi-sim',
            'chi_tra': 'tesseract-ocr-chi-tra',
            'eng': 'tesseract-ocr-eng',
            'jpn': 'tesseract-ocr-jpn',
            'kor': 'tesseract-ocr-kor',
            'ara': 'tesseract-ocr-ara',
            'fra': 'tesseract-ocr-fra',
            'deu': 'tesseract-ocr-deu',
            'spa': 'tesseract-ocr-spa',
            'ita': 'tesseract-ocr-ita',
            'por': 'tesseract-ocr-por',
            'rus': 'tesseract-ocr-rus',
            'hin': 'tesseract-ocr-hin',
            'tha': 'tesseract-ocr-tha',
            'vie': 'tesseract-ocr-vie'
        }
        
        return package_mapping.get(ocr_code, f'tesseract-ocr-{ocr_code}')
    
    def _check_available_language_packages(self, pkg_manager, password):
        """检查系统中可用的语言包 - 增强版"""
        self.main_window.status_queue.put("检查系统中可用的Tesseract语言包...")
        
        try:
            # 根据包管理器类型选择正确的搜索命令
            search_commands = {
                'apt': ['sudo', '-S', 'apt-cache', 'search', 'tesseract-ocr'],
                'dnf': ['sudo', '-S', 'dnf', 'search', 'tesseract'],
                'yum': ['sudo', '-S', 'yum', 'search', 'tesseract'],  # 添加yum支持
                'zypper': ['sudo', '-S', 'zypper', 'search', 'tesseract'],  # 添加zypper支持
                'pacman': ['sudo', '-S', 'pacman', '-Ss', 'tesseract']  # 添加pacman支持
            }
            
            if pkg_manager not in search_commands:
                self.main_window.status_queue.put(f"不支持使用 {pkg_manager} 搜索语言包")
                return
            
            process = subprocess.Popen(
                search_commands[pkg_manager],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            stdout_output, stderr_output = process.communicate(input=f"{password}\n", timeout=60)
            
            if stdout_output:
                # 只显示前500个字符，避免输出太长
                self.main_window.status_queue.put(f"可用的语言包: {stdout_output[:500]}")
            
        except Exception as e:
            self.main_window.status_queue.put(f"检查可用包时出错: {e}")
    
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
                # 右键点击时，通知主窗口切换显示状态
                if self.parent():
                    self.parent().toggle_overlay_visibility()
            else:
                super().mousePressEvent(event)
    
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
        if overlay_text.startswith("翻译结果") or overlay_text.startswith("OCR结果"):
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
            # 如果是打包后的可执行文件
            app_dir = Path(os.path.dirname(sys.executable))
        else:
            # 如果是脚本运行
            app_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        
        # 设置 Argos Translate 包目录
        argos_package_dir = app_dir / "argos_packages"
        setup_custom_package_dir(argos_package_dir)
        
        # 设置 Tesseract tessdata 目录
        tessdata_dir = app_dir / "tessdata"
        tessdata_dir.mkdir(parents=True, exist_ok=True)
        os.environ['TESSDATA_PREFIX'] = str(tessdata_dir.absolute())  # 使用绝对路径
        
        # 记录目录设置
        print(f"设置 Argos 包目录: {argos_package_dir.absolute()}")
        print(f"设置 Tesseract 数据目录: {tessdata_dir.absolute()}")
        
        self.capture_area = None
        self.translator_overlay = None
        self.translation_in_progress = False
        self.translation_ready = False
        
        # 添加全局鼠标监听相关属性
        self.global_mouse_listener = None
        self.overlay_hidden = False  # 跟踪翻译框的隐藏状态
        
        self.status_queue = queue.Queue()
        
        # 🆕 修改翻译器初始化
        self.translator = Translator(self.status_queue) if ARGOS_TRANSLATE_AVAILABLE else None
        self.online_translator = OnlineTranslator()  # 添加在线翻译器
        self.use_online_translation = True  # 默认使用在线翻译
        self.translation_ready = False  # 初始化为 False，需通过 initialize_offline_translator 设置


        # 启动离线翻译器初始化（如果默认在线，可在切换时初始化）
        if self.translator and not self.use_online_translation:
            threading.Thread(target=self.initialize_offline_translator, daemon=True).start()
        
        self.init_ui()
        self.init_translator()
        self.init_global_mouse_listener()
        
        # 设置窗口属性
        self.setWindowTitle("Skylark Translation V2.4 - 扫描屏幕翻译软件")
        self.setGeometry(100, 100, 550, 350)  # 稍微增大窗口
        
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
        """全局鼠标点击事件处理 - 带调试信息"""
        current_time = time.time()
        
        # 只在鼠标按下时处理，避免按下和释放都被处理
        if button == mouse.Button.right and pressed:
            # 检查点击延迟
            if current_time - self.last_right_click_time < self.click_delay:
                print(f"忽略快速点击: {current_time - self.last_right_click_time:.3f}s")
                return  # 忽略快速连续点击
            
            self.last_right_click_time = current_time
            print(f"处理右键点击: ({x}, {y}), pressed: {pressed}")
            
            if self.translator_overlay:
                overlay_rect = self.translator_overlay.geometry()
                overlay_visible = not self.overlay_hidden
                
                print(f"覆盖层位置: {overlay_rect.x()}, {overlay_rect.y()}, {overlay_rect.width()}x{overlay_rect.height()}")
                print(f"覆盖层状态: {'显示' if not self.overlay_hidden else '隐藏'}")
                
                # 检查点击是否在覆盖层区域内
                click_in_overlay = (
                    overlay_rect.x() <= x <= overlay_rect.x() + overlay_rect.width() and
                    overlay_rect.y() <= y <= overlay_rect.y() + overlay_rect.height()
                )
                
                print(f"点击在覆盖层内: {click_in_overlay}")
                
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

    def toggle_overlay_visibility(self):
        """切换翻译框显示/隐藏状态"""
        if self.overlay_hidden:
            self.show_overlay()
        else:
            self.hide_overlay()
    
    def hide_overlay(self):
        """完全隐藏翻译框"""
        if self.translator_overlay and not self.overlay_hidden:
            self.translator_overlay.hide()
            self.overlay_hidden = True
            self.update_status("翻译框已隐藏 (右键任意位置可唤醒)")
            print("翻译框已隐藏")
    
    def show_overlay(self):
        """显示翻译框"""
        if self.translator_overlay and self.overlay_hidden:
            self.translator_overlay.show()
            self.translator_overlay.setWindowOpacity(0.8)
            self.overlay_hidden = False
            self.update_status("翻译框已显示")
            print("翻译框已显示")

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
        self.online_radio.toggled.connect(self.on_translation_type_changed)
        engine_type_layout.addWidget(self.online_radio)
        
        self.offline_radio = QRadioButton("离线翻译 (Argos)")
        self.offline_radio.setEnabled(ARGOS_TRANSLATE_AVAILABLE)
        self.offline_radio.toggled.connect(self.on_translation_type_changed)
        engine_type_layout.addWidget(self.offline_radio)
        
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
        
        self.on_translation_type_changed()

    def on_translation_type_changed(self):
        """翻译类型改变事件"""
        self.use_online_translation = self.online_radio.isChecked()
        
        self.online_engine_combo.setEnabled(self.use_online_translation)
        self.api_settings_btn.setEnabled(self.use_online_translation)
        
        if self.use_online_translation:
            self.translation_ready = True
            self.update_status("在线翻译已就绪！双击选择框进行翻译。")
            current_engine = self.online_engine_combo.currentData()
            if current_engine:
                self.online_translator.set_translator(current_engine)
        else:
            # 检查离线翻译器是否可用
            if self.translator:
                # 重新初始化离线翻译器
                self.translator.ready = False
                self.translation_ready = False
                threading.Thread(target=self.initialize_offline_translator, daemon=True).start()
            else:
                self.update_status("Argos Translate 未安装，离线翻译不可用")
                self.translation_ready = False

    def on_online_engine_changed(self):
        if self.use_online_translation:
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

    def manage_language_packs(self):
        dialog = LanguagePackDialog(self)
        dialog.exec_()

    def init_translator(self):
        if self.translator:
            self.update_status("正在初始化离线翻译引擎...")
            threading.Thread(target=self.translator.initialize, daemon=True).start()
        
        if self.use_online_translation:
            self.translation_ready = True
            self.update_status("在线翻译已就绪！双击选择框进行翻译。")

    def check_status_queue(self):
        try:
            while not self.status_queue.empty():
                message = self.status_queue.get_nowait()
                if not self.use_online_translation:
                    self.update_status(message)
                    if "随时可用" in message:
                        self.translation_ready = True
                        self.update_status("离线翻译引擎已就绪！双击选择框进行翻译。")
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
        
        # 检查是否有可用的语言
        if not self.use_online_translation and (not self.translator or not self.translator.ready):
            QMessageBox.warning(self, "警告", "离线翻译未就绪，请先安装语言包或切换到在线翻译")
            return
        
        # 获取可用的语言列表
        if self.use_online_translation:
            available_languages = SUPPORTED_LANGUAGES
        else:
            # 使用离线翻译器的可用语言
            if self.translator and hasattr(self.translator, 'available_languages'):
                available_languages = self.translator.available_languages
            else:
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
                if self.translator:
                    self.translator.from_code = SOURCE_LANG
                    self.translator.to_code = TARGET_LANG
                    self.translator.ready = False
                    if not self.use_online_translation:
                        self.translation_ready = False
                lang_map = {"ja": "jpn", "en": "eng", "zh": "chi_sim", "ko": "kor", "ms": "msa"}
                ocr_lang = lang_map.get(SOURCE_LANG, "eng")
                translation_mode = "在线" if self.use_online_translation else "离线"
                self.update_status(f"语言设置已更新: 源语言={SOURCE_LANG}, 目标语言={TARGET_LANG}, OCR语言={ocr_lang}, 翻译模式={translation_mode}")
                if self.translator and not self.use_online_translation:
                    threading.Thread(target=self.initialize_offline_translator, daemon=True).start()

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
    
            if self.use_online_translation:
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
    
            elif self.translator and not self.translation_ready:
                self.update_status("离线翻译未就绪，正在初始化...")
                self.initialize_offline_translator()
                if not self.translation_ready:
                    self.update_ui_signal.emit("离线翻译初始化失败，请检查语言包", "初始化失败")
                    return
    
            elif self.translator and self.translation_ready:
                self.update_ui_signal.emit("正在离线翻译文本...", "正在离线翻译...")
                def offline_translate_and_update():
                    try:
                        translated_text = self.translator.translate(original_text, SOURCE_LANG, TARGET_LANG)
                        self.append_translation(f"翻译 (Argos): {translated_text}")
                        self.update_ui_signal.emit("离线翻译完成", translated_text)
                    except Exception as e:
                        import traceback
                        error_msg = f"离线翻译错误: {e}"
                        print(f"{error_msg}\n{traceback.format_exc()}")
                        self.update_ui_signal.emit(error_msg, f"错误: {e}")
                    finally:
                        self.translation_in_progress = False
                        self.translation_lock.release()
                threading.Thread(target=offline_translate_and_update, daemon=True).start()
                background_thread_started = True
    
            else:
                self.update_ui_signal.emit("仅显示OCR结果 (无翻译引擎)", original_text)
                self.append_translation(f"仅OCR: {original_text}")
                self.translation_in_progress = False
                self.translation_lock.release()
    
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
        
        if self.translator_overlay:
            try:
                self.update_ui_signal.disconnect(self.translator_overlay.handle_update_signal)
            except TypeError:
                pass
            self.translator_overlay.close()
            self.translator_overlay.deleteLater()
            self.translator_overlay = None
        event.accept()

    def toggle_translation_mode(self, use_online):
        self.use_online_translation = use_online
        self.update_status(f"已切换到{'在线' if use_online else '离线'}翻译模式")
        if not use_online:
            if self.translator:
                self.translator.ready = False
                self.translation_ready = False
                threading.Thread(target=self.initialize_offline_translator, daemon=True).start()
            else:
                try:
                    import argostranslate.translate
                    self.translator = argostranslate.translate.Translator()
                    threading.Thread(target=self.initialize_offline_translator, daemon=True).start()
                except ImportError:
                    self.update_status("Argos Translate 未安装")
                    self.translation_ready = False
        else:
            if self.translator:
                self.translator.ready = False
            self.translation_ready = False

    def initialize_offline_translator(self):
        with self.translation_lock:
            if self.translator and not self.translation_ready:
                self.update_status("正在初始化离线翻译器...")
                print(f"初始化前就绪状态: {self.translation_ready}")
                try:
                    success = self.translator.initialize()  # 现在 initialize() 返回布尔值
                    self.translator.ready = success
                    self.translation_ready = success
                    if success:
                        self.update_status("离线翻译已就绪")
                    else:
                        self.update_status("离线翻译初始化失败，请安装语言包")
                    print(f"初始化后就绪状态: {self.translation_ready}")
                except Exception as e:
                    self.update_status(f"离线翻译初始化失败: {e}")
                    self.translation_ready = False
                    print(f"初始化错误: {e}")


def setup_qt_plugins():
    """
    动态设置QT插件路径以兼容Windows和Linux发行版
    """
    if 'QT_QPA_PLATFORM_PLUGIN_PATH' in os.environ:
        del os.environ['QT_QPA_PLATFORM_PLUGIN_PATH']
    try:
        plugins_path = QLibraryInfo.location(QLibraryInfo.PluginsPath)
        if os.path.exists(plugins_path):
            os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = plugins_path
            print(f"设置QT插件路径: {plugins_path}")
        else:
            print(f"警告: QT插件路径不存在: {plugins_path}")
    except ImportError:
        print("警告: 无法设置QT插件路径")

def main():
    # 设置高DPI支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    # 设置QT插件路径
    setup_qt_plugins()

    # Linux特定设置
    if sys.platform == "linux":
        os.environ['QT_QPA_PLATFORM'] = 'xcb'
        print("设置 QT_QPA_PLATFORM = xcb")

    # 设置OpenCV
    os.environ['OPENCV_VIDEOIO_PRIORITY'] = '0'

    # 检查argostranslate
    if not ARGOS_TRANSLATE_AVAILABLE:
        print("警告: 未找到 argostranslate 库。")
        print("请运行: pip install argostranslate")

    # 打印环境信息
    print("=== 环境信息 ===")
    print(f"Python版本: {sys.version}")
    print(f"系统: {sys.platform}")
    print(f"QT_QPA_PLATFORM_PLUGIN_PATH: {os.environ.get('QT_QPA_PLATFORM_PLUGIN_PATH', '未设置')}")
    print(f"QT_QPA_PLATFORM: {os.environ.get('QT_QPA_PLATFORM', '未设置')}")

    # 创建应用
    app = QApplication(sys.argv)

    # 应用主题
    try:
        apply_modern_theme(app)
        print("✅ 现代化主题已应用")
    except Exception as e:
        print(f"⚠️ 应用主题时出错: {e}")

    # 打印Qt插件路径
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
