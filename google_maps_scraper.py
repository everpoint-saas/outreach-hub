import os
import pandas as pd
import time
import random
import re
from datetime import datetime
from us_cities import TOP_50_CITIES
import config
import db

# Shared state for pause/resume/stop
class ScraperState:
    def __init__(self):
        self.paused = False
        self.stopped = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self.stopped = True

    def reset(self):
        self.paused = False
        self.stopped = False


def parse_raw_data(raw_lines: list) -> dict:
    """
    Parse Google Maps raw text into structured fields.
    Returns: {website, phone, address, rating, review_count}
    """
    result = {
        "website": "",
        "phone": "",
        "address": "",
        "rating": "",
        "review_count": ""
    }

    text = " ".join(raw_lines)

    # Phone pattern (US format)
    phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
    if phone_match:
        result["phone"] = phone_match.group()

    # Rating pattern (e.g., "4.8" or "4.8(123)")
    rating_match = re.search(r'(\d\.\d)\s*\((\d+)\)', text)
    if rating_match:
        result["rating"] = rating_match.group(1)
        result["review_count"] = rating_match.group(2)

    # Try to find address-like text (contains street indicators)
    for line in raw_lines:
        line_lower = line.lower()
        # Skip if it's a phone or website
        if re.search(r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', line):
            continue
        if "www." in line_lower or ".com" in line_lower:
            result["website"] = line.strip()
            continue
        # Address indicators
        if any(x in line_lower for x in ['st', 'ave', 'blvd', 'rd', 'dr', 'ln', 'way', 'suite', 'floor', '#']):
            if len(line) > 10:  # Avoid short matches
                result["address"] = line.strip()

    return result


def scrape_google_maps(keywords, location="", use_city_loop=False, headless=False,
                       max_results=config.MAX_RESULTS_PER_SEARCH, log_callback=print, state=None):
    """
    Executes Google Maps scraping with improved field parsing.
    """
    if state is None:
        state = ScraperState()

    target_locations = []
    if use_city_loop:
        target_locations = TOP_50_CITIES
        log_callback(f"Targeting Top {len(target_locations)} US Cities")
    else:
        target_locations = [location] if location else [""]

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        log_callback("Launching Browser (Edge)...")
        browser = p.chromium.launch(headless=headless, channel="msedge")
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = context.new_page()

        all_leads = []
        seen_companies = set()
        db.init()
        inserted_count = 0
        duplicate_count = 0

        for base_keyword in keywords:
            if state.stopped:
                log_callback("Scraping stopped by user.")
                break

            base_keyword = base_keyword.strip()
            if not base_keyword:
                continue

            for loc in target_locations:
                if state.stopped:
                    break

                while state.paused:
                    log_callback("Paused... waiting to resume")
                    time.sleep(1)
                    if state.stopped:
                        break

                search_term = f"{base_keyword} in {loc}" if loc else base_keyword
                log_callback(f"--- Searching: {search_term} ---")

                try:
                    page.goto("https://www.google.com/maps", timeout=60000)
                except Exception as e:
                    log_callback(f"Error loading Google Maps: {e}")
                    continue

                try:
                    search_box = page.locator('input#searchboxinput')
                    search_box.wait_for(state="visible", timeout=10000)
                    search_box.fill(search_term)
                    page.keyboard.press("Enter")
                except Exception as e:
                    log_callback(f"Error finding search box: {e}")
                    continue

                # CAPTCHA detection loop
                captcha_wait_start = time.time()
                max_captcha_wait = config.MAX_CAPTCHA_WAIT
                while True:
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=5000)
                    except:
                        pass

                    try:
                        page_content = page.content().lower()
                        has_captcha = (
                            "unusual traffic" in page_content or
                            "captcha" in page_content or
                            "/sorry/index" in page_content or
                            page.locator("iframe[src*='recaptcha']").count() > 0
                        )
                    except:
                        has_captcha = False

                    if has_captcha:
                        if headless:
                            log_callback("[CAPTCHA] Detected in background. Relaunching in visible mode...")
                            browser.close()
                            headless = False
                            browser = p.chromium.launch(headless=False, channel="msedge")
                            context = browser.new_context(
                                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                            )
                            page = context.new_page()
                            page.goto("https://www.google.com/maps")
                            search_box = page.locator('input#searchboxinput')
                            search_box.wait_for(state="visible", timeout=10000)
                            search_box.fill(search_term)
                            page.keyboard.press("Enter")
                            captcha_wait_start = time.time()
                            continue

                        elapsed = int(time.time() - captcha_wait_start)
                        if elapsed >= max_captcha_wait:
                            log_callback(f"Captcha timeout. Skipping {search_term}.")
                            break
                        log_callback(f"[CAPTCHA DETECTED] Please solve it in the browser... ({elapsed}s)")
                        time.sleep(3)
                        continue

                    # Check for results feed
                    if page.locator('div[role="feed"]').count() > 0:
                        break

                    # Also check for "No results found" message to break loop
                    if "couldn't find" in page_content or "no results" in page_content:
                        break

                    if int(time.time() - captcha_wait_start) > 15:
                        break
                    time.sleep(1)

                try:
                    try:
                        page.wait_for_selector('div[role="feed"]', timeout=5000)
                    except:
                        if "couldn't find" not in page.content().lower():
                            log_callback("No results feed found (possibly no results for this query).")
                        time.sleep(1)
                        continue

                    feed = page.locator('div[role="feed"]')

                    log_callback("Scrolling results...")
                    scroll_count = max(1, config.MAX_SCROLL_COUNT)
                    for _ in range(scroll_count):
                        if state.stopped:
                            break
                        feed.evaluate("node => node.scrollTop += 2000")
                        time.sleep(random.uniform(1.5, 3))

                    items = page.locator('div[role="article"]').all()
                    log_callback(f"Found {len(items)} items.")

                    results_this_search = 0
                    for item in items:
                        if results_this_search >= max_results or state.stopped:
                            break

                        try:
                            name = item.get_attribute("aria-label")
                            if not name:
                                continue

                            name_lower = name.lower().strip()
                            if name_lower in seen_companies:
                                continue
                            seen_companies.add(name_lower)

                            text_content = item.inner_text().split('\n')
                            parsed = parse_raw_data(text_content)

                            # Click item to get website from detail panel
                            website = ""
                            try:
                                item.click()
                                time.sleep(random.uniform(1.5, 2.5))

                                # Look for website link in detail panel
                                # Google Maps uses data-item-id="authority" for website links
                                website_link = page.locator('a[data-item-id="authority"]').first
                                if website_link.count() > 0:
                                    website = website_link.get_attribute("href") or ""
                                else:
                                    # Fallback: look for any link with website icon
                                    website_btn = page.locator('button[data-item-id="authority"]').first
                                    if website_btn.count() > 0:
                                        aria_label = website_btn.get_attribute("aria-label") or ""
                                        if aria_label:
                                            # Extract URL from aria-label like "Open website: example.com"
                                            website = aria_label.replace("Open website:", "").strip()

                                # Also try to get phone from detail panel if not found
                                if not parsed["phone"]:
                                    phone_btn = page.locator('button[data-item-id^="phone"]').first
                                    if phone_btn.count() > 0:
                                        phone_text = phone_btn.get_attribute("aria-label") or ""
                                        phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', phone_text)
                                        if phone_match:
                                            parsed["phone"] = phone_match.group()

                            except Exception as e:
                                log_callback(f"  Detail extraction failed: {e}")

                            lead = {
                                "Company": name,
                                "Website": website or parsed["website"],
                                "Phone": parsed["phone"],
                                "Address": parsed["address"],
                                "Rating": parsed["rating"],
                                "Reviews": parsed["review_count"],
                                "Keyword": base_keyword,
                                "Location": loc,
                                "Raw_Data": " | ".join(text_content[:5]),  # First 5 lines only
                                "Scraped_At": datetime.now().isoformat()
                            }
                            all_leads.append(lead)

                            lead_data = {
                                "company": lead["Company"],
                                "email": "",
                                "phone": lead["Phone"],
                                "website": lead["Website"],
                                "address": lead["Address"],
                                "city": loc,
                                "country": "United States",
                                "source": "google_maps",
                                "source_id": "",
                                "rating": lead["Rating"],
                                "review_count": lead["Reviews"],
                                "keyword": base_keyword,
                                "score": 0,
                                "scraped_at": lead["Scraped_At"],
                            }
                            inserted_id, is_new = db.insert_lead(lead_data)
                            if is_new:
                                inserted_count += 1
                            else:
                                duplicate_count += 1

                            results_this_search += 1
                            log_callback(f"Extracted: {name} | Website: {website or 'N/A'}")

                        except Exception as e:
                            log_callback(f"Extraction error: {e}")

                except Exception as e:
                    log_callback(f"Error processing results: {e}")

                time.sleep(2)

        browser.close()
        log_callback("Browser closed.")
        log_callback(f"DB insert summary: new={inserted_count}, duplicates={duplicate_count}")

        if all_leads:
            df = pd.DataFrame(all_leads)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"data/raw/google_maps_{timestamp}.csv"

            # Ensure directory exists
            os.makedirs("data/raw", exist_ok=True)

            df.to_csv(output_file, index=False)
            log_callback(f"Saved {len(all_leads)} leads to {output_file}")
            return str(output_file)
        else:
            log_callback("No leads found.")
            return None


if __name__ == "__main__":
    scrape_google_maps(["business consulting"], headless=False)
