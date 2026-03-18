
import requests
import re
import time
import json
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
import logging
import signal
from threading import Event
from email_validator import validate_email
import db
from datetime import datetime
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class EmailCrawler:
    def __init__(self, use_browser=True):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        # Standard regex
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        # Obfuscated regex (e.g., "name [at] domain . com")
        self.obfuscated_pattern = re.compile(r'([a-zA-Z0-9._%+-]+)\s*[\(\[]\s*at\s*[\)\]]\s*([a-zA-Z0-9.-]+)\s*[\(\[]\s*dot\s*[\)\]]\s*([a-zA-Z]{2,})', re.IGNORECASE)
        self.stop_signal = False

        self.use_browser = use_browser
        self.browser = None
        self.context = None
        self.playwright = None

    def start_browser(self):
        """Initialize Playwright browser if not already running."""
        if self.use_browser and not self.browser:
            try:
                from playwright.sync_api import sync_playwright
                self.playwright = sync_playwright().start()
                self.browser = self.playwright.chromium.launch(headless=True)
                self.context = self.browser.new_context(user_agent=self.headers['User-Agent'])
                logging.info("Browser started for EmailCrawler.")
            except Exception as e:
                logging.error(f"Failed to start browser: {e}")
                self.use_browser = False # Fallback to requests

    def stop(self):
        self.stop_signal = True
        try:
            if self.context:
                self.context.close()
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass

        self.context = None
        self.browser = None
        self.playwright = None

    def is_valid_email(self, email):
        """Filter out junk emails."""
        if len(email) < 5 or len(email) > 100:
            return False

        # Filter image extensions commonly mistaken for emails or junk
        junk_extensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.css', '.js']
        if any(email.lower().endswith(ext) for ext in junk_extensions):
            return False

        # Filter common junk addresses
        junk_prefixes = ['sentry', 'noreply', 'no-reply', 'admin', 'hostmaster', 'postmaster', 'webmaster', 'example', 'username', 'email']
        # Note: strict filtering might remove valid generic emails (admin@), but for cold emailing we prefer specific ones or contact@
        # Let's keep contact, info, hello, support suitable for cold outreach.

        return True

    def extract_emails_from_text(self, text):
        found = set()

        # Standard regex
        found.update(re.findall(self.email_pattern, text))

        # Obfuscated: "user [at] domain . com" -> "user@domain.com"
        simple_obfuscated = re.findall(r'([a-zA-Z0-9._%+-]+)\s*[\(\[]\s*at\s*[\)\]]\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text, re.IGNORECASE)
        for user, domain in simple_obfuscated:
            found.add(f"{user}@{domain}")

        return found

    def extract_emails_from_html_signals(self, html):
        """Extract emails from footer/meta/schema.org and structured snippets."""
        found = set()
        if not html:
            return found

        try:
            soup = BeautifulSoup(html, "html.parser")

            # Footer text often contains direct contact emails.
            for footer in soup.find_all("footer"):
                found.update(self.extract_emails_from_text(footer.get_text(" ", strip=True)))

            # Meta tags (rare, but cheap to inspect).
            for meta in soup.find_all("meta"):
                for attr in ("content", "value"):
                    value = meta.get(attr)
                    if value:
                        found.update(self.extract_emails_from_text(str(value)))

            # Schema.org JSON-LD contact points.
            for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
                raw = script.string or script.get_text() or ""
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                    payload_str = json.dumps(payload)
                    found.update(self.extract_emails_from_text(payload_str))
                except Exception:
                    # Not valid JSON; still do regex over raw text.
                    found.update(self.extract_emails_from_text(raw))
        except Exception:
            pass

        return found

    def clean_google_redirect_url(self, url):
        """Extract real URL from Google redirect URLs like /url?q=http://..."""
        if not url:
            return url

        # Handle Google redirect URLs
        if url.startswith('/url?') or 'google.com/url?' in url:
            try:
                parsed = urlparse(url)
                params = parse_qs(parsed.query)
                if 'q' in params:
                    return params['q'][0]
            except Exception:
                pass

        return url

    def fetch_page_content(self, url):
        """Fetch page content using Browser or Requests."""
        if self.use_browser:
            if not self.browser:
                self.start_browser()

            if self.browser:
                try:
                    page = self.context.new_page()
                    # Block resources to speed up
                    page.route("**/*", lambda route: route.continue_() if route.request.resource_type in ["document", "script", "xhr", "fetch"] else route.abort())

                    try:
                        page.goto(url, timeout=20000, wait_until="domcontentloaded")
                        time.sleep(2) # Allow JS to execute
                        content = page.content() # Get full HTML
                        text = page.evaluate("() => document.body.innerText") # Get visible text

                        # Get links for crawling
                        links = page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => ({href: a.href, text: a.innerText}))")

                        page.close()
                        return content, text, links
                    except Exception as e:
                        page.close()
                        logging.warning(f"Browser navigation failed for {url}: {e}")
                        # Fallback to requests?
                        pass
                except Exception as e:
                    logging.error(f"Browser error: {e}")

        # Fallback or default to Requests
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                text = resp.text # using raw html for regex often works for emails in source, but innerText is better for visible.
                # Let's use connection of both
                links = [{'href': a.get('href'), 'text': a.get_text()} for a in soup.find_all('a', href=True)]
                return resp.text, soup.get_text(), links
        except Exception as e:
            logging.warning(f"Requests failed for {url}: {e}")

        return "", "", []

    def crawl_site(self, url, log_callback=print):
        if not url:
            return []

        # Clean Google redirect URLs first
        url = self.clean_google_redirect_url(url)

        if not url.startswith('http'):
            url = 'http://' + url

        found_emails = set()
        visited = set()

        log_callback(f"Visiting home: {url}")

        # 1. Visit Homepage
        html, text, links = self.fetch_page_content(url)
        if not html:
            log_callback(f"Failed to load {url}")
            return []

        visited.add(url)

        # Extract emails
        found_emails.update(self.extract_emails_from_text(html)) # Search in source
        found_emails.update(self.extract_emails_from_text(text)) # Search in visible text (for obfuscated e.g.)
        found_emails.update(self.extract_emails_from_html_signals(html))

        # 2. Find Contact/About pages (Depth 1)
        contact_links = []

        for link_obj in links:
            href = link_obj.get('href', '')
            link_text = link_obj.get('text', '').lower() if link_obj.get('text') else ""

            if not href: continue

            href_lower = href.lower()

            # Check for mailto links first
            if 'mailto:' in href_lower:
                email = href_lower.replace('mailto:', '').split('?')[0].strip()
                if self.is_valid_email(email):
                    found_emails.add(email)

            # Look for Contact/About pages
            if any(k in link_text or k in href_lower for k in ['contact', 'about', 'team', 'staff']):
                 full_url = urljoin(url, href)

                 # Ensure it's the same domain
                 if urlparse(full_url).netloc == urlparse(url).netloc:
                     if full_url not in visited:
                         contact_links.append(full_url)

        # Limit contact pages to visit
        contact_links = list(set(contact_links))[:3] # Max 3 pages

        for link in contact_links:
            if self.stop_signal:
                break

            log_callback(f"  > Checking page: {link}")
            try:
                time.sleep(1.0)
                sub_html, sub_text, sub_links = self.fetch_page_content(link)
                found_emails.update(self.extract_emails_from_text(sub_html))
                found_emails.update(self.extract_emails_from_text(sub_text))
                found_emails.update(self.extract_emails_from_html_signals(sub_html))
            except Exception as e:
                pass

        # Filter and clean
        valid_emails = [e for e in found_emails if self.is_valid_email(e)]
        return list(valid_emails)

