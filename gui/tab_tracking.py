"""Tracking Tab - Email open/click tracking dashboard.

Fetches tracking data from Cloudflare KV via the bulk-stats API
and displays it in a sortable table.
"""

from __future__ import annotations

import json
from urllib.request import urlopen, Request
from urllib.error import URLError
from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QDialog,
)
from PySide6.QtCore import Qt, QThread, Signal

import config
import db


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRACKING_BASE_URL = config.TRACKING_BASE_URL.rstrip("/")

# Read from wrangler.toml at import time is fragile; store key here.
# This matches wrangler.toml [vars] STATS_API_KEY.
_STATS_API_KEY = "1a66b85664c5574c9c078fa240299c17ea1d4929560074d6"

# Column definitions: (header_text, data_key, default_width)
COLUMNS = [
    ("Date", "date", 90),
    ("Company", "company", 200),
    ("Contact", "contact", 150),
    ("Email", "email", 200),
    ("Opens", "open_count", 65),
    ("Clicks", "click_count", 65),
    ("Last Open", "last_open", 160),
    ("Last Click", "last_click", 160),
    ("Status", "status", 80),
    ("Tracking ID", "tracking_id", 120),
]


# ---------------------------------------------------------------------------
# Background Worker
# ---------------------------------------------------------------------------

class TrackingFetchWorker(QThread):
    """Fetch outreach records from SQLite, then query Cloudflare bulk-stats."""

    finished = Signal(list)  # list[dict]
    error = Signal(str)

    def run(self) -> None:
        try:
            rows = self._fetch()
            self.finished.emit(rows)
        except Exception as exc:
            self.error.emit(str(exc))

    def _fetch(self) -> list[dict]:
        db.init()
        records = db.get_tracking_records()

        # Collect tracking IDs with metadata
        tid_map: dict[str, dict] = {}
        for row in records:
            tid = str(row.get("tracking_id", "")).strip()
            if not tid:
                continue
            contact = str(row.get("contact_person", "")).strip()
            tid_map[tid] = {
                "tracking_id": tid,
                "date": str(row.get("date", "")),
                "company": str(row.get("company", "")),
                "contact": contact,
                "email": str(row.get("email", "")),
                "status": str(row.get("status", "")),
                "open_count": 0,
                "click_count": 0,
                "last_open": "",
                "last_click": "",
            }

        if not tid_map:
            return []

        # Query Cloudflare bulk-stats (max 50 per request)
        all_tids = list(tid_map.keys())
        for i in range(0, len(all_tids), 50):
            batch = all_tids[i : i + 50]
            tids_param = ",".join(batch)
            url = f"{TRACKING_BASE_URL}/bulk-stats?key={_STATS_API_KEY}&tids={tids_param}"
            try:
                req = Request(url, method="GET")
                req.add_header("User-Agent", "LeadGenPro/1.0")
                with urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode())
                results = data.get("results", {})
                for tid, stats in results.items():
                    if tid in tid_map:
                        tid_map[tid]["open_count"] = stats.get("open_count", 0)
                        tid_map[tid]["click_count"] = stats.get("click_count", 0)
                        last_open = stats.get("last_open") or ""
                        last_click = stats.get("last_click") or ""
                        # Format ISO timestamps for display
                        if last_open:
                            last_open = last_open.replace("T", " ")[:19]
                        if last_click:
                            last_click = last_click.replace("T", " ")[:19]
                        tid_map[tid]["last_open"] = last_open
                        tid_map[tid]["last_click"] = last_click
            except (URLError, Exception):
                # If API fails, leave counts at 0 but still show the rows
                pass

        return list(tid_map.values())


# ---------------------------------------------------------------------------
# Numeric-aware table item for proper sorting
# ---------------------------------------------------------------------------

class NumericTableItem(QTableWidgetItem):
    """QTableWidgetItem that sorts numerically when the value is a number."""

    def __lt__(self, other: QTableWidgetItem) -> bool:
        def _to_float(text: str) -> float:
            try:
                return float(text)
            except (ValueError, TypeError):
                return 0.0

        return _to_float(self.text()) < _to_float(other.text())


# ---------------------------------------------------------------------------
# Daily Stats Dialog
# ---------------------------------------------------------------------------

