import os
import sys
import traceback
from datetime import datetime

import pandas as pd
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QTabWidget,
    QMessageBox,
    QGroupBox,
    QTableWidgetItem,
    QFileDialog,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush

from .styles import DARK_STYLE, LIGHT_STYLE

from google_maps_scraper import ScraperState
import process_leads
import followup_manager
import db
import config

from .dialogs import ScoringDialog, BlacklistDialog, EmailCampaignDialog, CsvImportDialog
from .workers import ScraperThread, PipelineThread, SmartHuntWorker
from .tab_mailing import MailingTab
from .tab_google_maps import GoogleMapsTab
from .tab_setup import SetupTab

from .tab_pipeline import PipelineTab
from .tab_history import HistoryTab
from .tab_data_editor import DataEditorTab
from .tab_tracking import TrackingTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.resize(1200, 850)

        self.current_theme = "LIGHT"
        self.setStyleSheet(LIGHT_STYLE)

        self.scraper_state = ScraperState()
        self.custom_blacklist = None
        self.custom_score_keywords = None

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)

        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(config.APP_NAME)
        header.setProperty("class", "header")
        header_layout.addWidget(header)

        self.btn_theme = QPushButton("Dark Mode")
        self.btn_theme.setCursor(Qt.PointingHandCursor)
        self.btn_theme.setFixedWidth(120)
        self.btn_theme.clicked.connect(self.toggle_theme)
        header_layout.addWidget(self.btn_theme)

        header_layout.addStretch()

        header_sub = QLabel(config.APP_SUBTITLE)
        header_sub.setProperty("class", "subheader")
        header_sub.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        header_layout.addWidget(header_sub)

        main_layout.addWidget(header_container)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_setup = SetupTab(on_save=self.save_setup_settings)
        self.tabs.addTab(self.tab_setup, "Setup")

        self.tab_maps = GoogleMapsTab(
            on_run=self.run_maps,
            on_toggle_location=self.toggle_location_input,
            on_set_keywords=self.set_maps_keywords,
        )
        self.tabs.addTab(self.tab_maps, "Google Maps Scraper")

        self.tab_pipeline = PipelineTab(
            on_edit_scoring=self.edit_scoring,
            on_edit_blacklist=self.edit_blacklist,
            on_run_pipeline=self.run_pipeline,
            on_run_email_crawler=self.run_email_crawler,
            on_refresh_targets=self.load_targets,
            on_run_smart_hunt=self.run_smart_hunt,
            on_create_drafts_selected=self.create_drafts_for_selected,
            on_mark_selected_sent=self.mark_selected_sent,
            on_mark_all_sent=self.mark_all_sent,
            on_targets_click=self.targets_table_clicked,
            on_targets_hover=self.targets_table_hover,
            on_verify_emails=self.run_email_verification,
        )
        self.tab_pipeline.btn_reset_targets.clicked.connect(self.reset_today_targets)
        self.tabs.addTab(self.tab_pipeline, "Pipeline & Targets")

        self.tab_history = HistoryTab(
            on_filter_changed=self.load_history,
            on_refresh=self.load_history,
            on_mark_unsent=self.mark_as_unsent,
            on_mark_replied=self.mark_as_replied,
            on_remove=self.remove_from_history,
        )
        self.tabs.addTab(self.tab_history, "History")

        self.tab_editor = DataEditorTab(
            on_load=self.load_csv_to_editor,
            on_save=self.save_csv_from_editor,
            on_add_row=self.add_editor_row,
            on_del_row=self.del_editor_row,
            on_import=self.import_editor_csv_to_db,
        )
        self.tabs.addTab(self.tab_editor, "Data Editor")

        self.tab_mailing = MailingTab()
        self.tabs.addTab(self.tab_mailing, "Mailing (Gmail)")

        self.tab_tracking = TrackingTab(log_callback=self.log)
        self.tabs.addTab(self.tab_tracking, "Tracking")

        # Alias widgets to keep legacy logic concise
        self.maps_location = self.tab_maps.maps_location
        self.chk_city_loop = self.tab_maps.chk_city_loop
        self.maps_max_results = self.tab_maps.maps_max_results
        self.maps_input = self.tab_maps.maps_input
        self.maps_headless = self.tab_maps.maps_headless
        self.btn_maps_run = self.tab_maps.btn_maps_run

        self.daily_target_spin = self.tab_pipeline.daily_target_spin
        self.targets_table = self.tab_pipeline.targets_table

        self.history_filter = self.tab_history.history_filter
        self.history_table = self.tab_history.history_table
        self.history_stats_label = self.tab_history.history_stats_label

        self.editor_path = self.tab_editor.editor_path
        self.editor_table = self.tab_editor.editor_table
        self.editor_status = self.tab_editor.editor_status

        control_group = QGroupBox("Scraper Control")
        control_layout = QHBoxLayout(control_group)

        self.btn_pause = QPushButton("Pause")
        self.btn_pause.setProperty("class", "warning")
        self.btn_pause.clicked.connect(self.pause_scraper)
        self.btn_pause.setEnabled(False)
        control_layout.addWidget(self.btn_pause)

        self.btn_resume = QPushButton("Resume")
        self.btn_resume.setProperty("class", "success")
        self.btn_resume.clicked.connect(self.resume_scraper)
        self.btn_resume.setEnabled(False)
        control_layout.addWidget(self.btn_resume)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setProperty("class", "danger")
        self.btn_stop.clicked.connect(self.stop_scraper)
        self.btn_stop.setEnabled(False)
        control_layout.addWidget(self.btn_stop)

        main_layout.addWidget(control_group)

        log_label = QLabel("Execution Log")
        log_label.setProperty("class", "subheader")
        main_layout.addWidget(log_label)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(140)
        main_layout.addWidget(self.log_area)

        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)

        self.worker = None
        self.pipeline_worker = None

        self.load_targets()
        self.load_history()

    def toggle_theme(self):
        if self.current_theme == "DARK":
            self.setStyleSheet(LIGHT_STYLE)
            self.current_theme = "LIGHT"
            self.btn_theme.setText("Dark Mode")
        else:
            self.setStyleSheet(DARK_STYLE)
            self.current_theme = "DARK"
            self.btn_theme.setText("Light Mode")

    def set_maps_keywords(self, keywords):
        self.maps_input.setText("\n".join(keywords))

    def edit_scoring(self):
        dlg = ScoringDialog(parent=self, score_keywords=process_leads.SCORE_KEYWORDS)
        if dlg.exec():
            self.custom_score_keywords = dlg.get_keywords()
            self.log("Updated scoring rules (will apply on next pipeline run).")

    def edit_blacklist(self):
        dlg = BlacklistDialog(parent=self, blacklist=process_leads.BLACKLIST)
        if dlg.exec():
            self.custom_blacklist = dlg.get_blacklist()
            self.log("Updated blacklist (will apply on next pipeline run).")

    def save_setup_settings(self, values):
        env_keys = [
            "GMAIL_CREDENTIALS_PATH",
            "GMAIL_TOKEN_PATH",
            "GEMINI_API_KEY",
            "MILLIONVERIFIER_API_KEY",
            "SENDER_NAME",
            "SENDER_COMPANY",
            "SENDER_DOMAIN",
            "SENDER_LINKEDIN",
            "SENDER_TAGLINE",
            "SENDER_ADDRESS",
            "SENDER_BACKGROUND",
            "PRODUCT_NAME",
            "PRODUCT_CATEGORY",
            "PRODUCT_DESCRIPTION",
            "PRODUCT_TARGET_ROLE",
            "PRODUCT_PAIN_POINT",
            "DEFAULT_CTA",
        ]

        env_lines = [
            "# App setup",
            "# Auto-generated by Outreach Hub.",
        ]

        for key in env_keys:
            value = str(values.get(key, "")).strip()
            env_lines.append(f"{key}={self._format_env_value(value)}")

        env_path = os.path.join(config.BASE_DIR, ".env")
        with open(env_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(env_lines) + "\n")

        # Apply values to config module immediately (no restart needed)
        _path_keys = {"GMAIL_CREDENTIALS_PATH", "GMAIL_TOKEN_PATH"}
        for key in env_keys:
            value = str(values.get(key, "")).strip()
            os.environ[key] = value
            if key in _path_keys:
                setattr(config, key, config._resolve_path(value))
            else:
                setattr(config, key, value)

        self.log(f"Saved setup to {env_path}")
        QMessageBox.information(
            self,
            "Setup Saved",
            "Settings saved and applied.",
        )

    def _format_env_value(self, value: str) -> str:
        if not value:
            return ""
        if any(ch in value for ch in [" ", "#", '"']):
            escaped = value.replace('"', '\\"')
            return f"\"{escaped}\""
        return value

    def setup_editor_tab(self):
        pass

    def load_csv_to_editor(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if not fname:
            return
        self.editor_path.setText(fname)
        try:
            df = pd.read_csv(fname)
            self.editor_table.setRowCount(len(df))
            self.editor_table.setColumnCount(len(df.columns))
            self.editor_table.setHorizontalHeaderLabels(list(df.columns))
            for i, row in df.iterrows():
                for j, value in enumerate(row):
                    self.editor_table.setItem(i, j, QTableWidgetItem(str(value) if pd.notna(value) else ""))
            self.editor_status.setText(f"Loaded: {os.path.basename(fname)}")
            self.log(f"Loaded editor file: {fname}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load CSV: {e}")

    def save_csv_from_editor(self):
        path = self.editor_path.text().strip()
        if not path:
            QMessageBox.warning(self, "No Path", "Please load a CSV first.")
            return
        try:
            rows = self.editor_table.rowCount()
            cols = self.editor_table.columnCount()
            headers = []
            for c in range(cols):
                item = self.editor_table.horizontalHeaderItem(c)
                headers.append(item.text() if item else f"col_{c}")
            data = []
            for r in range(rows):
                row_data = {}
                for c in range(cols):
                    item = self.editor_table.item(r, c)
                    row_data[headers[c]] = item.text() if item else ""
                data.append(row_data)
            pd.DataFrame(data).to_csv(path, index=False)
            self.editor_status.setText(f"Saved: {os.path.basename(path)}")
            self.log(f"Saved edited CSV to: {path}")
            QMessageBox.information(self, "Saved", "File saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save CSV: {e}")

    def _editor_table_to_dataframe(self) -> pd.DataFrame:
        rows = self.editor_table.rowCount()
        cols = self.editor_table.columnCount()
        headers = []

        for c in range(cols):
            item = self.editor_table.horizontalHeaderItem(c)
            headers.append(item.text() if item else f"col_{c}")

        data = []
        for r in range(rows):
            row_data = {}
            for c in range(cols):
                item = self.editor_table.item(r, c)
                row_data[headers[c]] = item.text().strip() if item and item.text() else ""
            data.append(row_data)

        return pd.DataFrame(data, columns=headers)

    def import_editor_csv_to_db(self):
        if self.editor_table.columnCount() == 0:
            QMessageBox.warning(self, "No Data", "Please load a CSV first.")
            return

        df = self._editor_table_to_dataframe()
        if df.empty:
            QMessageBox.warning(self, "No Data", "There are no rows to import.")
            return

        dialog = CsvImportDialog(list(df.columns), parent=self)
        if not dialog.exec():
            return

        config_data = dialog.get_config()
        mapping = config_data["mapping"]
        source_name = config_data["source"]

        imported = 0
        duplicates = 0
        skipped = 0

        db.init()

        for _, row in df.iterrows():
            company_column = mapping.get("company", "")
            company = str(row.get(company_column, "")).strip() if company_column else ""
            if not company:
                skipped += 1
                continue

            payload = {
                "company": company,
                "source": source_name,
            }

            for field, column_name in mapping.items():
                if field == "company" or not column_name:
                    continue
                value = row.get(column_name, "")
                if pd.isna(value):
                    continue
                if field == "score":
                    try:
                        payload[field] = int(float(str(value).strip()))
                    except ValueError:
                        continue
                else:
                    text = str(value).strip()
                    if text:
                        payload[field] = text

            _, is_new = db.insert_lead(payload)
            if is_new:
                imported += 1
            else:
                duplicates += 1

        self.editor_status.setText(f"Imported {imported} new leads")
        self.log(
            f"CSV import done. New: {imported}, Duplicates: {duplicates}, Skipped: {skipped}, Source: {source_name}"
        )
        QMessageBox.information(
            self,
            "Import Complete",
            (
                f"Imported {imported} new leads.\n"
                f"Skipped {duplicates} duplicates and {skipped} empty rows."
            ),
        )

    def add_editor_row(self):
        row = self.editor_table.rowCount()
        self.editor_table.insertRow(row)

    def del_editor_row(self):
        row = self.editor_table.currentRow()
        if row >= 0:
            self.editor_table.removeRow(row)

    def load_targets(self):
        try:
            db.init()
            today = datetime.now().strftime("%Y-%m-%d")
            targets = db.get_daily_targets(today)
            if not targets:
                self.targets_table.setRowCount(1)
                self.targets_table.setColumnCount(1)
                self.targets_table.setHorizontalHeaderLabels(["Status"])
                self.targets_table.setItem(0, 0, QTableWidgetItem("No daily targets in DB. Run the pipeline first."))
                return

            df = pd.DataFrame(targets)
            self.targets_table.setRowCount(len(df))
            self.targets_table.setColumnCount(len(df.columns))
            self.targets_table.setHorizontalHeaderLabels(list(df.columns))

            for i, row in df.iterrows():
                for j, value in enumerate(row):
                    item = QTableWidgetItem(str(value) if pd.notna(value) else "")
                    self.targets_table.setItem(i, j, item)

            # Color coding logic
            email_col = -1
            status_col = -1

            for c in range(self.targets_table.columnCount()):
                header = self.targets_table.horizontalHeaderItem(c).text().lower()
                if header == "email":
                    email_col = c
                elif header == "status":
                    status_col = c

            for i in range(self.targets_table.rowCount()):
                # Check Email
                if email_col >= 0:
                    email_item = self.targets_table.item(i, email_col)
                    if email_item:
                        email_txt = email_item.text().strip()
                        if email_txt and email_txt.lower() != "nan":
                            # Use QBrush/QColor for valid email
                            for c in range(self.targets_table.columnCount()):
                                item = self.targets_table.item(i, c)
                                if item:
                                    item.setBackground(QColor("#e8f5e9")) # Light Green

                # Check Status (override if Sent)
                if status_col >= 0:
                    status_item = self.targets_table.item(i, status_col)
                    if status_item:
                        status_txt = status_item.text().lower()
                        if status_txt == "sent":
                            for c in range(self.targets_table.columnCount()):
                                item = self.targets_table.item(i, c)
                                if item:
                                    item.setBackground(QColor("#e0e0e0")) # Gray

            self.targets_table.resizeColumnsToContents()
            self.log(f"Loaded {len(df)} targets from SQLite daily_targets.")
        except Exception as e:
            self.log(f"Error loading targets: {e}")

    def load_history(self):
        db.init()

        try:
            df = followup_manager.ensure_history_schema()
            if df.empty:
                self.history_table.setRowCount(0)
                self.history_stats_label.setText("No history yet.")
                return
            df["_original_idx"] = df.index

            filter_value = self.history_filter.currentText().lower()
            if filter_value == "sent":
                df = df[df["status"] == "sent"]
            elif filter_value == "skipped":
                df = df[df["status"] == "skipped"]
            elif filter_value == "follow-up sent":
                df = df[df["status"] == "followup_sent"]
            elif filter_value == "replied":
                df = df[df["status"] == "replied"]

            full_df = followup_manager.ensure_history_schema()
            sent_count = len(full_df[full_df["status"] == "sent"]) if "status" in full_df.columns else len(full_df)
            skip_count = len(full_df[full_df["status"] == "skipped"]) if "status" in full_df.columns else 0
            followup_count = len(full_df[full_df["status"] == "followup_sent"]) if "status" in full_df.columns else 0
            replied_count = len(full_df[full_df["status"] == "replied"]) if "status" in full_df.columns else 0
            self.history_stats_label.setText(
                f"Total: {len(full_df)} | Sent: {sent_count} | Skipped: {skip_count} | Follow-up: {followup_count} | Replied: {replied_count}"
            )

            display_cols = [c for c in df.columns if c != "_original_idx"]
            self.history_table.setRowCount(len(df))
            self.history_table.setColumnCount(len(display_cols))
            self.history_table.setHorizontalHeaderLabels(display_cols)

            self._history_original_indices = df["_original_idx"].tolist()
            self._history_lead_ids = df["lead_id"].tolist() if "lead_id" in df.columns else []

            for i, (_, row) in enumerate(df.iterrows()):
                for j, col in enumerate(display_cols):
                    value = row[col]
                    item = QTableWidgetItem(str(value) if pd.notna(value) else "")
                    self.history_table.setItem(i, j, item)
            self.history_table.resizeColumnsToContents()
        except Exception as e:
            self.log(f"Error loading history: {e}")

    def mark_selected_sent(self):
        selected_rows = set(item.row() for item in self.targets_table.selectedItems())
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select at least one row.")
            return
        self._mark_rows_as_sent(list(selected_rows))

    def mark_all_sent(self):
        row_count = self.targets_table.rowCount()
        if row_count == 0:
            return

        reply = QMessageBox.question(self, "Confirm", f"Mark all {row_count} targets as sent?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._mark_rows_as_sent(list(range(row_count)))

    def _mark_rows_as_sent(self, rows):
        import mark_sent

        mark_sent.ensure_dirs()
        records = []
        now = datetime.now()

        header_map = {}
        for col in range(self.targets_table.columnCount()):
            header = self.targets_table.horizontalHeaderItem(col)
            if header:
                header_map[header.text().strip().lower()] = col

        company_col = header_map.get("company", header_map.get("name", 0))
        email_col = header_map.get("email")
        lead_id_col = header_map.get("id")

        for row in rows:
            item = self.targets_table.item(row, company_col)
            if not item:
                continue

            company = item.text()
            email = ""
            lead_id = None

            if email_col is not None:
                email_item = self.targets_table.item(row, email_col)
                email = email_item.text().strip() if email_item else ""
            if lead_id_col is not None:
                lead_id_item = self.targets_table.item(row, lead_id_col)
                if lead_id_item and lead_id_item.text().isdigit():
                    lead_id = int(lead_id_item.text())

            records.append({
                "lead_id": lead_id,
                "company": company,
                "company_norm": mark_sent.normalize_company(company),
                "source": "today_targets",
                "status": "sent",
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "note": "via UI",
                "email": email,
                "followup_count": 0,
                "last_sent_date": now.strftime("%Y-%m-%d"),
                "replied": False,
            })

        if records:
            mark_sent.save_to_history(records)
            self.log(f"Marked {len(records)} companies as sent.")
            self.load_history()
            QMessageBox.information(self, "Done", f"Marked {len(records)} companies as sent.\nThey will be excluded from future processing.")

    def mark_as_unsent(self):
        selected_rows = sorted(set(item.row() for item in self.history_table.selectedItems()))
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select at least one row.")
            return

        if not hasattr(self, "_history_lead_ids"):
            QMessageBox.warning(self, "Error", "Please refresh history first.")
            return

        try:
            changed = 0
            for row in selected_rows:
                lead_id = int(self._history_lead_ids[row])
                db.record_outreach(lead_id, status="skipped", followup_number=0, note="mark_unsent")
                changed += 1

            self.log(f"Marked {len(selected_rows)} entries as unsent (skipped).")
            self.load_history()
            QMessageBox.information(self, "Done", f"Marked {changed} entries as unsent.\nThey will appear in future pipeline runs.")
        except Exception as e:
            self.log(f"Error updating history: {e}")

    def remove_from_history(self):
        selected_rows = sorted(set(item.row() for item in self.history_table.selectedItems()))
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select at least one row.")
            return

        if not hasattr(self, "_history_lead_ids"):
            QMessageBox.warning(self, "Error", "Please refresh history first.")
            return

        reply = QMessageBox.question(self, "Confirm", f"Remove {len(selected_rows)} entries from history?", QMessageBox.Yes | QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        try:
            removed = 0
            for row in selected_rows:
                lead_id = int(self._history_lead_ids[row])
                if db.clear_outreach_for_lead(lead_id):
                    removed += 1
            self.log(f"Removed {removed} lead histories.")
            self.load_history()
        except Exception as e:
            self.log(f"Error removing from history: {e}")

    def mark_as_replied(self):
        selected_rows = sorted(set(item.row() for item in self.history_table.selectedItems()))
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select at least one row.")
            return

        if not hasattr(self, "_history_lead_ids"):
            QMessageBox.warning(self, "Error", "Please refresh history first.")
            return

        try:
            changed = 0
            for row in selected_rows:
                lead_id = int(self._history_lead_ids[row])
                if db.mark_replied(lead_id):
                    changed += 1
            self.log(f"Marked {changed} entries as replied.")
            self.load_history()
            QMessageBox.information(self, "Done", f"Marked {changed} entries as replied.")
        except Exception as e:
            self.log(f"Error updating reply status: {e}")

    def run_email_verification(self):
        if self.pipeline_worker and self.pipeline_worker.isRunning():
            QMessageBox.warning(self, "Busy", "Pipeline is already running.")
            return

        if not config.MILLIONVERIFIER_API_KEY:
            QMessageBox.critical(
                self, "API Key Missing",
                "MillionVerifier API key not found.\n"
                "Add it in the Setup tab or save it in .env."
            )
            return

        # Count how many emails need verification
        db.init()
        leads = db.search_leads(limit=100000, offset=0)
        to_verify = [
            l for l in leads
            if l.get("email") and "@" in str(l.get("email", ""))
            and int(l.get("email_valid", -1)) in (-1, 1)
        ]

        if not to_verify:
            QMessageBox.information(self, "Nothing to Verify", "All emails have already been verified.")
            return

        reply = QMessageBox.question(
            self, "Verify Emails",
            f"Found {len(to_verify)} emails to verify via MillionVerifier.\n"
            f"This will use {len(to_verify)} API credits.\n\nProceed?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.log_area.clear()
        self.status_label.setText("Verifying emails via MillionVerifier...")

        from .workers import EmailVerificationThread
        self.pipeline_worker = EmailVerificationThread()
        self.pipeline_worker.log_signal.connect(self.log)
        self.pipeline_worker.finished_signal.connect(self.verification_finished)
        self.pipeline_worker.start()

    def verification_finished(self, msg):
        self.log(f"\n--- {msg} ---")
        self.status_label.setText("Ready")
        self.load_targets()
        QMessageBox.information(self, "Verification Complete", msg)

    def run_pipeline(self):
        if self.pipeline_worker and self.pipeline_worker.isRunning():
            QMessageBox.warning(self, "Busy", "Pipeline is already running.")
            return

        self.log_area.clear()
        self.status_label.setText("Running pipeline...")

        settings = {"daily_target_count": self.daily_target_spin.value()}
        if self.custom_blacklist:
            settings["blacklist"] = self.custom_blacklist
        if self.custom_score_keywords:
            settings["score_keywords"] = self.custom_score_keywords

        self.pipeline_worker = PipelineThread(settings)
        self.pipeline_worker.log_signal.connect(self.log)
        self.pipeline_worker.finished_signal.connect(self.pipeline_finished)
        self.pipeline_worker.start()

    def pipeline_finished(self, msg):
        self.log(f"\n--- {msg} ---")
        self.status_label.setText("Ready")
        self.load_targets()
        QMessageBox.information(self, "Pipeline Complete", msg)

    def reset_today_targets(self):
        today = datetime.now().strftime("%Y-%m-%d")
        reply = QMessageBox.question(
            self,
            "Reset Targets",
            f"Delete all daily targets for {today}?\n"
            "Next pipeline run will re-select with current priority rules.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        removed = db.clear_daily_targets(today)
        self.log(f"Cleared {removed} daily targets for {today}.")
        self.load_targets()

    def toggle_location_input(self, checked):
        self.maps_location.setEnabled(not checked)
        if checked:
            self.maps_location.setText("Looping Top 50 Cities...")
        else:
            self.maps_location.setText("New York, USA")

    def log(self, message):
        if not hasattr(self, "log_area") or self.log_area is None:
            return
        self.log_area.append(message)
        sb = self.log_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def run_maps(self):
        try:
            import playwright  # noqa: F401
        except ImportError:
            QMessageBox.warning(
                self,
                "Playwright Not Installed",
                "Google Maps scraping requires Playwright.\n\n"
                "To install, open a terminal and run:\n"
                "  pip install playwright\n"
                "  playwright install chromium\n\n"
                "This is optional. You can still import leads via CSV.",
            )
            return

        text = self.maps_input.toPlainText().strip()
        location = self.maps_location.text().strip()
        use_city_loop = self.chk_city_loop.isChecked()

        if not text:
            QMessageBox.warning(self, "Input Error", "Please enter at least one keyword.")
            return

        keywords = [line.strip() for line in text.split("\n") if line.strip()]
        headless = self.maps_headless.isChecked()
        max_results = self.maps_max_results.value()

        self.start_worker("GOOGLE_MAPS", {
            "keywords": keywords,
            "location": location,
            "use_city_loop": use_city_loop,
            "headless": headless,
            "max_results": max_results,
        })

    def start_worker(self, mode, params):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Busy", "A scraping task is already running.")
            return

        self.log_area.clear()
        self.log(f"Starting {mode}...")
        self.status_label.setText(f"Running {mode}...")
        self.toggle_buttons(False)

        self.scraper_state.reset()
        self.worker = ScraperThread(mode, params, self.scraper_state)
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.task_finished)
        self.worker.start()

    def pause_scraper(self):
        self.scraper_state.pause()
        self.log(">>> PAUSE requested...")
        self.status_label.setText("Paused")
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(True)

    def resume_scraper(self):
        self.scraper_state.resume()
        self.log(">>> RESUME requested...")
        self.status_label.setText("Running...")
        self.btn_pause.setEnabled(True)
        self.btn_resume.setEnabled(False)

    def run_email_crawler(self):
        db.init()
        today = datetime.now().strftime("%Y-%m-%d")
        if not db.get_daily_targets(today):
            QMessageBox.warning(self, "No Targets", "Please run the pipeline first to generate daily targets.")
            return

        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Busy", "A task is already running.")
            return

        reply = QMessageBox.question(
            self,
            "Start Email Crawling?",
            "This will visit each website in today's SQLite targets to find email addresses.\n\n"
            "Safety: 'Safe Mode' enabled (Slow speed, public info only).\n"
            "Estimated time: ~10 seconds per company.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.log_area.clear()
        self.status_label.setText("Crawling Emails (Safe Mode)...")
        self.log("Starting Safe Email Crawler...")

        from .workers import EmailCrawlerThread

        self.worker = EmailCrawlerThread("")
        self.worker.log_signal.connect(self.log)
        self.worker.finished_signal.connect(self.crawler_finished)
        self.worker.start()

        self.btn_stop.setEnabled(True)
        self.scraper_state.reset()

    def crawler_finished(self, msg):
        self.log(f"\n--- {msg} ---")
        self.status_label.setText("Ready")
        self.btn_stop.setEnabled(False)
        self.load_targets()
        QMessageBox.information(self, "Crawling Complete", msg)

    def stop_scraper(self):
        self.scraper_state.stop()
        if hasattr(self.worker, "stop"):
            self.worker.stop()
        self.log(">>> STOP requested... finishing current operation...")
        self.status_label.setText("Stopping...")

    def task_finished(self, msg):
        self.log(f"\n--- {msg} ---")
        self.status_label.setText("Ready")
        self.toggle_buttons(True)
        self.load_targets()
        QMessageBox.information(self, "Completed", msg)

    def toggle_buttons(self, idle):
        self.btn_maps_run.setEnabled(idle)

        self.btn_pause.setEnabled(not idle)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(not idle)

    def targets_table_clicked(self, row, col):
        from PySide6.QtWidgets import QApplication
        import webbrowser
        import urllib.parse

        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            url_columns = ["Website", "website"]
            for url_col_name in url_columns:
                for c in range(self.targets_table.columnCount()):
                    header = self.targets_table.horizontalHeaderItem(c)
                    if header and header.text() == url_col_name:
                        item = self.targets_table.item(row, c)
                        if item:
                            url = item.text()
                            if url and url.startswith("/url?q="):
                                try:
                                    parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                                    if "q" in parsed:
                                        url = parsed["q"][0]
                                except Exception:
                                    pass
                            if url and (url.startswith("http") or url.startswith("www")):
                                if url.startswith("www"):
                                    url = "https://" + url
                                webbrowser.open(url)
                                self.log(f"Opened: {url}")
                                return

    def targets_table_hover(self, row, col):
        header = self.targets_table.horizontalHeaderItem(col)
        if header and header.text() in ["Website", "website"]:
            self.targets_table.setCursor(Qt.PointingHandCursor)
        else:
            self.targets_table.setCursor(Qt.ArrowCursor)

    def run_smart_hunt(self):
        selected_rows = self.targets_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a row to hunt for email.")
            return

        idx = selected_rows[0].row()
        cols = {}
        for c in range(self.targets_table.columnCount()):
            header_item = self.targets_table.horizontalHeaderItem(c)
            if header_item:
                cols[header_item.text().lower()] = c

        website_col = cols.get("website", 0)
        company_col = cols.get("company", cols.get("name", 0))

        website_item = self.targets_table.item(idx, website_col)
        company_item = self.targets_table.item(idx, company_col)
        website = website_item.text() if website_item else ""
        company = company_item.text() if company_item else ""

        if not website or website.lower() == "nan":
            QMessageBox.warning(self, "No Website", "Selected row has no website URL.")
            return

        self.log(f"Starting Smart Hunt for {company}...")

        gemini = self.tab_mailing.gemini
        if not gemini or not gemini.model:
            QMessageBox.critical(self, "AI Error", "Gemini AI is not initialized. Check API Key.")
            return

        worker = SmartHuntWorker(idx, website, company, gemini)
        worker.log_signal.connect(self.log)
        worker.finished_signal.connect(self.smart_hunt_finished)
        worker.start()

        if not hasattr(self, "active_workers"):
            self.active_workers = []
        self.active_workers.append(worker)

    def smart_hunt_finished(self, result):
        idx = result["index"]
        email = result["email"]

        if email:
            found_col = -1
            for c in range(self.targets_table.columnCount()):
                header = self.targets_table.horizontalHeaderItem(c).text()
                if header in ["Email", "email"]:
                    found_col = c
                    break

            if found_col == -1:
                found_col = self.targets_table.columnCount()
                self.targets_table.insertColumn(found_col)
                self.targets_table.setHorizontalHeaderItem(found_col, QTableWidgetItem("email"))

            self.targets_table.setItem(idx, found_col, QTableWidgetItem(email))

            try:
                lead_id_col = -1
                company_col = -1
                for c in range(self.targets_table.columnCount()):
                    header = self.targets_table.horizontalHeaderItem(c).text().lower()
                    if header == "id":
                        lead_id_col = c
                    elif header == "company":
                        company_col = c

                lead_id = None
                if lead_id_col >= 0:
                    lead_item = self.targets_table.item(idx, lead_id_col)
                    if lead_item and lead_item.text().isdigit():
                        lead_id = int(lead_item.text())

                if lead_id:
                    db.update_lead(lead_id, {"email": email, "email_valid": 1})
                    company = self.targets_table.item(idx, company_col).text() if company_col >= 0 else "Unknown"
                    self.log(f"SAVED: Email for {company} updated in SQLite.")
                QMessageBox.information(self, "Found!", f"Successfully found email: {email}")
            except Exception as e:
                self.log(f"Error saving to SQLite: {e}")
        else:
            QMessageBox.information(self, "Not Found", "Could not find an email.")

    def create_drafts_for_selected(self):
        selected_rows = self.targets_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select at least one row in the table.")
            return

        col_count = self.targets_table.columnCount()
        headers = [self.targets_table.horizontalHeaderItem(c).text() for c in range(col_count)]

        data = []
        for row_model_index in selected_rows:
            row_idx = row_model_index.row()
            row_data = {}
            for c in range(col_count):
                item = self.targets_table.item(row_idx, c)
                row_data[headers[c]] = item.text() if item else ""
            data.append(row_data)

        selected_df = pd.DataFrame(data)

        # 1. Open Dialog for Settings/Preview
        dlg = EmailCampaignDialog(
            parent=self,
            targets_df=selected_df,
            gemini_client=self.tab_mailing.gemini,
            template_subject=self.tab_mailing.txt_subject.text(),
            template_body=self.tab_mailing.txt_body.toPlainText()
        )

        if dlg.exec():
            # 2. If accepted, run draft creation
            # We urge MailingTab to do the work, so we don't duplicate worker logic
            self.tab_mailing.active_targets_df = selected_df
            self.tab_mailing.create_bulk_drafts(enhanced_params=dlg.get_config())

            # Optional: Switch tab to show progress?
            # User requested NOT to switch tab.
            # But the progress bar is in MailingTab.
            # We can just inform user:
            self.log("Started creating drafts in background... Check Mailing tab for progress if needed.")
