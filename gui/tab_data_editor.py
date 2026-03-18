from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget
)


class DataEditorTab(QWidget):
    def __init__(self, on_load, on_save, on_add_row, on_del_row, on_import):
        super().__init__()
        self._build_ui(on_load, on_save, on_add_row, on_del_row, on_import)

    def _build_ui(self, on_load, on_save, on_add_row, on_del_row, on_import):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.editor_path = QLineEdit()
        self.editor_path.setPlaceholderText("Path to CSV file...")
        top.addWidget(self.editor_path)

        btn_load = QPushButton("Load CSV")
        btn_load.clicked.connect(on_load)
        top.addWidget(btn_load)

        btn_save = QPushButton("Save CSV")
        btn_save.setProperty("class", "success")
        btn_save.clicked.connect(on_save)
        top.addWidget(btn_save)

        btn_import = QPushButton("Import to Leads DB")
        btn_import.setProperty("class", "primary")
        btn_import.clicked.connect(on_import)
        top.addWidget(btn_import)

        layout.addLayout(top)

        self.editor_table = QTableWidget()
        layout.addWidget(self.editor_table)

        row_btns = QHBoxLayout()
        btn_add_row = QPushButton("Add Row")
        btn_add_row.clicked.connect(on_add_row)
        row_btns.addWidget(btn_add_row)

        btn_del_row = QPushButton("Delete Row")
        btn_del_row.setProperty("class", "warning")
        btn_del_row.clicked.connect(on_del_row)
        row_btns.addWidget(btn_del_row)

        row_btns.addStretch()
        self.editor_status = QLabel("")
        row_btns.addWidget(self.editor_status)

        layout.addLayout(row_btns)
