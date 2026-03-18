import sys
import os
import time

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: playwright not installed.")
    sys.exit(1)

def run():
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug", "screenshots")
    os.makedirs(target_dir, exist_ok=True)

    output_path = os.path.join(target_dir, "final_report.png")

    print("Launching browser...")
    with sync_playwright() as p:
        # headless=False로 설정하여 브라우저가 뜨는 것을 볼 수 있게 함
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        try:
            print("Navigating to http://localhost:3000...")
            page.goto("http://localhost:3000", timeout=30000)

            # 페이지 로드 대기 (네트워크 유휴 상태까지)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except:
                print("Network idle timeout, proceeding anyway...")

            print("Looking for 'Final Report'...")
            # 'Final Report' 텍스트를 가진 요소 찾기
            # 대소문자 무시하고 텍스트 포함 여부 확인
            try:
                # 탭이나 버튼으로 클릭 가능한 요소 찾기 시도
                final_report_loc = page.get_by_text("Final Report", exact=False).first
                if final_report_loc.is_visible():
                    final_report_loc.click()
                    print("Clicked 'Final Report'.")
                    time.sleep(2) # 탭 전환 대기
                else:
                    print("'Final Report' text not visible. Taking screenshot of current view.")
            except Exception as e:
                print(f"Navigation error (continuing to screenshot): {e}")

            page.screenshot(path=output_path, full_page=True)
            print(f"Screenshot saved to {output_path}")

            time.sleep(1) # 잠시 대기
            browser.close()

        except Exception as e:
            print(f"Browser interaction failed: {e}")
            browser.close()
            sys.exit(1)

if __name__ == "__main__":
    run()
