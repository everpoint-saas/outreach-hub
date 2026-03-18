import sys
import os

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright not installed.")
    sys.exit(1)

def run():
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug", "screenshots")
    os.makedirs(target_dir, exist_ok=True)

    output_path = os.path.join(target_dir, "final_report.png")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
            page = browser.new_page()
            print("Navigating to http://localhost:3000...")
            page.goto("http://localhost:3000")
            page.wait_for_load_state("networkidle")

            print("Looking for 'Final Report'...")
            # Try to find a specific tab or button with text 'Final Report'
            # Using a broad locator to handle potential variations in casing or structure
            try:
                # Prioritize a precise match if it's a tab
                tab = page.get_by_text("Final Report", exact=False)
                if tab.count() > 0:
                    tab.first.click()
                    print("Clicked 'Final Report' tab.")
                    page.wait_for_timeout(2000) # specific wait for tab switch
                else:
                    print("Warning: could not find element with text 'Final Report'. Taking screenshot of current page.")
            except Exception as e:
                print(f"Interaction error: {e}")

            page.screenshot(path=output_path, full_page=True)
            print(f"Screenshot saved to {output_path}")

            browser.close()
        except Exception as e:
            print(f"Browser error: {e}")
            sys.exit(1)

if __name__ == "__main__":
    run()
