import requests
import threading
import time
import random
import json
import os
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTableWidget, QTableWidgetItem, QCheckBox, QSpinBox,
    QGroupBox, QTextEdit, QMessageBox, QComboBox, QLineEdit,
    QScrollArea, QWidget, QHeaderView
)
from PyQt5.QtCore import QTimer, pyqtSignal, QThread, Qt
from PyQt5.QtGui import QColor

class GoogleTranslateManager(QThread):
    """轻量化Google翻译API管理器"""
    
    endpoint_status_updated = pyqtSignal(str, bool, str, float)
    api_switched = pyqtSignal(str, str)
    limit_reached = pyqtSignal(str)  # 触发限制时的信号
    
    def __init__(self):
        super().__init__()
        
        # 精选的Google翻译端点（按可用性排序）
        self.endpoints = [
            # 最稳定的官方端点
            "https://translate.googleapis.com/translate_a/single",
            "https://translate.google.com/translate_a/single",
            
            # 国内可访问的端点
            "https://translate.google.cn/translate_a/single",
            "https://translate.google.com.hk/translate_a/single",
            
            # 备用客户端端点
            "https://clients5.google.com/translate_a/single",
            "https://translate-pa.googleapis.com/translate_a/single",
            
            # 其他地区镜像
            "https://translate.google.com.tw/translate_a/single",
            "https://translate.google.com.sg/translate_a/single",
            "https://translate.google.co.jp/translate_a/single",
        ]
        
        # 用户代理列表 - 模拟不同浏览器避免检测
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36'
        ]
        
        # 请求客户端类型
        self.client_types = ['gtx', 'webapp', 'dict-chrome-ex', 't']
        
        self.current_endpoint = self.endpoints[0]
        self.current_endpoint_index = 0
        self.endpoint_status = {}
        
        # 限制绕过策略
        self.daily_char_count = 0
        self.last_reset_date = datetime.now().date()
        self.request_delay = 0.5  # 请求间隔
        self.auto_switch_on_limit = True
        
        # 监控设置
        self.is_monitoring = False
        self.check_interval = 300
        self.auto_switch_enabled = True
        
        # 加载每日字符计数
        self.load_daily_stats()
    
    def get_random_headers(self):
        """获取随机的请求头"""
        return {
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://translate.google.com/',
        }
    
    def get_random_params(self, text, from_lang='auto', to_lang='zh'):
        """获取随机的请求参数"""
        return {
            'client': random.choice(self.client_types),
            'sl': from_lang,
            'tl': to_lang,
            'dt': 't',
            'q': text,
            'ie': 'UTF-8',
            'oe': 'UTF-8',
            'tk': str(random.randint(100000, 999999))  # 随机token
        }
    
    def test_endpoint(self, endpoint_url, test_text="Hello"):
        """测试端点是否可用"""
        try:
            params = self.get_random_params(test_text, 'en', 'zh')
            headers = self.get_random_headers()
            
            start_time = time.time()
            response = requests.get(
                endpoint_url, 
                params=params, 
                headers=headers, 
                timeout=10
            )
            response_time = time.time() - start_time
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result and len(result) > 0 and len(result[0]) > 0:
                        translated = result[0][0][0]
                        if translated and len(translated) > 0:
                            return True, f"正常 ({response_time:.2f}s)", response_time
                    return False, "返回结果异常", response_time
                except json.JSONDecodeError:
                    return False, "JSON解析失败", response_time
            elif response.status_code == 429:
                return False, "请求限制 (429)", response_time
            elif response.status_code == 403:
                return False, "访问被拒绝 (403)", response_time
            else:
                return False, f"HTTP {response.status_code}", response_time
                
        except requests.exceptions.Timeout:
            return False, "请求超时", 10.0
        except requests.exceptions.ConnectionError:
            return False, "连接失败", 0.0
        except Exception as e:
            return False, str(e)[:50], 0.0
    
    def translate(self, text, from_lang='auto', to_lang='zh', retry_count=3):
        """翻译文本，带有智能重试和端点切换"""
        if not text.strip():
            return text
        
        # 检查日期，重置每日计数
        self.check_daily_reset()
        
        # 记录字符数
        char_count = len(text)
        self.daily_char_count += char_count
        self.save_daily_stats()
        
        # 添加请求延迟
        if self.request_delay > 0:
            time.sleep(self.request_delay)
        
        for attempt in range(retry_count):
            try:
                params = self.get_random_params(text, from_lang, to_lang)
                headers = self.get_random_headers()
                
                response = requests.get(
                    self.current_endpoint,
                    params=params,
                    headers=headers,
                    timeout=15
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result and len(result) > 0 and len(result[0]) > 0:
                        translated = result[0][0][0]
                        if translated:
                            return translated
                
                elif response.status_code == 429:
                    # 触发速率限制，尝试切换端点
                    self.limit_reached.emit(f"端点 {self.current_endpoint} 触发限制")
                    if self.auto_switch_on_limit:
                        old_endpoint = self.current_endpoint
                        if self.switch_to_next_endpoint():
                            self.api_switched.emit(old_endpoint, self.current_endpoint)
                            continue  # 用新端点重试
                
                # 其他错误情况下的重试延迟
                if attempt < retry_count - 1:
                    time.sleep(random.uniform(1, 3))
                    
            except Exception as e:
                if attempt < retry_count - 1:
                    time.sleep(random.uniform(1, 3))
                else:
                    print(f"翻译失败: {e}")
        
        return None
    
    def switch_to_next_endpoint(self):
        """切换到下一个端点"""
        self.current_endpoint_index = (self.current_endpoint_index + 1) % len(self.endpoints)
        self.current_endpoint = self.endpoints[self.current_endpoint_index]
        return True
    
    def find_best_endpoint(self):
        """找到最佳可用端点"""
        best_endpoint = None
        best_time = float('inf')
        
        for i, endpoint in enumerate(self.endpoints):
            is_working, message, response_time = self.test_endpoint(endpoint)
            self.endpoint_status_updated.emit(endpoint, is_working, message, response_time)
            
            if is_working and response_time < best_time:
                best_endpoint = endpoint
                best_time = response_time
                self.current_endpoint_index = i
            
            time.sleep(1)  # 避免请求过于频繁
        
        if best_endpoint:
            self.current_endpoint = best_endpoint
            return True, best_time
        
        return False, 0
    
    def check_daily_reset(self):
        """检查是否需要重置每日统计"""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_char_count = 0
            self.last_reset_date = current_date
            self.save_daily_stats()
    
    def load_daily_stats(self):
        """加载每日统计数据"""
        try:
            if os.path.exists('translation_stats.json'):
                with open('translation_stats.json', 'r') as f:
                    data = json.load(f)
                    self.daily_char_count = data.get('daily_char_count', 0)
                    date_str = data.get('date', '')
                    if date_str:
                        self.last_reset_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            pass
    
    def save_daily_stats(self):
        """保存每日统计数据"""
        try:
            data = {
                'daily_char_count': self.daily_char_count,
                'date': self.last_reset_date.strftime('%Y-%m-%d')
            }
            with open('translation_stats.json', 'w') as f:
                json.dump(data, f)
        except:
            pass
    
    def get_daily_stats(self):
        """获取今日统计信息"""
        self.check_daily_reset()
        return {
            'chars_today': self.daily_char_count,
            'current_endpoint': self.current_endpoint,
            'endpoint_index': self.current_endpoint_index + 1,
            'total_endpoints': len(self.endpoints)
        }
    
    def run(self):
        """监控主循环"""
        while self.is_monitoring:
            is_working, message, response_time = self.test_endpoint(self.current_endpoint)
            self.endpoint_status_updated.emit(self.current_endpoint, is_working, message, response_time)
            
            if not is_working and self.auto_switch_enabled:
                success, _ = self.find_best_endpoint()
                if success:
                    self.api_switched.emit("故障端点", self.current_endpoint)
            
            for _ in range(self.check_interval):
                if not self.is_monitoring:
                    break
                time.sleep(1)
    
    def start_monitoring(self):
        """开始监控"""
        self.is_monitoring = True
        self.start()
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_monitoring = False
        self.wait()

class GoogleAPIDialog(QDialog):
    """轻量化的Google翻译API管理对话框"""
    
    def __init__(self, screen_translator=None):
        super().__init__()
        self.screen_translator = screen_translator
        self.api_manager = GoogleTranslateManager()
        
        # 创建滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        # 创建内容小部件
        self.content_widget = QWidget()
        self.init_ui()
        self.setup_connections()
        self.update_stats()
        
        # 设置滚动区域的内容
        self.scroll_area.setWidget(self.content_widget)
        
        # 设置主布局
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.scroll_area)
        
        # 定时更新统计信息
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(5000)  # 每5秒更新
        
    def init_ui(self):
        # 设置内容小部件的布局
        layout = QVBoxLayout(self.content_widget)
        
        # 当前状态组
        status_group = QGroupBox("当前状态")
        status_layout = QVBoxLayout()
        
        # 当前端点
        endpoint_layout = QHBoxLayout()
        endpoint_layout.addWidget(QLabel("当前端点:"))
        self.current_endpoint_label = QLabel(self.api_manager.current_endpoint)
        self.current_endpoint_label.setStyleSheet("font-weight: bold; color: green;")
        endpoint_layout.addWidget(self.current_endpoint_label)
        endpoint_layout.addStretch()
        status_layout.addLayout(endpoint_layout)
        
        # 今日使用统计
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("今日已翻译:"))
        self.chars_today_label = QLabel("0 字符")
        self.chars_today_label.setStyleSheet("font-weight: bold; color: blue;")
        stats_layout.addWidget(self.chars_today_label)
        stats_layout.addStretch()
        
        stats_layout.addWidget(QLabel("端点序号:"))
        self.endpoint_index_label = QLabel("1/9")
        stats_layout.addWidget(self.endpoint_index_label)
        status_layout.addLayout(stats_layout)
        
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        # 智能策略组
        strategy_group = QGroupBox("智能绕过策略")
        strategy_layout = QVBoxLayout()
        
        # 自动切换设置
        switch_layout = QHBoxLayout()
        self.auto_switch_checkbox = QCheckBox("遇到限制时自动切换端点")
        self.auto_switch_checkbox.setChecked(True)
        switch_layout.addWidget(self.auto_switch_checkbox)
        strategy_layout.addLayout(switch_layout)
        
        # 请求延迟
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("请求间隔:"))
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(0, 5000)
        self.delay_spinbox.setValue(500)
        self.delay_spinbox.setSuffix(" 毫秒")
        delay_layout.addWidget(self.delay_spinbox)
        delay_layout.addWidget(QLabel("(降低被检测风险)"))
        delay_layout.addStretch()
        strategy_layout.addLayout(delay_layout)
        
        strategy_group.setLayout(strategy_layout)
        layout.addWidget(strategy_group)
        
        # 手动控制组
        control_group = QGroupBox("手动控制")
        control_layout = QVBoxLayout()
        
        # 按钮行1
        btn_row1 = QHBoxLayout()
        
        self.test_current_btn = QPushButton("测试当前端点")
        self.test_current_btn.clicked.connect(self.test_current_endpoint)
        btn_row1.addWidget(self.test_current_btn)
        
        self.find_best_btn = QPushButton("查找最佳端点")
        self.find_best_btn.clicked.connect(self.find_best_endpoint)
        btn_row1.addWidget(self.find_best_btn)
        
        self.next_endpoint_btn = QPushButton("下一个端点")
        self.next_endpoint_btn.clicked.connect(self.switch_next_endpoint)
        btn_row1.addWidget(self.next_endpoint_btn)
        
        control_layout.addLayout(btn_row1)
        
        # 按钮行2
        btn_row2 = QHBoxLayout()
        
        self.start_monitor_btn = QPushButton("开始自动监控")
        self.start_monitor_btn.clicked.connect(self.start_monitoring)
        btn_row2.addWidget(self.start_monitor_btn)
        
        self.stop_monitor_btn = QPushButton("停止监控")
        self.stop_monitor_btn.clicked.connect(self.stop_monitoring)
        self.stop_monitor_btn.setEnabled(False)
        btn_row2.addWidget(self.stop_monitor_btn)
        
        self.reset_stats_btn = QPushButton("重置统计")
        self.reset_stats_btn.clicked.connect(self.reset_daily_stats)
        btn_row2.addWidget(self.reset_stats_btn)
        
        control_layout.addLayout(btn_row2)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # 端点状态表
        endpoints_group = QGroupBox("所有端点状态")
        endpoints_layout = QVBoxLayout()
        
        self.endpoints_table = QTableWidget()
        self.endpoints_table.setColumnCount(3)
        self.endpoints_table.setHorizontalHeaderLabels(["端点地址", "状态", "响应时间"])
        self.endpoints_table.setAlternatingRowColors(True)
        
        # 设置列宽比例
        self.endpoints_table.setColumnWidth(0, 250)  # 端点地址列更宽
        self.endpoints_table.setColumnWidth(1, 120)  # 状态列中等宽度
        self.endpoints_table.setColumnWidth(2, 100)  # 响应时间列较窄
        
        # 设置表格固定高度以显示5行
        row_height = 30  # 每行高度
        header_height = self.endpoints_table.horizontalHeader().height()
        table_height = header_height + (row_height * 5)  # 表头高度 + 5行高度
        self.endpoints_table.setFixedHeight(table_height)
        
        # 设置行高
        self.endpoints_table.verticalHeader().setDefaultSectionSize(row_height)
        
        # 启用水平和垂直滚动条
        self.endpoints_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.endpoints_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 设置表头可拖动调整列宽
        self.endpoints_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.endpoints_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.endpoints_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        
        # 设置表头样式
        self.endpoints_table.horizontalHeader().setStyleSheet(
            "QHeaderView::section { background-color: #f0f0f0; padding: 4px; border: 1px solid #c0c0c0; }"
        )
        
        self.update_endpoints_table()
        
        endpoints_layout.addWidget(self.endpoints_table)
        endpoints_group.setLayout(endpoints_layout)
        layout.addWidget(endpoints_group)
        
        # 日志区域
        log_group = QGroupBox("活动日志")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(100)
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # 添加弹性空间，确保内容可以滚动
        layout.addStretch()
    
    def setup_connections(self):
        """设置信号连接"""
        # 确保信号使用正确的类型
        self.api_manager.endpoint_status_updated.connect(
            self.on_endpoint_status_updated, 
            Qt.QueuedConnection  # 使用队列连接确保线程安全
        )
        self.api_manager.api_switched.connect(
            self.on_api_switched,
            Qt.QueuedConnection  # 使用队列连接确保线程安全
        )
        self.api_manager.limit_reached.connect(
            self.on_limit_reached,
            Qt.QueuedConnection  # 使用队列连接确保线程安全
        )
        
        # 策略设置连接
        self.auto_switch_checkbox.toggled.connect(
            lambda checked: setattr(self.api_manager, 'auto_switch_on_limit', checked)
        )
        self.delay_spinbox.valueChanged.connect(
            lambda value: setattr(self.api_manager, 'request_delay', value / 1000.0)
        )
    
    def update_endpoints_table(self):
        """更新端点表格"""
        endpoints = self.api_manager.endpoints
        self.endpoints_table.setRowCount(len(endpoints))
        
        for i, endpoint in enumerate(endpoints):
            # 端点地址（简化显示）
            url_display = endpoint.replace("https://", "").replace("/translate_a/single", "")
            url_item = QTableWidgetItem(url_display)
            if i == self.api_manager.current_endpoint_index:
                url_item.setBackground(QColor(200, 255, 200))
            self.endpoints_table.setItem(i, 0, url_item)
            
            # 状态
            status_item = QTableWidgetItem("未测试")
            self.endpoints_table.setItem(i, 1, status_item)
            
            # 响应时间
            time_item = QTableWidgetItem("-")
            self.endpoints_table.setItem(i, 2, time_item)

            # 调整列宽以适应内容
            self.endpoints_table.resizeColumnsToContents()
            # 确保第一列有最小宽度，以便显示完整的URL
            if self.endpoints_table.columnWidth(0) < 250:
                self.endpoints_table.setColumnWidth(0, 250)
    
    def update_stats(self):
        """更新统计信息显示"""
        stats = self.api_manager.get_daily_stats()
        self.chars_today_label.setText(f"{stats['chars_today']:,} 字符")
        self.endpoint_index_label.setText(f"{stats['endpoint_index']}/{stats['total_endpoints']}")
        self.current_endpoint_label.setText(
            stats['current_endpoint'].replace("https://", "").replace("/translate_a/single", "")
        )
    
    def test_current_endpoint(self):
        """测试当前端点"""
        endpoint = self.api_manager.current_endpoint
        self.add_log(f"正在测试: {endpoint}")
        
        def test_in_thread():
            is_working, message, response_time = self.api_manager.test_endpoint(endpoint)
            if is_working:
                self.add_log(f"✅ 当前端点正常: {message}")
            else:
                self.add_log(f"❌ 当前端点异常: {message}")
        
        threading.Thread(target=test_in_thread, daemon=True).start()
    
    def find_best_endpoint(self):
        """查找最佳端点"""
        self.add_log("🔍 正在查找最佳端点...")
        
        def find_in_thread():
            success, best_time = self.api_manager.find_best_endpoint()
            if success:
                self.add_log(f"✅ 已切换到最佳端点 ({best_time:.2f}s)")
                self.update_stats()
                self.update_endpoints_table()
            else:
                self.add_log("❌ 未找到可用端点")
        
        threading.Thread(target=find_in_thread, daemon=True).start()
    
    def switch_next_endpoint(self):
        """切换到下一个端点"""
        old_endpoint = self.api_manager.current_endpoint
        self.api_manager.switch_to_next_endpoint()
        self.add_log(f"🔄 手动切换到下一个端点")
        self.update_stats()
        self.update_endpoints_table()
    
    def start_monitoring(self):
        """开始监控"""
        self.api_manager.check_interval = 300  # 5分钟
        self.api_manager.auto_switch_enabled = True
        self.api_manager.start_monitoring()
        
        self.start_monitor_btn.setEnabled(False)
        self.stop_monitor_btn.setEnabled(True)
        self.add_log("✅ 自动监控已启动")
    
    def stop_monitoring(self):
        """停止监控"""
        self.api_manager.stop_monitoring()
        self.start_monitor_btn.setEnabled(True)
        self.stop_monitor_btn.setEnabled(False)
        self.add_log("⏹️ 自动监控已停止")
    
    def reset_daily_stats(self):
        """重置每日统计"""
        self.api_manager.daily_char_count = 0
        self.api_manager.save_daily_stats()
        self.update_stats()
        self.add_log("📊 每日统计已重置")
    
    def on_endpoint_status_updated(self, url, is_working, message, response_time):
        """更新端点状态"""
        for i in range(self.endpoints_table.rowCount()):
            url_item = self.endpoints_table.item(i, 0)
            full_url = self.api_manager.endpoints[i]
            
            if full_url == url:
                # 更新状态
                status_text = "✅ 正常" if is_working else f"❌ {message}"
                status_item = self.endpoints_table.item(i, 1)
                status_item.setText(status_text)
                
                # 设置颜色
                color = QColor(200, 255, 200) if is_working else QColor(255, 200, 200)
                status_item.setBackground(color)
                
                # 更新响应时间
                time_text = f"{response_time:.2f}s" if response_time > 0 else "-"
                time_item = self.endpoints_table.item(i, 2)
                time_item.setText(time_text)
                break
    
    def on_api_switched(self, old_url, new_url):
        """处理API切换"""
        self.update_stats()
        self.update_endpoints_table()
        self.add_log(f"🔄 自动切换端点")
    
    def on_limit_reached(self, message):
        """处理限制触发"""
        self.add_log(f"⚠️ {message}")
    
    def add_log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_text.append(log_entry)
        
        # 限制日志行数
        if self.log_text.document().blockCount() > 50:
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.LineUnderCursor)
            cursor.removeSelectedText()
        
        # 滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

# 使用示例
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    dialog = GoogleAPIDialog()
    dialog.setWindowTitle("Google翻译API智能管理器")
    dialog.resize(600, 650)  # 设置初始大小
    dialog.show()
    
    sys.exit(app.exec_())