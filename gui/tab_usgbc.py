from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit

import config


class USGBCTab(QWidget):
    def __init__(self, on_run_org, on_run_person):
        super().__init__()
        self._build_ui(on_run_org, on_run_person)

    def _build_ui(self, on_run_org, on_run_person):
        layout = QVBoxLayout(self)

        country_layout = QHBoxLayout()
        country_layout.addWidget(QLabel("Countries (comma separated):"))
        self.usgbc_countries = QLineEdit("United States")
        self.usgbc_countries.setPlaceholderText("e.g. United States, India, United Arab Emirates")
        country_layout.addWidget(self.usgbc_countries)
        layout.addLayout(country_layout)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Subcategories (comma separated):"))
        self.usgbc_subcategories = QLineEdit(", ".join(config.USGBC_DEFAULT_SUBCATEGORIES))
        filter_layout.addWidget(self.usgbc_subcategories)
        layout.addLayout(filter_layout)

        state_layout = QHBoxLayout()
        state_layout.addWidget(QLabel("States (optional, comma separated):"))
        self.usgbc_states = QLineEdit("")
        state_layout.addWidget(self.usgbc_states)
        layout.addLayout(state_layout)

        cred_layout = QHBoxLayout()
        cred_layout.addWidget(QLabel("People Credentials (comma separated, optional):"))
        self.usgbc_credentials = QLineEdit(", ".join(config.USGBC_DEFAULT_CREDENTIALS))
        cred_layout.addWidget(self.usgbc_credentials)
        layout.addLayout(cred_layout)

        btn_layout = QHBoxLayout()
        self.btn_org = QPushButton("Scrape Organizations")
        self.btn_org.setProperty("class", "success")
        self.btn_org.clicked.connect(on_run_org)
        btn_layout.addWidget(self.btn_org)

        self.btn_person = QPushButton("Scrape People")
        self.btn_person.setProperty("class", "primary")
        self.btn_person.clicked.connect(on_run_person)
        btn_layout.addWidget(self.btn_person)

        layout.addLayout(btn_layout)

        info = QLabel("USGBC results are written directly to the local leads database.")
        info.setProperty("class", "subheader")
        layout.addWidget(info)