STOP_REQUESTED = False
STOP_EVENT = Event()


def request_crawl_stop():
    """Signal crawler loop to stop safely across threads."""
    global STOP_REQUESTED
    STOP_REQUESTED = True
    STOP_EVENT.set()

def run_crawler_on_file(input_csv="data/output/today_targets.csv", output_csv=None, log_callback=print):
    # Default: overwrite the same file (update in place)
    if output_csv is None:
        output_csv = input_csv
    crawler = EmailCrawler()
    global STOP_REQUESTED
    STOP_REQUESTED = False
    STOP_EVENT.clear()

    try:
        df = pd.read_csv(input_csv)
    except FileNotFoundError:
        log_callback(f"Input file not found: {input_csv}")
        return

    if "Website" not in df.columns:
        log_callback("No 'Website' column in CSV.")
        return

    log_callback(f"Found {len(df)} targets. Starting crawl...")

    # Check if 'Email' column exists, if not create it
    if "Email" not in df.columns:
        df["Email"] = ""

    save_interval = 5

    for i, row in df.iterrows():
        if crawler.stop_signal or STOP_REQUESTED or STOP_EVENT.is_set():
            log_callback("Stopping crawler...")
            break

        website = str(row["Website"])
        company = str(row["Company"])

        # Skip if empty website or already has email
        if pd.isna(website) or not website or website.lower() == 'nan':
            continue

        current_email = str(row.get("Email", ""))
        if current_email and current_email.lower() != 'nan':
            continue

        log_callback(f"[{i+1}/{len(df)}] Crawling {company} ({website})...")

        emails = crawler.crawl_site(website, log_callback)

        if emails:
            # Filter for valid emails first
            valid_candidates = []
            for e in emails:
                # Basic quick check
                if not crawler.is_valid_email(e):
                    continue
                # DNS check
                v = validate_email(e)
                if v["valid"]:
                    valid_candidates.append(e)
                else:
                    log_callback(f"  Invalid MX/Email: {e} ({v.get('error')})")

            if valid_candidates:
                # Prioritize info@, contact@ if multiple
                primary = valid_candidates[0]
                for e in valid_candidates:
                    if any(x in e for x in ['info', 'contact', 'hello', 'support']):
                        primary = e
                        break

                df.at[i, "Email"] = primary
                log_callback(f"  Found & Validated: {primary}")
            else:
                log_callback("  Emails found but all failed validation.")
        else:
            log_callback("  No email found.")

        # Auto-save every few rows
        if (i + 1) % save_interval == 0:
            df.to_csv(output_csv, index=False)

        time.sleep(1) # Delay between companies

    df.to_csv(output_csv, index=False)
    log_callback(f"Done! Saved with emails to {output_csv}")
    return output_csv


