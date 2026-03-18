from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

import config


class SetupTab(QWidget):
    def __init__(self, on_save):
        super().__init__()
        self._on_save = on_save
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root_layout.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)

        intro = QLabel(
            "Use this tab for first-time setup. Save your keys and sender profile here, then restart the app."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        files_group = QGroupBox("Keys & Files")
        files_form = QFormLayout(files_group)
        self.edit_gmail_credentials = self._path_row(config.GMAIL_CREDENTIALS_PATH, files_form)
        self.edit_gmail_token = self._path_row(config.GMAIL_TOKEN_PATH, files_form, save_file=True)

        self.edit_gemini_key = QLineEdit(config.GEMINI_API_KEY)
        self.edit_gemini_key.setPlaceholderText("Paste Gemini API key")
        files_form.addRow("Gemini API Key:", self.edit_gemini_key)

        self.edit_mv_key = QLineEdit(config.MILLIONVERIFIER_API_KEY)
        self.edit_mv_key.setPlaceholderText("Optional")
        files_form.addRow("MillionVerifier API Key:", self.edit_mv_key)
        layout.addWidget(files_group)

        sender_group = QGroupBox("Sender Profile")
        sender_form = QFormLayout(sender_group)
        self.edit_sender_name = self._line(config.SENDER_NAME, "Your name")
        sender_form.addRow("Sender Name:", self.edit_sender_name)
        self.edit_sender_company = self._line(config.SENDER_COMPANY, "Your company")
        sender_form.addRow("Sender Company:", self.edit_sender_company)
        self.edit_sender_domain = self._line(config.SENDER_DOMAIN, "example.com")
        sender_form.addRow("Sender Domain:", self.edit_sender_domain)
        self.edit_sender_linkedin = self._line(config.SENDER_LINKEDIN, "https://www.linkedin.com/in/...")
        sender_form.addRow("LinkedIn URL:", self.edit_sender_linkedin)
        self.edit_sender_tagline = self._line(config.SENDER_TAGLINE, "Founder")
        sender_form.addRow("Sender Title:", self.edit_sender_tagline)
        self.edit_sender_address = self._line(config.SENDER_ADDRESS, "Mailing address")
        sender_form.addRow("Sender Address:", self.edit_sender_address)
        self.edit_sender_background = self._line(
            config.SENDER_BACKGROUND,
            "Short founder background",
        )
        sender_form.addRow("Background:", self.edit_sender_background)
        layout.addWidget(sender_group)

        product_group = QGroupBox("Offer & Messaging")
        product_form = QFormLayout(product_group)
        self.edit_product_name = self._line(config.PRODUCT_NAME, "Product or service name")
        product_form.addRow("Product Name:", self.edit_product_name)
        self.edit_product_category = self._line(config.PRODUCT_CATEGORY, "workflow automation")
        product_form.addRow("Product Category:", self.edit_product_category)
        self.edit_product_description = self._line(
            config.PRODUCT_DESCRIPTION,
            "What your product does",
        )
        product_form.addRow("Product Description:", self.edit_product_description)
        self.edit_target_role = self._line(
            config.PRODUCT_TARGET_ROLE,
            "Who this is for",
        )
        product_form.addRow("Target Role:", self.edit_target_role)
        self.edit_pain_point = self._line(
            config.PRODUCT_PAIN_POINT,
            "Problem you solve",
        )
        product_form.addRow("Pain Point:", self.edit_pain_point)
        self.edit_default_cta = self._line(
            config.DEFAULT_CTA,
            "Default call to action",
        )
        product_form.addRow("Default CTA:", self.edit_default_cta)
        layout.addWidget(product_group)

        prompt_group = QGroupBox("AI Prompt (Advanced)")
        prompt_layout = QVBoxLayout(prompt_group)
        prompt_hint = QLabel(
            "Customize the rules Gemini follows when writing emails. "
            "Use {name}, {company}, {product}, {cta} as placeholders. "
            "Leave blank to use the default prompt."
        )
        prompt_hint.setWordWrap(True)
        prompt_layout.addWidget(prompt_hint)
        self.edit_email_prompt = QPlainTextEdit(config.CUSTOM_EMAIL_PROMPT)
        self.edit_email_prompt.setPlaceholderText(
            "Example:\n"
            "1. No generic openers like 'I hope you're well'.\n"
            "2. Mention one operational pain point in one sentence.\n"
            "3. Body length under 110 words.\n"
            "4. Subject line under 6 words.\n"
            "5. Tone: Professional and peer-to-peer."
        )
        self.edit_email_prompt.setMaximumHeight(180)
        prompt_layout.addWidget(self.edit_email_prompt)
        layout.addWidget(prompt_group)

        action_row = QHBoxLayout()
        action_row.addStretch()
        btn_save = QPushButton("Save Setup")
        btn_save.setProperty("class", "success")
        btn_save.clicked.connect(lambda: self._on_save(self.get_values()))
        action_row.addWidget(btn_save)
        layout.addLayout(action_row)

    def _line(self, value: str, placeholder: str) -> QLineEdit:
        edit = QLineEdit(value)
        edit.setPlaceholderText(placeholder)
        return edit

    def _path_row(self, value: str, form: QFormLayout, save_file: bool = False) -> QLineEdit:
        wrapper = QWidget()
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)

        edit = QLineEdit(value)
        row.addWidget(edit)

        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(lambda: self._choose_file(edit, save_file=save_file))
        row.addWidget(btn_browse)

        label = "Gmail Token Path:" if save_file else "Gmail Credentials JSON:"
        form.addRow(label, wrapper)
        return edit

    def _choose_file(self, target: QLineEdit, save_file: bool = False):
        current = target.text().strip() or config.BASE_DIR
        if save_file:
            path, _ = QFileDialog.getSaveFileName(self, "Select File", current, "JSON Files (*.json);;All Files (*)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select File", current, "JSON Files (*.json);;All Files (*)")
        if path:
            target.setText(path)

    def get_values(self):
        return {
            "GMAIL_CREDENTIALS_PATH": self.edit_gmail_credentials.text().strip(),
            "GMAIL_TOKEN_PATH": self.edit_gmail_token.text().strip(),
            "GEMINI_API_KEY": self.edit_gemini_key.text().strip(),
            "MILLIONVERIFIER_API_KEY": self.edit_mv_key.text().strip(),
            "SENDER_NAME": self.edit_sender_name.text().strip(),
            "SENDER_COMPANY": self.edit_sender_company.text().strip(),
            "SENDER_DOMAIN": self.edit_sender_domain.text().strip(),
            "SENDER_LINKEDIN": self.edit_sender_linkedin.text().strip(),
            "SENDER_TAGLINE": self.edit_sender_tagline.text().strip(),
            "SENDER_ADDRESS": self.edit_sender_address.text().strip(),
            "SENDER_BACKGROUND": self.edit_sender_background.text().strip(),
            "PRODUCT_NAME": self.edit_product_name.text().strip(),
            "PRODUCT_CATEGORY": self.edit_product_category.text().strip(),
            "PRODUCT_DESCRIPTION": self.edit_product_description.text().strip(),
            "PRODUCT_TARGET_ROLE": self.edit_target_role.text().strip(),
            "PRODUCT_PAIN_POINT": self.edit_pain_point.text().strip(),
            "DEFAULT_CTA": self.edit_default_cta.text().strip(),
            "CUSTOM_EMAIL_PROMPT": self.edit_email_prompt.toPlainText().strip(),
        }
