from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTableWidget,
                             QHeaderView, QTableWidgetItem, QSpinBox, QHBoxLayout,
                             QPushButton, QDialogButtonBox, QListWidget,
                             QAbstractItemView, QLineEdit, QMessageBox, QTextEdit,
                             QCheckBox, QFormLayout, QComboBox)
from PySide6.QtCore import Qt
import process_leads
from crawl_emails import _verify_web_context

class ScoringDialog(QDialog):
    """Dialog for editing scoring keywords."""
    def __init__(self, parent=None, score_keywords=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Scoring Keywords")
        self.resize(450, 450)
        self.score_keywords = score_keywords or dict(process_leads.SCORE_KEYWORDS)

        layout = QVBoxLayout(self)

        info = QLabel("Higher scores = higher priority (1-10).\nPartial match works (e.g., 'sustainab' matches 'sustainability').\nDouble-click cells to edit.")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Table for keywords
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Keyword", "Score (1-10)"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 100)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.table)

        self.load_keywords()

        # Add/Remove buttons
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Add Keyword")
        btn_add.setProperty("class", "success")
        btn_add.clicked.connect(self.add_keyword)
        btn_layout.addWidget(btn_add)

        btn_remove = QPushButton("Remove Selected")
        btn_remove.setProperty("class", "danger")
        btn_remove.clicked.connect(self.remove_keyword)
        btn_layout.addWidget(btn_remove)
        layout.addLayout(btn_layout)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_keywords(self):
        self.table.setRowCount(len(self.score_keywords))
        for i, (keyword, score) in enumerate(self.score_keywords.items()):
            keyword_item = QTableWidgetItem(keyword)
            score_item = QTableWidgetItem(str(score))
            score_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, keyword_item)
            self.table.setItem(i, 1, score_item)

    def add_keyword(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        keyword_item = QTableWidgetItem("new_keyword")
        score_item = QTableWidgetItem("1")
        score_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 0, keyword_item)
        self.table.setItem(row, 1, score_item)
        self.table.editItem(keyword_item)  # Start editing the keyword

    def remove_keyword(self):
        rows = sorted(set(item.row() for item in self.table.selectedItems()), reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def validate_and_accept(self):
        """Validate scores before accepting."""
        for i in range(self.table.rowCount()):
            score_item = self.table.item(i, 1)
            if score_item:
                try:
                    score = int(score_item.text())
                    if score < 1 or score > 10:
                        raise ValueError
                except ValueError:
                    keyword_item = self.table.item(i, 0)
                    keyword = keyword_item.text() if keyword_item else f"Row {i+1}"
                    QMessageBox.warning(self, "Invalid Score",
                        f"Score for '{keyword}' must be a number between 1 and 10.")
                    return
        self.accept()

    def get_keywords(self):
        result = {}
        for i in range(self.table.rowCount()):
            keyword_item = self.table.item(i, 0)
            score_item = self.table.item(i, 1)
            if keyword_item and score_item:
                keyword = keyword_item.text().strip()
                try:
                    score = int(score_item.text())
                    score = max(1, min(10, score))  # Clamp to 1-10
                except ValueError:
                    score = 1
                if keyword:
                    result[keyword] = score
        return result


class BlacklistDialog(QDialog):
    """Dialog for editing blacklist."""
    def __init__(self, parent=None, blacklist=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Blacklist")
        self.resize(400, 400)
        self.blacklist = list(blacklist) if blacklist else list(process_leads.BLACKLIST)

        layout = QVBoxLayout(self)

        info = QLabel("Companies/URLs containing these terms will be filtered out.")
        info.setWordWrap(True)
        layout.addWidget(info)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        for item in self.blacklist:
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        # Add/Remove
        btn_layout = QHBoxLayout()
        self.add_input = QLineEdit()
        self.add_input.setPlaceholderText("Add new term...")
        btn_layout.addWidget(self.add_input)

        btn_add = QPushButton("Add")
        btn_add.clicked.connect(self.add_item)
        btn_layout.addWidget(btn_add)

        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self.remove_item)
        btn_layout.addWidget(btn_remove)
        layout.addLayout(btn_layout)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_item(self):
        text = self.add_input.text().strip()
        if text:
            self.list_widget.addItem(text)
            self.add_input.clear()

    def remove_item(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def get_blacklist(self):
        result = []
        for i in range(self.list_widget.count()):
            result.append(self.list_widget.item(i).text())
        return result


class EmailCampaignDialog(QDialog):
    """Dialog for configuring email campaign settings and previewing AI content."""
    def __init__(self, parent=None, targets_df=None, gemini_client=None,
                 template_subject="", template_body=""):
        super().__init__(parent)
        self.targets_df = targets_df
        self.gemini = gemini_client
        self.template_subject = template_subject
        self.template_body = template_body

        self.tokenizer_mode = False # Reserved
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Personalize Email Campaign with Gemini")
        self.setMinimumWidth(500)
        vbox = QVBoxLayout(self)

        form = QFormLayout()

        self.combo_tone = QComboBox()
        self.combo_tone.addItems(["Professional", "Casual & Friendly", "Direct & Bold", "Curiosity Based"])
        form.addRow("Tone of Voice:", self.combo_tone)

        self.edit_custom_goal = QLineEdit()
        self.edit_custom_goal.setPlaceholderText("e.g., Reply if this is relevant and I can share examples.")
        form.addRow("Call to Action (CTA):", self.edit_custom_goal)

        self.chk_use_website_context = QCheckBox("Crawl website for better personalization")
        self.chk_use_website_context.setChecked(True)
        form.addRow(self.chk_use_website_context)

        vbox.addLayout(form)

        info_label = QLabel(f"Selected {len(self.targets_df)} targets for draft creation.")
        info_label.setStyleSheet("color: #888; font-style: italic;")
        vbox.addWidget(info_label)

        btn_box = QHBoxLayout()
        btn_generate = QPushButton("Generate Preview First")
        btn_generate.clicked.connect(self.preview_personalized)

        btn_apply = QPushButton("Apply & Create Drafts")
        btn_apply.setProperty("class", "success")
        btn_apply.clicked.connect(self.accept) # Accept dialog to proceed

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        btn_box.addWidget(btn_generate)
        btn_box.addWidget(btn_apply)
        btn_box.addWidget(btn_cancel)
        vbox.addLayout(btn_box)

    def preview_personalized(self):
        try:
            if self.targets_df is None or self.targets_df.empty:
                QMessageBox.warning(self, "No Data", "No targets to preview.")
                return

            row = self.targets_df.iloc[0]

            raw_preview_company = str(row.get("Company", row.get("company", "")))
            if " @ " in raw_preview_company:
                preview_company = raw_preview_company.split(" @ ", 1)[1]
            else:
                preview_company = raw_preview_company

            # Simple loading indicator (blocking)
            self.setCursor(Qt.WaitCursor)

            web_context = ""
            org_foundation = str(row.get("org_foundation", "")).strip()
            if org_foundation and org_foundation.lower() not in ("nan", "none", ""):
                web_context = f"Company mission/about: {org_foundation}"

            if self.chk_use_website_context.isChecked() and not web_context:
                import requests
                from bs4 import BeautifulSoup
                try:
                    website = str(row.get("Website", row.get("website", "")))
                    if website and website.lower() != "nan":
                        if not website.startswith("http"):
                            website = "https://" + website
                        resp = requests.get(website, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
                        soup = BeautifulSoup(resp.text, "html.parser")
                        raw_text = soup.get_text()[:4000]
                        web_context = _verify_web_context(preview_company, raw_text)
                except Exception:
                    pass

            tone = self.combo_tone.currentText()
            cta = self.edit_custom_goal.text()

            preview_title = str(row.get("Title", row.get("title", "")))
            if (not preview_title or preview_title.lower() in ("", "nan")) and row.get("leed_credential"):
                preview_title = str(row.get("leed_credential"))

            preview_name = str(row.get("Name", row.get("contact_person", "")) or "").strip()
            preview_location = row.get("Location", row.get("state"))

            self.setCursor(Qt.ArrowCursor)

            if not self.gemini or not self.gemini.model:
                QMessageBox.warning(self, "AI Error", "Gemini is not initialized.")
                return

            full_email = self.gemini.generate_full_email(
                preview_company,
                name=preview_name,
                title=preview_title,
                location=preview_location,
                web_context=web_context,
                tone=tone,
                cta=cta,
            )

            preview_dlg = QDialog(self)
            preview_dlg.setWindowTitle(f"Preview: {preview_company}")
            preview_dlg.resize(600, 400)
            pvbox = QVBoxLayout(preview_dlg)

            edit = QTextEdit()
            edit.setPlainText(full_email)
            pvbox.addWidget(edit)

            btn_close = QPushButton("Close Preview")
            btn_close.clicked.connect(preview_dlg.accept)
            pvbox.addWidget(btn_close)
            preview_dlg.exec()

        except Exception as e:
            self.setCursor(Qt.ArrowCursor)
            QMessageBox.warning(self, "Preview Error", str(e))

    def get_config(self):
        return {
            "tone": self.combo_tone.currentText(),
            "cta": self.edit_custom_goal.text(),
            "use_web": self.chk_use_website_context.isChecked()
        }


class CsvImportDialog(QDialog):
    FIELD_LABELS = {
        "company": "Company (required)",
        "email": "Email",
        "phone": "Phone",
        "website": "Website",
        "contact_person": "Contact Person",
        "title": "Job Title",
        "address": "Address",
        "city": "City",
        "state": "State/Province",
        "country": "Country",
        "keyword": "Keyword/Tag",
        "score": "Score",
    }

    FIELD_ALIASES = {
        "company": ["company", "organization", "business", "account", "firm", "name"],
        "email": ["email", "email address", "e-mail"],
        "phone": ["phone", "telephone", "mobile"],
        "website": ["website", "site", "url", "domain"],
        "contact_person": ["contact", "contact person", "person", "owner", "decision maker"],
        "title": ["title", "job title", "role", "position"],
        "address": ["address", "street"],
        "city": ["city", "town"],
        "state": ["state", "province", "region"],
        "country": ["country", "nation"],
        "keyword": ["keyword", "tag", "segment", "industry", "category"],
        "score": ["score", "priority", "rank"],
    }

    def __init__(self, headers, parent=None):
        super().__init__(parent)
        self.headers = [str(header) for header in headers]
        self.field_combos = {}
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("Import CSV to Leads Database")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        help_text = QLabel(
            "Check the column mapping below. Company is required, everything else is optional."
        )
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        form = QFormLayout()

        self.edit_source = QLineEdit("csv_import")
        self.edit_source.setPlaceholderText("Source label saved in the database")
        form.addRow("Source Name:", self.edit_source)

        options = ["(Not used)"] + self.headers
        for field, label in self.FIELD_LABELS.items():
            combo = QComboBox()
            combo.addItems(options)
            guess = self._guess_header(field)
            if guess:
                combo.setCurrentText(guess)
            self.field_combos[field] = combo
            form.addRow(label + ":", combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _guess_header(self, field: str) -> str:
        aliases = self.FIELD_ALIASES.get(field, [])
        for header in self.headers:
            normalized = header.strip().lower()
            if normalized in aliases:
                return header
        for header in self.headers:
            normalized = header.strip().lower()
            if any(alias in normalized for alias in aliases):
                return header
        return ""

    def _validate(self):
        if self.field_combos["company"].currentIndex() == 0:
            QMessageBox.warning(self, "Company Required", "Please map a company column before importing.")
            return
        if not self.edit_source.text().strip():
            QMessageBox.warning(self, "Source Required", "Please enter a source name.")
            return
        self.accept()

    def get_config(self):
        mapping = {}
        for field, combo in self.field_combos.items():
            value = combo.currentText()
            mapping[field] = "" if value == "(Not used)" else value
        return {
            "source": self.edit_source.text().strip(),
            "mapping": mapping,
        }