def run_crawler_on_db(target_date=None, log_callback=print):
    """Crawl emails for daily targets stored in SQLite and update leads.email."""
    crawler = EmailCrawler()
    global STOP_REQUESTED
    STOP_REQUESTED = False
    STOP_EVENT.clear()

    db.init()
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")

    targets = db.get_daily_targets(target_date)
    if not targets:
        log_callback(f"No daily targets found for {target_date}. Falling back to high-score leads missing email.")
        targets = db.get_leads_missing_email(limit=50, min_score=config.MIN_LEAD_SCORE)
        if not targets:
            log_callback("No leads available for email crawling.")
            return 0

    log_callback(f"Found {len(targets)} DB targets. Starting crawl...")
    updated_count = 0

    for i, row in enumerate(targets):
        if crawler.stop_signal or STOP_REQUESTED or STOP_EVENT.is_set():
            log_callback("Stopping crawler...")
            break

        lead_id = int(row.get("id", 0))
        website = str(row.get("website", "")).strip()
        company = str(row.get("company", ""))
        current_email = str(row.get("email", "")).strip()

        if not website:
            continue
        if current_email and current_email.lower() != "nan":
            continue

        log_callback(f"[{i + 1}/{len(targets)}] Crawling {company} ({website})...")
        emails = crawler.crawl_site(website, log_callback)

        if emails:
            valid_candidates = []
            for e in emails:
                if not crawler.is_valid_email(e):
                    continue
                v = validate_email(e)
                if v["valid"]:
                    valid_candidates.append(e)
                else:
                    log_callback(f"  Invalid MX/Email: {e} ({v.get('error')})")

            if valid_candidates:
                primary = valid_candidates[0]
                for e in valid_candidates:
                    if any(x in e for x in ['info', 'contact', 'hello', 'support']):
                        primary = e
                        break
                db.update_lead(lead_id, {"email": primary, "email_valid": 1})
                updated_count += 1
                log_callback(f"  Found & Updated: {primary}")
            else:
                log_callback("  Emails found but all failed validation.")
                db.update_lead(lead_id, {"email_valid": 0})
        else:
            log_callback("  No email found.")

        time.sleep(1)

    log_callback(f"Done! Updated {updated_count} leads in DB.")
    return updated_count

