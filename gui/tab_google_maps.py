from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton,
    QCheckBox, QLineEdit, QSpinBox
)


class GoogleMapsTab(QWidget):
    def __init__(self, on_run, on_toggle_location, on_set_keywords):
        super().__init__()
        self._on_set_keywords = on_set_keywords
        self._build_ui(on_run, on_toggle_location)

    def _build_ui(self, on_run, on_toggle_location):
        layout = QVBoxLayout(self)

        loc_layout = QHBoxLayout()
        loc_lbl = QLabel("Target Location:")
        self.maps_location = QLineEdit("New York, USA")
        loc_layout.addWidget(loc_lbl)
        loc_layout.addWidget(self.maps_location)
        layout.addLayout(loc_layout)

        self.chk_city_loop = QCheckBox("Auto-Loop Top 50 US Cities (Includes Portland, Seattle, etc.)")
        self.chk_city_loop.toggled.connect(on_toggle_location)
        layout.addWidget(self.chk_city_loop)

        max_layout = QHBoxLayout()
        max_lbl = QLabel("Max Results per Search:")
        self.maps_max_results = QSpinBox()
        self.maps_max_results.setRange(1, 100)
        self.maps_max_results.setValue(10)
        max_layout.addWidget(max_lbl)
        max_layout.addWidget(self.maps_max_results)
        max_layout.addStretch()
        layout.addLayout(max_layout)

        preset_layout = QHBoxLayout()
        btn_preset_consult = QPushButton("Preset: Consulting Firms")
        btn_preset_consult.clicked.connect(lambda: self._on_set_keywords([
            "Business consulting firm", "Operations consulting", "Strategy consulting",
            "Workflow automation consultant", "Process improvement services"
        ]))
        preset_layout.addWidget(btn_preset_consult)

        btn_preset_arch = QPushButton("Preset: Agencies & Services")
        btn_preset_arch.clicked.connect(lambda: self._on_set_keywords([
            "Digital agency", "Marketing agency", "B2B services company",
            "Software development agency", "Lead generation company"
        ]))
        preset_layout.addWidget(btn_preset_arch)
        layout.addLayout(preset_layout)

        lbl = QLabel("Keywords (One per line):")
        layout.addWidget(lbl)

        self.maps_input = QTextEdit()
        self.maps_input.setPlaceholderText("Business consulting\nWorkflow automation")
        layout.addWidget(self.maps_input)

        self.maps_headless = QCheckBox("Run in Background (Headless)")
        self.maps_headless.setChecked(False)
        layout.addWidget(self.maps_headless)

        self.btn_maps_run = QPushButton("Start Google Maps Scraping")
        self.btn_maps_run.setProperty("class", "success")
        self.btn_maps_run.clicked.connect(on_run)
        layout.addWidget(self.btn_maps_run)
