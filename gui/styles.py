"""
Outreach Hub - Theme Styles
"""

DARK_STYLE = """
/* Main Window */
QMainWindow {
    background-color: #1a1a2e;
}

QWidget {
    background-color: #1a1a2e;
    color: #eaeaea;
    font-family: 'Segoe UI', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
    font-size: 13px;
}

/* Tab Widget */
QTabWidget::pane {
    border: none;
    background-color: #16213e;
    border-radius: 10px;
    padding: 10px;
}

QTabBar::tab {
    background-color: #0f3460;
    color: #a0a0a0;
    padding: 12px 24px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #16213e;
    color: #00d9ff;
    font-weight: 600;
}

QTabBar::tab:hover:!selected {
    background-color: #1a3a5c;
    color: #ffffff;
}

/* Buttons */
QPushButton {
    background-color: #0f3460;
    color: #ffffff;
    border: none;
    padding: 10px 20px;
    border-radius: 6px;
    font-weight: 500;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #1a4a7a;
}

QPushButton:pressed {
    background-color: #0a2540;
}

QPushButton:disabled {
    background-color: #2a2a4a;
    color: #606080;
}

/* Primary Action Buttons */
QPushButton[class="primary"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d9ff, stop:1 #00a8cc);
    color: #1a1a2e;
    font-weight: 600;
}

QPushButton[class="primary"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #33e0ff, stop:1 #33b8d9);
}

/* Success Buttons */
QPushButton[class="success"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00c851, stop:1 #00a040);
    color: white;
}

QPushButton[class="success"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00e05a, stop:1 #00b848);
}

/* Warning Buttons */
QPushButton[class="warning"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffbb33, stop:1 #ff9500);
    color: #1a1a2e;
}

QPushButton[class="warning"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ffc94d, stop:1 #ffa31a);
}

/* Danger Buttons */
QPushButton[class="danger"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff4444, stop:1 #cc0000);
    color: white;
}

QPushButton[class="danger"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff6666, stop:1 #e60000);
}

/* Purple Buttons */
QPushButton[class="purple"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #9c27b0, stop:1 #7b1fa2);
    color: white;
}

QPushButton[class="purple"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ab47bc, stop:1 #8e24aa);
}

/* Input Fields */
QLineEdit, QTextEdit, QSpinBox {
    background-color: #0f3460;
    border: 2px solid #1a4a7a;
    border-radius: 6px;
    padding: 8px 12px;
    color: #ffffff;
    selection-background-color: #00d9ff;
    font-family: 'Segoe UI', 'Malgun Gothic', sans-serif;
}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
    border-color: #00d9ff;
}

QLineEdit::placeholder, QTextEdit::placeholder {
    color: #606080;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #1a4a7a;
    border: none;
    width: 20px;
}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #2a5a8a;
}

/* Checkboxes */
QCheckBox {
    spacing: 8px;
    color: #c0c0c0;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 4px;
    border: 2px solid #1a4a7a;
    background-color: #0f3460;
}

QCheckBox::indicator:checked {
    background-color: #00d9ff;
    border-color: #00d9ff;
}

QCheckBox::indicator:hover {
    border-color: #00d9ff;
}

/* Tables */
QTableWidget {
    background-color: #16213e;
    alternate-background-color: #1a2a4e;
    border: none;
    border-radius: 8px;
    gridline-color: #0f3460;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #0f3460;
}

QTableWidget::item:selected {
    background-color: #00d9ff;
    color: #1a1a2e;
}

QHeaderView::section {
    background-color: #0f3460;
    color: #00d9ff;
    padding: 10px;
    border: none;
    font-weight: 600;
}

/* Group Boxes */
QGroupBox {
    background-color: #16213e;
    border: 1px solid #0f3460;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 24px;
    font-weight: 600;
}

QGroupBox::title {
    color: #00d9ff;
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 8px;
}

/* Scrollbars */
QScrollBar:vertical {
    background-color: #0f3460;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #1a4a7a;
    border-radius: 6px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #00d9ff;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #0f3460;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #1a4a7a;
    border-radius: 6px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #00d9ff;
}

/* Labels */
QLabel {
    color: #c0c0c0;
}

QLabel[class="header"] {
    font-size: 24px;
    font-weight: 700;
    color: #ffffff;
}

QLabel[class="subheader"] {
    font-size: 14px;
    font-weight: 600;
    color: #00d9ff;
}

/* Status Bar */
QStatusBar {
    background-color: #0f3460;
    color: #00d9ff;
    border-top: 1px solid #1a4a7a;
}

/* Message Box */
QMessageBox {
    background-color: #1a1a2e;
}

QMessageBox QLabel {
    color: #eaeaea;
}

/* List Widget */
QListWidget {
    background-color: #16213e;
    border: 2px solid #0f3460;
    border-radius: 6px;
    padding: 4px;
}

QListWidget::item {
    padding: 8px;
    border-radius: 4px;
}

QListWidget::item:selected {
    background-color: #00d9ff;
    color: #1a1a2e;
}

/* Dialog */
QDialog {
    background-color: #1a1a2e;
}

/* Progress Bar */
QProgressBar {
    background-color: #0f3460;
    border: none;
    border-radius: 6px;
    height: 20px;
    text-align: center;
    color: #ffffff;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d9ff, stop:1 #00a8cc);
    border-radius: 6px;
}

/* Combo Box */
QComboBox {
    background-color: #0f3460;
    border: 2px solid #1a4a7a;
    border-radius: 6px;
    padding: 8px 12px;
    color: #ffffff;
    min-width: 100px;
}

QComboBox:hover {
    border-color: #00d9ff;
}

QComboBox QAbstractItemView {
    background-color: #16213e;
    border: 1px solid #1a4a7a;
    selection-background-color: #00d9ff;
    selection-color: #1a1a2e;
}
"""


