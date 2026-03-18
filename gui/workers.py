import traceback
import os
import pandas as pd
from PySide6.QtCore import QThread, Signal
import google_maps_scraper
from google_maps_scraper import ScraperState
import process_leads
import crawl_emails
import sys
from datetime import datetime
import time

from outreach_scheduler import now_est, is_optimal_send_time, next_optimal_send_time
from tracking import new_tracking_id, wrap_links_for_tracking, to_simple_html_email
import followup_manager
import config
import db
from crawl_emails import _verify_web_context

class EmailCrawlerThread(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, input_file):
        super().__init__()
        self.input_file = input_file
        self.crawler = crawl_emails.EmailCrawler()

    def run(self):
        try:
            self.log_signal.emit("Started safe email crawling...")
            updated = crawl_emails.run_crawler_on_db(log_callback=self.log_signal.emit)
            self.finished_signal.emit(f"Crawling finished! Updated {updated} leads in SQLite.")

        except Exception as e:
            self.log_signal.emit(f"Error: {e}")
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit("Crawling failed.")

    def stop(self):
        crawl_emails.request_crawl_stop()

class ScraperThread(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, mode, params, state):
        super().__init__()
        self.mode = mode
        self.params = params
        self.state = state

    def run(self):
        try:
            if self.mode == "GOOGLE_MAPS":
                keywords = self.params.get("keywords", [])
                location = self.params.get("location", "")
                use_city_loop = self.params.get("use_city_loop", False)
                headless = self.params.get("headless", False)
                max_results = self.params.get("max_results", 10)
                result = google_maps_scraper.scrape_google_maps(
                    keywords=keywords,
                    location=location,
                    use_city_loop=use_city_loop,
                    headless=headless,
                    max_results=max_results,
                    log_callback=self.log_signal.emit,
                    state=self.state
                )
            else:
                result = None

            if self.state.stopped:
                self.finished_signal.emit("Stopped by user. Partial data may have been saved.")
            elif result:
                self.finished_signal.emit(f"Done! Saved to: {result}")
            else:
                self.finished_signal.emit("Done. No data saved.")

        except Exception as e:
            self.log_signal.emit(f"ERROR: {str(e)}")
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit("Failed with error.")


class PipelineThread(QThread):
    """Thread for running the pipeline processing."""
    log_signal = Signal(str)
    finished_signal = Signal(str)

    def __init__(self, custom_settings=None):
        super().__init__()
        self.custom_settings = custom_settings or {}

    def run(self):
        try:
            # Apply custom settings if provided
            if self.custom_settings.get("blacklist"):
                process_leads.BLACKLIST = self.custom_settings["blacklist"]
            if self.custom_settings.get("score_keywords"):
                process_leads.SCORE_KEYWORDS = self.custom_settings["score_keywords"]
            if self.custom_settings.get("daily_target_count"):
                process_leads.DAILY_TARGET_COUNT = self.custom_settings["daily_target_count"]

            # Redirect print to our log
            import builtins
            original_print = builtins.print
            def custom_print(*args, **kwargs):
                msg = " ".join(str(a) for a in args)
                self.log_signal.emit(msg)
            builtins.print = custom_print

            try:
                process_leads.process_leads()
                self.finished_signal.emit("Pipeline completed successfully!")
            finally:
                builtins.print = original_print

        except Exception as e:
            self.log_signal.emit(f"PIPELINE ERROR: {str(e)}")
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit("Pipeline failed with error.")

class EmailVerificationThread(QThread):
    """Thread for running MillionVerifier email verification."""
    log_signal = Signal(str)
    finished_signal = Signal(str)

    def run(self):
        try:
            db.init()
            checked, valid, invalid = process_leads.verify_emails_millionverifier(
                log_callback=self.log_signal.emit
            )
            if checked > 0:
                self.finished_signal.emit(
                    f"Verification complete: {checked} checked, {valid} valid, {invalid} invalid"
                )
            else:
                self.finished_signal.emit("No emails needed verification.")
        except Exception as e:
            self.log_signal.emit(f"Verification error: {e}")
            self.log_signal.emit(traceback.format_exc())
            self.finished_signal.emit("Verification failed with error.")


class SmartHuntWorker(QThread):
    log_signal = Signal(str)
    finished_signal = Signal(dict) # Returns original row index and found email

    def __init__(self, row_index, website, company, gemini):
        super().__init__()
        self.row_index = row_index
        self.website = website
        self.company = company
        self.gemini = gemini

    def run(self):
        try:
            email = crawl_emails.smart_hunt_email(
                self.website,
                self.company,
                self.gemini,
                log_callback=self.log_signal.emit
            )
            self.finished_signal.emit({"index": self.row_index, "email": email})
        except Exception as e:
            self.log_signal.emit(f"Worker error: {e}")
            self.finished_signal.emit({"index": self.row_index, "email": ""})