def smart_hunt_email(website_url, company_name, gemini_helper, log_callback=print, session=None):
    """
    Advanced email hunting using Playwright and Gemini.
    Can follow redirects, find contact pages, and handle complex site structures.
    """
    from playwright.sync_api import sync_playwright

    crawler = EmailCrawler()
    url = crawler.clean_google_redirect_url(website_url)
    if not url.startswith('http'):
        url = 'https://' + url

    log_callback(f"Smart Hunting: {company_name} ({url})")

    owned_playwright = None
    browser = None
    context = None
    page = None

    try:
        if session is not None:
            context = session.context
            page = context.new_page()
        else:
            owned_playwright = sync_playwright().start()
            browser = owned_playwright.chromium.launch(headless=True)
            context = browser.new_context(user_agent=crawler.headers['User-Agent'])
            page = context.new_page()

        # 1. Visit URL
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            time.sleep(3) # Let some JS run

            # Get text AND all links
            page_text = page.evaluate("() => document.body.innerText")
            links = page.evaluate("() => Array.from(document.querySelectorAll('a')).map(a => ({href: a.href, text: a.innerText}))")

            # FAST PATH: Regex check first
            found_emails = crawler.extract_emails_from_text(page_text)
            # Also check mailto links
            for l in links:
                if "mailto:" in l['href'].lower():
                    email = l['href'].lower().replace('mailto:', '').split('?')[0].strip()
                    if crawler.is_valid_email(email):
                        found_emails.add(email)

            if found_emails:
                # Pick best one (info/contact)
                primary = list(found_emails)[0]
                for e in found_emails:
                    if any(x in e for x in ['info', 'contact', 'hello', 'support']):
                        primary = e
                        break
                log_callback(f"  Regex found email: {primary}")
                return primary

            # AI PATH: Ask Gemini to find/suggest
            # Combine text with some link info
            context_blob = page_text + "\n\nLinks found:\n" + "\n".join([f"{l['text']}: {l['href']}" for l in links[:20]])

            result = gemini_helper.extract_email_from_text(context_blob, company_name)

            if "@" in result:
                log_callback(f"  AI found email: {result}")
                return result

            if result.startswith("http"):
                # Visit the contact page AI suggested
                contact_url = result
                log_callback(f"  AI suggests contact page: {contact_url}")
                page.goto(contact_url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(3)
                page_text = page.evaluate("() => document.body.innerText")

                # One more Regex check on the new page
                found_emails = crawler.extract_emails_from_text(page_text)
                if found_emails:
                    log_callback(f"  Regex found on subpage: {list(found_emails)[0]}")
                    return list(found_emails)[0]

                result = gemini_helper.extract_email_from_text(page_text, company_name)
                if "@" in result:
                    log_callback(f"  AI found on contact page: {result}")
                    return result

        except Exception as e:
            log_callback(f"  Navigation error: {e}")

    except Exception as e:
        log_callback(f"  Smart Hunt error: {e}")
    finally:
        try:
            if page:
                page.close()
            if browser:
                browser.close()
            if owned_playwright:
                owned_playwright.stop()
        except Exception:
            pass

    return ""


class SmartHuntSession:
    """Reusable browser session for smart hunt batches."""
    def __init__(self):
        from playwright.sync_api import sync_playwright
        self._manager = sync_playwright().start()
        self.browser = self._manager.chromium.launch(headless=True)
        self.context = self.browser.new_context(user_agent=EmailCrawler().headers['User-Agent'])

    def close(self):
        try:
            self.context.close()
            self.browser.close()
            self._manager.stop()
        except Exception:
            pass


def smart_hunt_batch(rows, gemini_helper, log_callback=print):
    """
    Run smart hunt on multiple rows while reusing a single browser context.
    rows: iterable of dict-like with keys website/company.
    """
    results = []
    session = None
    try:
        session = SmartHuntSession()
        crawler = EmailCrawler()
        page = session.context.new_page()
        for row in rows:
            website = row.get("website") or row.get("Website") or ""
            company = row.get("company") or row.get("Company") or "Unknown"
            if not website:
                results.append({"company": company, "email": ""})
                continue

            # Reuse existing single-item implementation for reliability
            email = smart_hunt_email(website, company, gemini_helper, log_callback=log_callback, session=session)
            results.append({"company": company, "email": email})

            try:
                page.goto("about:blank", timeout=5000)
            except Exception:
                pass
    finally:
        if session:
            session.close()
    return results

if __name__ == "__main__":
    # Test run
    print("Testing crawler...")
    # run_crawler_on_file()

def _verify_web_context(company_name: str, web_text: str) -> str:
    """Return web_text only if it appears to match the company. Otherwise empty."""
    if not web_text or not company_name:
        return ""
    company_lower = company_name.lower()
    text_lower = web_text.lower()
    # Check if full company name appears in crawled text
    if company_lower in text_lower:
        return web_text
    # Check if any significant word (3+ chars) from company name appears
    words = [w for w in company_lower.split() if len(w) >= 3]
    matches = sum(1 for w in words if w in text_lower)
    if words and matches >= len(words) * 0.5:
        return web_text
    return ""