LIGHT_STYLE = """
/* Main Window */
QMainWindow {
    background-color: #f5f7fa;
}

QWidget {
    background-color: #f5f7fa;
    color: #333333;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

/* Tab Widget */
QTabWidget::pane {
    border: 1px solid #e0e0e0;
    background-color: #ffffff;
    border-radius: 10px;
    padding: 10px;
}

QTabBar::tab {
    background-color: #e0e0e0;
    color: #666666;
    padding: 12px 24px;
    margin-right: 4px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #007bff; /* Blue */
    font-weight: 600;
    border-bottom: 2px solid #007bff;
}

QTabBar::tab:hover:!selected {
    background-color: #d0d0d0;
    color: #333333;
}

/* Buttons */
QPushButton {
    background-color: #ffffff;
    color: #333333;
    border: 1px solid #cccccc;
    padding: 10px 20px;
    border-radius: 6px;
    font-weight: 500;
    min-width: 80px;
}

QPushButton:hover {
    background-color: #f0f0f0;
    border-color: #999999;
}

QPushButton:pressed {
    background-color: #e0e0e0;
}

QPushButton:disabled {
    background-color: #f0f0f0;
    color: #a0a0a0;
    border-color: #e0e0e0;
}

/* Primary Action Buttons */
QPushButton[class="primary"] {
    background-color: #007bff;
    color: #ffffff;
    border: none;
    font-weight: 600;
}
QPushButton[class="primary"]:hover { background-color: #0056b3; }

/* Success Buttons */
QPushButton[class="success"] {
    background-color: #28a745;
    color: #ffffff;
    border: none;
}
QPushButton[class="success"]:hover { background-color: #1e7e34; }

/* Warning Buttons */
QPushButton[class="warning"] {
    background-color: #ffc107;
    color: #333333;
    border: none;
}
QPushButton[class="warning"]:hover { background-color: #d39e00; }

/* Danger Buttons */
QPushButton[class="danger"] {
    background-color: #dc3545;
    color: #ffffff;
    border: none;
}
QPushButton[class="danger"]:hover { background-color: #bd2130; }

/* Purple Buttons (Custom) */
QPushButton[class="purple"] {
    background-color: #6f42c1;
    color: white;
    border: none;
}
QPushButton[class="purple"]:hover { background-color: #5a32a3; }


/* Input Fields */
QLineEdit, QTextEdit, QSpinBox {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 6px;
    padding: 8px 12px;
    color: #333333;
    selection-background-color: #007bff;
    selection-color: #ffffff;
}

QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
    border-color: #007bff;
    background-color: #ffffff;
}

QLineEdit::placeholder, QTextEdit::placeholder {
    color: #999999;
}

QSpinBox::up-button, QSpinBox::down-button {
    background-color: #f0f0f0;
    border: none;
    width: 20px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background-color: #e0e0e0; }


/* Checkboxes */
QCheckBox {
    spacing: 8px;
    color: #333333;
    background-color: transparent;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #999999;
    background-color: #ffffff;
}
QCheckBox::indicator:checked {
    background-color: #007bff;
    border-color: #007bff;
}
QCheckBox::indicator:hover {
    border-color: #007bff;
}


/* Tables */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f9f9f9;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    gridline-color: #eeeeee;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #eeeeee;
    color: #333333;
}

QTableWidget::item:selected {
    background-color: #007bff;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #f0f0f0;
    color: #333333;
    padding: 10px;
    border: none;
    border-bottom: 1px solid #cccccc;
    font-weight: 600;
}

/* Group Boxes */
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    margin-top: 20px; /* Space for title */
    padding-top: 20px;
    font-weight: 600;
}

QGroupBox::title {
    color: #007bff;
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 5px;
    background-color: transparent;
}


/* Scrollbars */
QScrollBar:vertical {
    background-color: #f0f0f0;
    width: 12px;
    border-radius: 6px;
}
QScrollBar::handle:vertical {
    background-color: #cccccc;
    border-radius: 6px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover { background-color: #999999; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }

QScrollBar:horizontal {
    background-color: #f0f0f0;
    height: 12px;
    border-radius: 6px;
}
QScrollBar::handle:horizontal {
    background-color: #cccccc;
    border-radius: 6px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover { background-color: #999999; }


/* Labels */
QLabel {
    color: #333333;
    background-color: transparent;
}

QLabel[class="header"] {
    font-size: 24px;
    font-weight: 700;
    color: #333333;
}

QLabel[class="subheader"] {
    font-size: 14px;
    font-weight: 600;
    color: #007bff;
}


/* Status Bar */
QStatusBar {
    background-color: #e0e0e0;
    color: #333333;
    border-top: 1px solid #cccccc;
}

/* Message Box */
QMessageBox {
    background-color: #ffffff;
}
QMessageBox QLabel {
    color: #333333;
}

/* List Widget */
QListWidget {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 6px;
    padding: 4px;
}
QListWidget::item {
    padding: 8px;
    border-radius: 4px;
    color: #333333;
}
QListWidget::item:selected {
    background-color: #007bff;
    color: #ffffff;
}
QListWidget::item:hover:!selected {
    background-color: #f0f0f0;
}

/* Dialog */
QDialog {
    background-color: #f5f7fa;
}


/* Progress Bar */
QProgressBar {
    background-color: #e0e0e0;
    border: 1px solid #cccccc;
    border-radius: 6px;
    height: 20px;
    text-align: center;
    color: #333333;
}
QProgressBar::chunk {
    background-color: #28a745;
    border-radius: 5px;
}

/* Combo Box */
QComboBox {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    border-radius: 6px;
    padding: 8px 12px;
    color: #333333;
    min-width: 100px;
}
QComboBox:hover { border-color: #007bff; }

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 1px solid #cccccc;
    selection-background-color: #007bff;
    selection-color: #ffffff;
    color: #333333;
}
"""
