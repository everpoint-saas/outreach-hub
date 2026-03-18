from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QAbstractItemView, QHeaderView
)


class HistoryTab(QWidget):
    def __init__(self, on_filter_changed, on_refresh, on_mark_unsent, on_mark_replied, on_remove):
        super().__init__()
        self._build_ui(on_filter_changed, on_refresh, on_mark_unsent, on_mark_replied, on_remove)

    def _build_ui(self, on_filter_changed, on_refresh, on_mark_unsent, on_mark_replied, on_remove):
        layout = QVBoxLayout(self)

        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter:")
        filter_layout.addWidget(filter_label)

        self.history_filter = QComboBox()
        self.history_filter.addItems(["All", "Sent", "Skipped", "Follow-up Sent", "Replied"])
        self.history_filter.currentTextChanged.connect(on_filter_changed)
        filter_layout.addWidget(self.history_filter)

        filter_layout.addStretch()

        self.history_stats_label = QLabel("")
        self.history_stats_label.setProperty("class", "subheader")
        filter_layout.addWidget(self.history_stats_label)

        layout.addLayout(filter_layout)

        self.history_table = QTableWidget()
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.history_table)

        hist_btn_layout = QHBoxLayout()

        btn_refresh_hist = QPushButton("Refresh")
        btn_refresh_hist.clicked.connect(on_refresh)
        hist_btn_layout.addWidget(btn_refresh_hist)

        btn_unsend = QPushButton("Mark as Unsent")
        btn_unsend.setProperty("class", "warning")
        btn_unsend.clicked.connect(on_mark_unsent)
        hist_btn_layout.addWidget(btn_unsend)

        btn_replied = QPushButton("Mark as Replied")
        btn_replied.setProperty("class", "success")
        btn_replied.clicked.connect(on_mark_replied)
        hist_btn_layout.addWidget(btn_replied)

        btn_remove_hist = QPushButton("Delete from History")
        btn_remove_hist.setProperty("class", "danger")
        btn_remove_hist.clicked.connect(on_remove)
        hist_btn_layout.addWidget(btn_remove_hist)

        layout.addLayout(hist_btn_layout)
