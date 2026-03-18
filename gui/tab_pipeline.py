from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QTableWidget, QAbstractItemView, QHeaderView, QCheckBox
)

import config


class PipelineTab(QWidget):
    def __init__(
        self,
        on_edit_scoring,
        on_edit_blacklist,
        on_run_pipeline,
        on_run_email_crawler,
        on_refresh_targets,
        on_run_smart_hunt,
        on_create_drafts_selected,
        on_mark_selected_sent,
        on_mark_all_sent,
        on_targets_click,
        on_targets_hover,
        on_verify_emails=None,
    ):
        super().__init__()
        self._build_ui(
            on_edit_scoring,
            on_edit_blacklist,
            on_run_pipeline,
            on_run_email_crawler,
            on_refresh_targets,
            on_run_smart_hunt,
            on_create_drafts_selected,
            on_mark_selected_sent,
            on_mark_all_sent,
            on_targets_click,
            on_targets_hover,
            on_verify_emails,
        )

    def _build_ui(
        self,
        on_edit_scoring,
        on_edit_blacklist,
        on_run_pipeline,
        on_run_email_crawler,
        on_refresh_targets,
        on_run_smart_hunt,
        on_create_drafts_selected,
        on_mark_selected_sent,
        on_mark_all_sent,
        on_targets_click,
        on_targets_hover,
        on_verify_emails=None,
    ):
        layout = QVBoxLayout(self)

        settings_layout = QHBoxLayout()

        target_layout = QHBoxLayout()
        target_lbl = QLabel("Daily Targets:")
        self.daily_target_spin = QSpinBox()
        self.daily_target_spin.setRange(1, 100)
        self.daily_target_spin.setValue(config.DAILY_TARGET_COUNT)
        target_layout.addWidget(target_lbl)
        target_layout.addWidget(self.daily_target_spin)
        settings_layout.addLayout(target_layout)

        settings_layout.addStretch()

        btn_scoring = QPushButton("Edit Scoring")
        btn_scoring.clicked.connect(on_edit_scoring)
        settings_layout.addWidget(btn_scoring)

        btn_blacklist = QPushButton("Edit Blacklist")
        btn_blacklist.clicked.connect(on_edit_blacklist)
        settings_layout.addWidget(btn_blacklist)

        layout.addLayout(settings_layout)

        pipeline_row = QHBoxLayout()
        btn_run_pipeline = QPushButton("Run Pipeline (SQLite)")
        btn_run_pipeline.setProperty("class", "purple")
        btn_run_pipeline.clicked.connect(on_run_pipeline)
        pipeline_row.addWidget(btn_run_pipeline)

        self.chk_project_activity = QCheckBox("Use Project Activity Scoring (slower)")
        self.chk_project_activity.setToolTip(
            "Query USGBC project history per org to score leads by recent activity.\n"
            "Adds ~1 API call per USGBC org lead. Recommended for first-time scoring."
        )
        pipeline_row.addWidget(self.chk_project_activity)
        pipeline_row.addStretch()
        layout.addLayout(pipeline_row)

        verify_row = QHBoxLayout()
        btn_clean_crawl = QPushButton("Find Emails for Targets (Safe Mode - Slow)")
        btn_clean_crawl.setProperty("class", "warning")
        btn_clean_crawl.clicked.connect(on_run_email_crawler)
        verify_row.addWidget(btn_clean_crawl)

        if on_verify_emails:
            btn_verify = QPushButton("Verify Emails (MillionVerifier)")
            btn_verify.setToolTip(
                "Deep email verification via MillionVerifier API.\n"
                "Checks if mailbox actually exists (not just domain).\n"
                "Uses 1 API credit per email. Filters out invalid addresses."
            )
            btn_verify.setProperty("class", "purple")
            btn_verify.clicked.connect(on_verify_emails)
            verify_row.addWidget(btn_verify)

        layout.addLayout(verify_row)

        targets_label = QLabel("Today's Targets (Ctrl+Click URL to open):")
        targets_label.setProperty("class", "subheader")
        layout.addWidget(targets_label)

        self.targets_table = QTableWidget()
        self.targets_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.targets_table.setAlternatingRowColors(True)
        self.targets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.targets_table.horizontalHeader().setStretchLastSection(True)
        self.targets_table.cellClicked.connect(on_targets_click)
        self.targets_table.setMouseTracking(True)
        self.targets_table.cellEntered.connect(on_targets_hover)
        layout.addWidget(self.targets_table)

        target_btn_layout = QHBoxLayout()

        btn_refresh = QPushButton("Refresh Targets")
        btn_refresh.clicked.connect(on_refresh_targets)
        target_btn_layout.addWidget(btn_refresh)

        self.btn_reset_targets = QPushButton("Reset Today's Targets")
        self.btn_reset_targets.setProperty("class", "danger")
        target_btn_layout.addWidget(self.btn_reset_targets)

        btn_smart_hunt = QPushButton("Smart Find Email (AI)")
        btn_smart_hunt.setProperty("class", "purple")
        btn_smart_hunt.clicked.connect(on_run_smart_hunt)
        target_btn_layout.addWidget(btn_smart_hunt)

        btn_draft_selected = QPushButton("Create Drafts for Selected")
        btn_draft_selected.setProperty("class", "success")
        btn_draft_selected.clicked.connect(on_create_drafts_selected)
        target_btn_layout.addWidget(btn_draft_selected)

        btn_mark_sent = QPushButton("Mark Selected as Sent")
        btn_mark_sent.setProperty("class", "success")
        btn_mark_sent.clicked.connect(on_mark_selected_sent)
        target_btn_layout.addWidget(btn_mark_sent)

        btn_mark_all = QPushButton("Mark All as Sent")
        btn_mark_all.setProperty("class", "warning")
        btn_mark_all.clicked.connect(on_mark_all_sent)
        target_btn_layout.addWidget(btn_mark_all)

        layout.addLayout(target_btn_layout)