class DraftWorker(QThread):
    progress = Signal(int)
    log = Signal(str)
    finished = Signal()

    def __init__(
        self,
        sender,
        targets,
        subject_tmpl,
        body_tmpl,
        gemini=None,
        use_ai=False,
        tracking_enabled=False,
        tracking_base_url="",
        followup_mode=False,
        enhanced_params=None
    ):
        super().__init__()
        self.sender = sender
        self.targets = targets
        self.subject_tmpl = subject_tmpl
        self.body_tmpl = body_tmpl
        self.gemini = gemini
        self.use_ai = use_ai
        self.tracking_enabled = tracking_enabled
        self.tracking_base_url = tracking_base_url.strip()
        self.followup_mode = followup_mode
        self.enhanced_params = enhanced_params
        self.is_running = True

    def _build_followup_content(self, row):
        company = str(row.get("company", row.get("Company", "")))
        followup_number = int(row.get("next_followup_number", int(row.get("followup_count", 0)) + 1))

        subject = f"Quick follow-up for {company}"

        if followup_number <= 1:
            body = (
                f"Hi there,\n\n"
                f"Following up on my earlier note about helping {company} reduce repetitive manual work.\n"
                f"{config.PRODUCT_NAME} is built for teams dealing with {config.PRODUCT_PAIN_POINT}.\n\n"
                f"{config.DEFAULT_CTA}\n\n"
                f"Best,\n"
                f"{config.SENDER_NAME}\n"
                f"{config.SENDER_TAGLINE}\n"
                f"{config.SENDER_COMPANY}\n"
                f"{config.SENDER_DOMAIN} | LinkedIn: {config.SENDER_LINKEDIN}"
            )
        elif followup_number == 2:
            body = (
                f"Hi there,\n\n"
                f"Wanted to check in once more in case my prior note got buried.\n"
                f"{config.PRODUCT_NAME} helps teams like {company} move faster by simplifying repetitive workflows.\n\n"
                f"{config.DEFAULT_CTA}\n\n"
                f"Best,\n"
                f"{config.SENDER_NAME}\n"
                f"{config.SENDER_TAGLINE}\n"
                f"{config.SENDER_COMPANY}\n"
                f"{config.SENDER_DOMAIN} | LinkedIn: {config.SENDER_LINKEDIN}"
            )
        else:
            body = (
                f"Hi there,\n\n"
                f"Final follow-up from me.\n"
                f"If improving workflow efficiency at {company} is still a priority, {config.PRODUCT_NAME} may be a fit.\n\n"
                f"If not relevant now, I will close the loop.\n\n"
                f"Best,\n"
                f"{config.SENDER_NAME}\n"
                f"{config.SENDER_TAGLINE}\n"
                f"{config.SENDER_COMPANY}\n"
                f"{config.SENDER_DOMAIN} | LinkedIn: {config.SENDER_LINKEDIN}"
            )

        return subject, body

    def _apply_tracking(self, body_text: str, row: pd.Series):
        if not self.tracking_enabled or not self.tracking_base_url:
            return body_text, "", ""

        tracking_id = str(row.get("tracking_id", "")).strip() or new_tracking_id()
        tracked_text = wrap_links_for_tracking(body_text, self.tracking_base_url, tracking_id)
        body_html = to_simple_html_email(tracked_text, self.tracking_base_url, tracking_id)
        return tracked_text, body_html, tracking_id

    def run(self):
        total = len(self.targets)
        if total == 0:
            self.finished.emit()
            return

        for i, (_, row) in enumerate(self.targets.iterrows()):
            if not self.is_running:
                break

            raw_company = str(row.get("Company", row.get("company", "")))
            # For "Name @ Org" style entries, use org name as company
            if " @ " in raw_company:
                company = raw_company.split(" @ ", 1)[1]
            else:
                company = raw_company
            company_norm = followup_manager.normalize_company(raw_company)
            lead_id_value = row.get("lead_id", row.get("id"))
            try:
                lead_id = int(lead_id_value)
            except (TypeError, ValueError):
                lead_id = None
            name = str(row.get("Name", row.get("contact_person", ""))).strip()
            if not name or name.lower() in ("nan", "valued partner", "none"):
                name = ""
            email = str(row.get("Email", row.get("email", ""))).strip()

            if not email or email.lower() == "nan":
                self.log.emit(f"Skipping {company}: No Email")
                self.progress.emit(int(((i + 1) / total) * 100))
                continue

            try:
                subject = ""
                body = ""

                if self.followup_mode:
                    subject, body = self._build_followup_content(row)
                else:
                    ai_intro = ""
                    if self.use_ai and self.gemini:
                        title = str(row.get("Title", row.get("title", "")))
                        # Legacy field fallback for imported credential values
                        if (not title or title.lower() in ("", "nan")) and row.get("leed_credential"):
                            title = str(row.get("leed_credential"))
                        location = str(row.get("Location", row.get("state", "")))

                        if self.enhanced_params:
                            web_context = ""
                            # Use org_foundation as context if available
                            org_foundation = str(row.get("org_foundation", "")).strip()
                            if org_foundation and org_foundation.lower() != "nan":
                                web_context = f"Company mission/about: {org_foundation}"

                            if self.enhanced_params.get("use_web") and not web_context:
                                try:
                                    website = str(row.get("Website", row.get("website", "")))
                                    if website and website.lower() != "nan":
                                        import requests
                                        from bs4 import BeautifulSoup
                                        if not website.startswith("http"):
                                            website = "https://" + website
                                        resp = requests.get(website, timeout=7, headers={"User-Agent": "Mozilla/5.0"})
                                        raw_text = BeautifulSoup(resp.text, "html.parser").get_text()[:4000]
                                        web_context = _verify_web_context(company, raw_text)
                                except Exception:
                                    pass

                            full_res = self.gemini.generate_full_email(
                                company,
                                name=name,
                                title=title,
                                location=location,
                                web_context=web_context,
                                tone=self.enhanced_params.get("tone"),
                                cta=self.enhanced_params.get("cta"),
                            )
                            if full_res.startswith("Subject:"):
                                # Expected format: "Subject: ...\n---\nBody..."
                                parts = full_res.split("---", 1)
                                subject = parts[0].replace("Subject:", "").strip()
                                body = parts[1].strip() if len(parts) > 1 else ""
                            elif "\n" in full_res.strip():
                                # No "Subject:" prefix — treat first line as subject
                                lines = full_res.strip().split("\n", 1)
                                subject = lines[0].strip()
                                body = lines[1].strip() if len(lines) > 1 else ""
                            else:
                                subject = f"Quick idea for {company}"
                                body = full_res
                        else:
                            ai_intro = self.gemini.generate_intro(company, name=name, job_title=title, location=location)
                            subject = self.subject_tmpl.replace("{Company}", company).replace("{Name}", name).replace("{AI_Intro}", ai_intro)
                            body = self.body_tmpl.replace("{Company}", company).replace("{Name}", name).replace("{AI_Intro}", ai_intro)

                        time.sleep(1)

                    if not subject:
                        if not ai_intro:
                            ai_intro = f"I came across {company} and was impressed by your work."
                        subject = self.subject_tmpl.replace("{Company}", company).replace("{Name}", name).replace("{AI_Intro}", ai_intro)
                        body = self.body_tmpl.replace("{Company}", company).replace("{Name}", name).replace("{AI_Intro}", ai_intro)

                tracked_body, body_html, tracking_id = self._apply_tracking(body, row)

            except Exception as e:
                self.log.emit(f"Error formatting for {company}: {e}")
                self.progress.emit(int(((i + 1) / total) * 100))
                continue

            try:
                today_str = datetime.today().strftime("%Y-%m-%d")
                history_dir = os.path.join("data", "history", today_str)
                os.makedirs(history_dir, exist_ok=True)

                safe_company = "".join([c for c in company if c.isalnum() or c in (" ", "_", "-")]).strip()
                if not safe_company:
                    safe_company = "Unknown_Company"
                filename = f"{safe_company}.txt"

                with open(os.path.join(history_dir, filename), "w", encoding="utf-8") as f:
                    f.write(f"To: {name} ({email})\\n")
                    f.write(f"Company: {company}\\n")
                    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n")
                    if tracking_id:
                        f.write(f"Tracking ID: {tracking_id}\\n")
                    f.write("-" * 30 + "\\n")
                    f.write(f"Subject: {subject}\\n")
                    f.write("-" * 30 + "\\n")
                    f.write(tracked_body)
            except Exception as e:
                self.log.emit(f"Could not save history file: {e}")

            res = self.sender.create_draft(email, subject, tracked_body, body_html=body_html or None)
            if res:
                self.log.emit(f"Draft created for {company} ({email})")
                if self.followup_mode:
                    followup_manager.mark_followup_sent(company_norm, tracking_id=tracking_id, lead_id=lead_id)
                elif tracking_id:
                    followup_manager.save_records([
                        {
                            "lead_id": lead_id,
                            "company": company,
                            "company_norm": company_norm,
                            "status": "sent",
                            "email": email,
                            "tracking_id": tracking_id,
                            "last_sent_date": datetime.now().strftime("%Y-%m-%d"),
                            "note": "tracking-enabled",
                        }
                    ])
            else:
                self.log.emit(f"Failed to create draft for {company}")

            time.sleep(0.5)
            self.progress.emit(int(((i + 1) / total) * 100))

        self.finished.emit()

    def stop(self):
        self.is_running = False
