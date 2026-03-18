from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QGroupBox, QMessageBox, QProgressBar, QCheckBox,
    QDialog, QComboBox, QFormLayout
)
from PySide6.QtCore import QThread, Signal
import pandas as pd
import os
from datetime import datetime

from gmail_sender import GmailSender
from gemini_helper import GeminiHelper
from outreach_scheduler import now_est, is_optimal_send_time, next_optimal_send_time
from tracking import new_tracking_id, wrap_links_for_tracking, to_simple_html_email
import followup_manager
import config
import db

import time


from .workers import DraftWorker
from .dialogs import EmailCampaignDialog




class MailingTab(QWidget):
    def __init__(self):
        super().__init__()
        self.gmail_client = GmailSender()
        self.gemini = GeminiHelper()
        self.worker = None
        self.active_targets_df = None
        self.setup_ui()

        if os.path.exists(config.GMAIL_TOKEN_PATH):
            self.authenticate_gmail(silent=True)

    def setup_ui(self):
        layout = QVBoxLayout(self)

        status_box = QGroupBox("Gmail Connection")
        status_layout = QHBoxLayout()
        self.lbl_status = QLabel("Status: Not Connected")
        self.btn_login = QPushButton("Connect Gmail")
        self.btn_login.setProperty("class", "primary")
        self.btn_login.clicked.connect(self.authenticate_gmail)
        status_layout.addWidget(self.lbl_status)
        status_layout.addWidget(self.btn_login)
        status_box.setLayout(status_layout)
        layout.addWidget(status_box)

        template_box = QGroupBox("Email Template")
        tmpl_layout = QVBoxLayout()

        tmpl_layout.addWidget(QLabel("Subject:"))
        self.txt_subject = QLineEdit()
        self.txt_subject.setPlaceholderText(config.DEFAULT_EMAIL_SUBJECT_TEMPLATE)
        self.txt_subject.setText(config.DEFAULT_EMAIL_SUBJECT_TEMPLATE)
        tmpl_layout.addWidget(self.txt_subject)

        tmpl_layout.addWidget(QLabel("Body (Variables: {Company}, {Name}, {AI_Intro}):"))
        self.txt_body = QTextEdit()
        default_body = config.DEFAULT_EMAIL_BODY_TEMPLATE.format(
            sender_name=config.SENDER_NAME,
            sender_title=config.SENDER_TAGLINE,
            sender_company=config.SENDER_COMPANY,
        )
        self.txt_body.setPlaceholderText(default_body)
        self.txt_body.setPlainText(default_body)
        tmpl_layout.addWidget(self.txt_body)

        self.chk_ai = QCheckBox("Use AI Personalization (Gemini)")
        if self.gemini.model:
            self.chk_ai.setChecked(True)
            self.chk_ai.setToolTip("Gemini is ready!")
        else:
            self.chk_ai.setChecked(False)
            self.chk_ai.setEnabled(False)
            self.chk_ai.setText("Use AI Personalization (Gemini) - [Configure key in Setup]")
        tmpl_layout.addWidget(self.chk_ai)

        template_box.setLayout(tmpl_layout)
        layout.addWidget(template_box)

        outreach_box = QGroupBox("Outreach Optimization")
        outreach_layout = QFormLayout()

        self.lbl_send_window = QLabel("")
        self._refresh_send_window_label()
        btn_refresh_window = QPushButton("Refresh EST Window")
        btn_refresh_window.clicked.connect(self._refresh_send_window_label)
        row_window = QHBoxLayout()
        row_window.addWidget(self.lbl_send_window)
        row_window.addWidget(btn_refresh_window)
        outreach_layout.addRow("Send Window:", row_window)

        self.chk_tracking = QCheckBox("Enable Open/Click Tracking")
        self.chk_tracking.setChecked(True)
        outreach_layout.addRow(self.chk_tracking)

        self.edit_tracking_base_url = QLineEdit(config.TRACKING_BASE_URL)
        self.edit_tracking_base_url.setPlaceholderText("Tracking server URL (e.g., http://localhost:8787)")
        outreach_layout.addRow("Tracking Base URL:", self.edit_tracking_base_url)

        outreach_box.setLayout(outreach_layout)
        layout.addWidget(outreach_box)

        action_box = QGroupBox("Actions")
        action_layout = QHBoxLayout()

        self.btn_send_test = QPushButton("Send Test to Self")
        self.btn_send_test.setProperty("class", "warning")
        self.btn_send_test.clicked.connect(self.send_test_email)

        self.btn_preview = QPushButton("AI Personalize Settings")
        self.btn_preview.setProperty("class", "purple")
        self.btn_preview.clicked.connect(self.open_personalization_dialog)

        self.btn_create_drafts = QPushButton("Create Drafts for Today's Targets")
        self.btn_create_drafts.setProperty("class", "success")
        self.btn_create_drafts.clicked.connect(self.create_bulk_drafts)
        self.btn_create_drafts.setEnabled(False)

        self.btn_followup_drafts = QPushButton("Create Due Follow-up Drafts")
        self.btn_followup_drafts.setProperty("class", "primary")
        self.btn_followup_drafts.clicked.connect(self.create_due_followup_drafts)
        self.btn_followup_drafts.setEnabled(False)

        action_layout.addWidget(self.btn_send_test)
        action_layout.addWidget(self.btn_preview)
        action_layout.addWidget(self.btn_create_drafts)
        action_layout.addWidget(self.btn_followup_drafts)
        action_box.setLayout(action_layout)
        layout.addWidget(action_box)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setFixedHeight(120)
        layout.addWidget(self.log_area)

    def _load_today_targets_df(self) -> pd.DataFrame:
        db.init()
        today = datetime.now().strftime("%Y-%m-%d")
        rows = db.get_daily_targets(today)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def _refresh_send_window_label(self):
        current = now_est()
        if is_optimal_send_time(current):
            self.lbl_send_window.setText(f"EST now: {current.strftime('%Y-%m-%d %H:%M')} (optimal)")
        else:
            next_slot = next_optimal_send_time(current)
            self.lbl_send_window.setText(
                f"EST now: {current.strftime('%Y-%m-%d %H:%M')} | Next optimal: {next_slot.strftime('%Y-%m-%d %H:%M')}"
            )

    def _check_send_window(self):
        self._refresh_send_window_label()
        if is_optimal_send_time():
            return True

        next_slot = next_optimal_send_time()
        reply = QMessageBox.question(
            self,
            "Outside Optimal Send Window",
            "Current time is outside Tue-Thu 9:00-11:00 AM EST.\n"
            f"Next optimal slot: {next_slot.strftime('%Y-%m-%d %H:%M EST')}\n\n"
            "Create drafts anyway?",
            QMessageBox.Yes | QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def log(self, message):
        self.log_area.append(message)

    def authenticate_gmail(self, silent=False):
        if not silent:
            self.log("Starting authentication...")
        try:
            success = self.gmail_client.authenticate(silent=silent)
            if success:
                email = self.gmail_client.get_profile()
                self.lbl_status.setText(f"Connected: {email}")
                self.lbl_status.setStyleSheet("color: #00c851; font-weight: bold")
                self.btn_login.setEnabled(False)
                self.btn_create_drafts.setEnabled(True)
                self.btn_followup_drafts.setEnabled(True)
                if not silent:
                    self.log("Authentication successful!")
            else:
                if not silent:
                    self.log("Authentication failed.")
        except Exception as e:
            if not silent:
                self.log(f"Auth Error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Failed to connect: {str(e)}")

    def send_test_email(self):
        if not self.gmail_client.service:
            QMessageBox.warning(self, "Warning", "Please connect Gmail first.")
            return

        my_email = self.gmail_client.get_profile()
        if not my_email:
            return

        subject = self.txt_subject.text() or "Test Subject"
        body = self.txt_body.toPlainText() or "Test Body"

        subject = subject.replace("{Company}", "TEST COMPANY").replace("{Name}", "TEST NAME")
        body = body.replace("{Company}", "TEST COMPANY").replace("{Name}", "TEST NAME")

        tracking_id = ""
        body_html = None
        if self.chk_tracking.isChecked() and self.edit_tracking_base_url.text().strip():
            tracking_id = new_tracking_id()
            body = wrap_links_for_tracking(body, self.edit_tracking_base_url.text().strip(), tracking_id)
            body_html = to_simple_html_email(body, self.edit_tracking_base_url.text().strip(), tracking_id)

        self.gmail_client.send_email(my_email, subject, body, body_html=body_html)
        self.log(f"Test email sent to {my_email}")
        if tracking_id:
            self.log(f"Tracking ID: {tracking_id}")
        QMessageBox.information(self, "Success", f"Sent test email to {my_email}")

    def open_personalization_dialog(self):
        self.run_personalized_config_dialog()

    def run_personalized_config_dialog(self, targets_df=None):
        if targets_df is not None:
            self.active_targets_df = targets_df
        else:
            try:
                self.active_targets_df = self._load_today_targets_df()
                if self.active_targets_df.empty:
                    raise Exception("File empty")
            except Exception:
                QMessageBox.warning(self, "No Targets", "No targets found in SQLite daily_targets. Run pipeline first.")
                return

        dlg = EmailCampaignDialog(
            parent=self,
            targets_df=self.active_targets_df,
            gemini_client=self.gemini,
            template_subject=self.txt_subject.text(),
            template_body=self.txt_body.toPlainText()
        )

        if dlg.exec():
            # User accepted (Apply)
            # We can capture the settings if we want to save them or just pass them to worker
            # Currently we pass them via self.create_bulk_drafts which reads fields, but
            # create_bulk_drafts needs to know about enhanced_params.
            # I will modify create_bulk_drafts to accept params or read from dialog result if passed.
            self.create_bulk_drafts(enhanced_params=dlg.get_config())


    def _build_worker(self, df: pd.DataFrame, followup_mode: bool = False, enhanced_params=None):
        use_ai = self.chk_ai.isChecked() and not followup_mode
        worker = DraftWorker(
            self.gmail_client,
            df,
            self.txt_subject.text(),
            self.txt_body.toPlainText(),
            self.gemini,
            use_ai,
            tracking_enabled=self.chk_tracking.isChecked(),
            tracking_base_url=self.edit_tracking_base_url.text().strip(),
            followup_mode=followup_mode,
            enhanced_params=enhanced_params
        )

        worker.progress.connect(self.progress_bar.setValue)
        worker.log.connect(self.log)
        worker.finished.connect(self.on_drafts_finished)
        return worker

    def create_bulk_drafts(self, enhanced_params=None):
        if not self.gmail_client.service:
            QMessageBox.warning(self, "No Connection", "Please Connect Gmail first.")
            return

        if not self._check_send_window():
            return

        df = self.active_targets_df
        if df is None or df.empty:
            df = self._load_today_targets_df()
            if df.empty:
                QMessageBox.warning(self, "Error", "No daily targets found in SQLite.")
                return

        self.btn_create_drafts.setEnabled(False)
        self.btn_followup_drafts.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log("Starting bulk draft creation...")

        self.worker = self._build_worker(df, followup_mode=False, enhanced_params=enhanced_params)
        self.worker.start()

    def create_due_followup_drafts(self):
        if not self.gmail_client.service:
            QMessageBox.warning(self, "No Connection", "Please Connect Gmail first.")
            return

        if not self._check_send_window():
            return

        due = followup_manager.load_due_followups()
        if due.empty:
            QMessageBox.information(self, "No Follow-ups Due", "No follow-up targets are due today.")
            return

        self.btn_create_drafts.setEnabled(False)
        self.btn_followup_drafts.setEnabled(False)
        self.progress_bar.setValue(0)
        self.log(f"Starting follow-up draft creation for {len(due)} records...")

        self.worker = self._build_worker(due, followup_mode=True)
        self.worker.start()

    def on_drafts_finished(self):
        self.btn_create_drafts.setEnabled(True)
        self.btn_followup_drafts.setEnabled(True)
        self.log("Draft creation completed.")
        QMessageBox.information(self, "Done", "Draft generation is complete. Check Gmail Drafts.")