class DailyStatsDialog(QDialog):
    """Dialog to show daily breakdown of open rates."""
    def __init__(self, data: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Daily Tracking Report")
        self.resize(600, 400)
        self.data = data
        self.layout = QVBoxLayout(self)
        self._build_ui()

    def _build_ui(self):
        # Calculate stats
        stats = defaultdict(lambda: {"sent": 0, "opened": 0, "clicked": 0})
        total_sent = 0
        total_opened = 0

        for row in self.data:
            date = row.get("date", "Unknown")
            stats[date]["sent"] += 1
            total_sent += 1
            if row.get("open_count", 0) > 0:
                stats[date]["opened"] += 1
                total_opened += 1
            if row.get("click_count", 0) > 0:
                stats[date]["clicked"] += 1

        # Summary Label
        overall_rate = (total_opened / total_sent * 100) if total_sent > 0 else 0
        summary = QLabel(f"<b>Overall Open Rate:</b> {overall_rate:.1f}% ({total_opened}/{total_sent})")
        summary.setStyleSheet("font-size: 14px; margin-bottom: 10px;")
        self.layout.addWidget(summary)

        # Table
        table = QTableWidget()
        columns = ["Date", "Sent", "Opened", "Open Rate", "Clicked"]
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(True)

        sorted_dates = sorted(stats.keys(), reverse=True)
        table.setRowCount(len(sorted_dates))

        for row_idx, date in enumerate(sorted_dates):
            s = stats[date]
            sent = s["sent"]
            opened = s["opened"]
            clicked = s["clicked"]
            rate = (opened / sent * 100) if sent > 0 else 0.0

            table.setItem(row_idx, 0, QTableWidgetItem(date))

            item_sent = NumericTableItem(str(sent))
            item_sent.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_idx, 1, item_sent)

            item_opened = NumericTableItem(str(opened))
            item_opened.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_idx, 2, item_opened)

            item_rate = NumericTableItem(f"{rate:.1f}")  # Store as string number for sorting?
            # Actually NumericTableItem parses float, so "12.5" is fine.
            # But let's append '%' for display and handle sorting if needed.
            # Using basic QTableWidgetItem for rate string might sort alphabetically "10%" < "2%".
            # Let's use NumericTableItem and just store average numeric value, or subclass.
            # For simplicity, let's use NumericTableItem with just the number.
            item_rate.setText(f"{rate:.1f}")
            item_rate.setToolTip(f"{rate:.1f}%")
            item_rate.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_idx, 3, item_rate)

            item_clicked = NumericTableItem(str(clicked))
            item_clicked.setTextAlignment(Qt.AlignCenter)
            table.setItem(row_idx, 4, item_clicked)

        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout.addWidget(table)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        self.layout.addWidget(btn_close)


# ---------------------------------------------------------------------------
# Tracking Tab Widget
# ---------------------------------------------------------------------------

class TrackingTab(QWidget):
    def __init__(self, log_callback=None):
        super().__init__()
        self._log = log_callback or (lambda msg: None)
        self._data: list[dict] = []
        self._worker: TrackingFetchWorker | None = None
        self._build_ui()

    # -- UI Construction ----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Header row
        header_row = QHBoxLayout()

        title = QLabel("Email Tracking Dashboard")
        title.setProperty("class", "subheader")
        header_row.addWidget(title)

        header_row.addStretch()

        self.stats_label = QLabel("")
        header_row.addWidget(self.stats_label)

        self.btn_daily_report = QPushButton("Daily Report")
        self.btn_daily_report.setProperty("class", "default")
        self.btn_daily_report.setCursor(Qt.PointingHandCursor)
        self.btn_daily_report.clicked.connect(self.show_daily_report)
        self.btn_daily_report.setEnabled(False) # Enabled only when data is loaded
        header_row.addWidget(self.btn_daily_report)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setProperty("class", "primary")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.refresh)
        header_row.addWidget(self.btn_refresh)

        layout.addLayout(header_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(COLUMNS))
        self.table.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)

        # Default column widths
        for i, (_, _, width) in enumerate(COLUMNS):
            self.table.setColumnWidth(i, width)

        # Stretch the Company column
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)

        layout.addWidget(self.table)

    # -- Data Loading -------------------------------------------------------

    def refresh(self) -> None:
        if self._worker and self._worker.isRunning():
            return

        self.btn_refresh.setEnabled(False)
        self.btn_daily_report.setEnabled(False)
        self.btn_refresh.setText("Loading...")
        self.stats_label.setText("Fetching tracking data...")

        self._worker = TrackingFetchWorker()
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_data_loaded(self, data: list[dict]) -> None:
        self._data = data
        self._render_table()
        self.btn_refresh.setEnabled(True)
        self.btn_daily_report.setEnabled(True)
        self.btn_refresh.setText("Refresh")

        total = len(data)
        opened = sum(1 for d in data if d["open_count"] > 0)
        clicked = sum(1 for d in data if d["click_count"] > 0)
        total_opens = sum(d["open_count"] for d in data)
        open_rate = f"{opened / total * 100:.1f}%" if total > 0 else "N/A"

        self.stats_label.setText(
            f"Total: {total} | Opened: {opened} ({open_rate}) | "
            f"Clicked: {clicked} | Total opens: {total_opens}"
        )
        self._log(f"Tracking data loaded: {total} emails, {opened} opened")

    def _on_error(self, msg: str) -> None:
        self.btn_refresh.setEnabled(True)
        self.btn_daily_report.setEnabled(False)
        self.btn_refresh.setText("Refresh")
        self.stats_label.setText(f"Error: {msg}")
        self._log(f"Tracking fetch error: {msg}")

    def show_daily_report(self):
        if not self._data:
            return
        dlg = DailyStatsDialog(self._data, self)
        dlg.exec()

    # -- Table Rendering ----------------------------------------------------

    def _render_table(self) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._data))

        for row_idx, row_data in enumerate(self._data):
            for col_idx, (_, key, _) in enumerate(COLUMNS):
                value = row_data.get(key, "")
                text = str(value) if value else ""

                # Use numeric-aware item for Opens and Clicks columns
                if key in ("open_count", "click_count"):
                    item = NumericTableItem(text)
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item = QTableWidgetItem(text)

                self.table.setItem(row_idx, col_idx, item)

            # Color coding: opened = green tint, not opened = no color
            open_count = row_data.get("open_count", 0)
            if open_count > 0:
                from PySide6.QtGui import QColor
                color = QColor("#e8f5e9")  # Light green
                for col_idx in range(len(COLUMNS)):
                    item = self.table.item(row_idx, col_idx)
                    if item:
                        item.setBackground(color)

        self.table.setSortingEnabled(True)
        # Default sort: by Opens descending
        self.table.sortByColumn(4, Qt.DescendingOrder)
