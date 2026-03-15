import os
import random
import re
import shutil
import time
from datetime import datetime, timedelta

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

load_dotenv()

# Make streamlit optional (for desktop app that doesn't need it)
try:
    import streamlit as st
except ImportError:
    st = None

try:
    import toml
except ImportError:
    try:
        import tomllib

        toml = tomllib
    except ImportError:
        toml = None


def _load_secrets_toml():
    """
    Load secrets from .streamlit/secrets.toml when running outside Streamlit.
    Returns a dictionary of secrets, or empty dict if file not found.
    """
    secrets = {}
    try:
        secrets_path = os.path.join(
            os.path.dirname(__file__), ".streamlit", "secrets.toml"
        )
        if os.path.exists(secrets_path):
            with open(secrets_path, "r", encoding="utf-8") as f:
                if toml:
                    secrets = toml.load(f)
                else:
                    # Simple fallback: parse as key-value pairs (basic TOML)
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip().strip('"').strip("'")
                            secrets[key] = value
        return secrets
    except Exception:
        return {}


def _get_secret(key, default=""):
    """
    Get secret from Streamlit secrets or secrets.toml file.
    Works both in Streamlit context and when running directly.
    """
    # If streamlit not available, use secrets.toml
    if st is None:
        secrets = _load_secrets_toml()
        return secrets.get(key, default)

    # Try Streamlit secrets first (when running in Streamlit)
    try:
        return st.secrets.get(key, default)
    except (AttributeError, RuntimeError, NameError):
        # Not in Streamlit context, try loading from secrets.toml
        secrets = _load_secrets_toml()
        return secrets.get(key, default)


def _notify_user(message, message_type="error"):
    """
    Safely notify user using Streamlit if available, otherwise use print.
    Also stores logs in st.session_state for persistence across reruns.

    Args:
        message (str): Message to display
        message_type (str): Type of message - "error", "success", "warning", or "info"
    """
    # If streamlit not available, just print
    if st is None:
        print(message)
        return

    try:
        # Store in session_state for persistence
        if "process_logs" not in st.session_state:
            st.session_state.process_logs = []
        st.session_state.process_logs.append({"message": message, "type": message_type})

        if message_type == "error":
            st.error(message)
        elif message_type == "success":
            st.success(message)
        elif message_type == "warning":
            st.warning(message)
        else:
            st.info(message)
    except Exception:
        # Streamlit not available or not in proper context, use print
        print(message)


def get_class_list_from_aca2000(
    aca2000_url=None, cust_num=None, user_id=None, user_pw=None, headless=False
):
    """
    Fetches available class list (names and IDs) from ACA2000.
    Returns the driver alive for reuse with get_students_for_classes().

    Steps:
    1. Login to ACA2000
    2. Navigate to 출석부 (Attendance)
    3. Select latest Saturday date
    4. Extract class names and IDs

    Returns:
        tuple: (class_info_dict, driver)
            - class_info: {"M7 월금": "2246", ...}
            - driver: live WebDriver for reuse (caller must quit when done)
            On error: ({}, None)
    """
    import re

    if not aca2000_url:
        aca2000_url = "https://t.aca2000.co.kr/"

    if not cust_num:
        cust_num = _get_secret("ACA2000_CUST_NUM", os.getenv("ACA2000_CUST_NUM", ""))
    if not user_id:
        user_id = _get_secret("ACA2000_USER_ID", os.getenv("ACA2000_USER_ID", ""))
    if not user_pw:
        user_pw = _get_secret("ACA2000_USER_PW", os.getenv("ACA2000_USER_PW", ""))

    if not all([cust_num, user_id, user_pw]):
        _notify_user(
            "❌ ACA2000 credentials (CUST_NUM, USER_ID, USER_PW) must be set", "error"
        )
        return {}, None

    # Create driver manually (not via context manager, so it stays alive)
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")
    # Use system chromedriver if available (Streamlit Cloud), otherwise use webdriver-manager
    import shutil

    system_chromedriver = shutil.which("chromedriver")
    if system_chromedriver:
        driver = webdriver.Chrome(service=Service(system_chromedriver), options=options)
    else:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), options=options
        )

    # _make_driver_read_only(driver)

    wait = WebDriverWait(driver, 20)

    try:
        # Step 1: Login
        _notify_user("[ACA2000] Step 1: Logging in...", "info")
        driver.get(aca2000_url)

        cust_num_input = wait.until(EC.presence_of_element_located((By.ID, "custNum")))
        driver.execute_script(
            "arguments[0].value = arguments[1];", cust_num_input, cust_num
        )
        user_id_input = wait.until(EC.presence_of_element_located((By.ID, "userID")))
        driver.execute_script(
            "arguments[0].value = arguments[1];", user_id_input, user_id
        )
        user_pw_input = wait.until(EC.presence_of_element_located((By.ID, "userPW")))
        driver.execute_script(
            "arguments[0].value = arguments[1];", user_pw_input, user_pw
        )

        try:
            login_btn = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[contains(text(), '로그인')] | //input[@value='로그인'] | //button[@type='submit'] | //input[@type='submit']",
                    )
                )
            )
            login_btn.click()
            _notify_user("[ACA2000] Login button clicked", "info")
        except Exception:
            try:
                user_pw_input.submit()
            except Exception:
                from selenium.webdriver.common.keys import Keys

                user_pw_input.send_keys(Keys.RETURN)

        # Check for login errors
        current_url = driver.current_url
        _notify_user(
            f"[ACA2000] Current URL after login attempt: {current_url}", "info"
        )
        if "/Account/Login" in current_url or "ReturnUrl" in current_url:
            _notify_user(
                "[ACA2000] ⚠️ Still on login page - checking for errors...", "warning"
            )
            try:
                error_elements = driver.find_elements(
                    By.CSS_SELECTOR,
                    ".error, .alert, .warning, [class*='error'], [class*='alert']",
                )
                if error_elements:
                    error_text = " ".join(
                        [elem.text for elem in error_elements if elem.text]
                    )
                    _notify_user(
                        f"[ACA2000] ⚠️ Login error detected: {error_text}", "error"
                    )
            except Exception:
                pass

        # Wait for redirect to /Attend
        try:
            wait_redirect = WebDriverWait(driver, 10)
            wait_redirect.until(
                lambda d: "/Attend" in d.current_url
                and "/Account/Login" not in d.current_url
            )
            _notify_user("[ACA2000] ✅ Login successful", "success")
        except Exception:
            current_url = driver.current_url
            if "/Account/Login" in current_url or "ReturnUrl" in current_url:
                _notify_user("[ACA2000] ❌ Login failed", "error")
                driver.quit()
                return {}, None
            else:
                try:
                    driver.get(f"{aca2000_url.rstrip('/')}/Attend")
                    wait.until(
                        lambda d: "/Attend" in d.current_url
                        and "/Account/Login" not in d.current_url
                    )
                except Exception:
                    _notify_user("[ACA2000] ❌ Could not navigate to /Attend", "error")
                    driver.quit()
                    return {}, None

        # Step 2: Navigate to 출석부
        _notify_user("[ACA2000] Step 2: Navigating to 출석부...", "info")
        try:
            attend_link = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.CSS_SELECTOR,
                        "a[href*='/Attend'], a[data-langnum='m3'], li[name='Attend'] a, .am3",
                    )
                )
            )
            attend_link.click()
        except Exception:
            if "/Attend" not in driver.current_url:
                driver.get(f"{aca2000_url.rstrip('/')}/Attend")

        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".attendL, .class-list, #반목록, .반목록")
            )
        )
        _notify_user("[ACA2000] ✅ Navigated to 출석부", "success")
        time.sleep(5)

        # Step 3: Select latest Saturday date
        _notify_user("[ACA2000] Step 3: Selecting latest Saturday date...", "info")
        today = datetime.now()
        days_since_saturday = (today.weekday() - 5) % 7
        if days_since_saturday == 0 and today.weekday() != 5:
            days_since_saturday = 7
        latest_saturday = today - timedelta(days=days_since_saturday)
        target_date = latest_saturday.strftime("%Y-%m-%d")
        target_year = latest_saturday.year
        target_month = latest_saturday.month
        target_day = latest_saturday.day
        _notify_user(
            f"[ACA2000] Target date (the latest Saturday): {target_date}", "info"
        )

        try:
            # Try calendar popup
            try:
                date_input = driver.find_element(By.ID, "iDate")
                date_input.click()
                time.sleep(1)
            except Exception:
                pass
            try:
                calendar_btn = driver.find_element(
                    By.CSS_SELECTOR, "img[src*='btn_calendar'], img[src*='calendar']"
                )
                driver.execute_script("arguments[0].click();", calendar_btn)
                time.sleep(1)
            except Exception:
                pass

            calendar_opened = False
            try:
                wait.until(
                    EC.visibility_of_element_located(
                        (
                            By.CSS_SELECTOR,
                            ".datepicker-dropdown, div.datepicker[style*='display: block']",
                        )
                    )
                )
                calendar_opened = True
            except Exception:
                pass

            if calendar_opened:
                # Navigate calendar to correct month
                for _ in range(12):
                    try:
                        header = driver.find_element(
                            By.CSS_SELECTOR, "th.datepicker-switch"
                        ).text.strip()
                        match = re.search(r"(\d{4})년\s*(\d{1,2})월", header)
                        if match:
                            cy, cm = int(match.group(1)), int(match.group(2))
                            if cy == target_year and cm == target_month:
                                break
                            elif (cy < target_year) or (
                                cy == target_year and cm < target_month
                            ):
                                driver.find_element(By.CSS_SELECTOR, "th.next").click()
                            else:
                                driver.find_element(By.CSS_SELECTOR, "th.prev").click()
                            time.sleep(0.5)
                        else:
                            break
                    except Exception:
                        break
                # Click target day (exclude old/new month days)
                try:
                    date_cell = wait.until(
                        EC.element_to_be_clickable(
                            (
                                By.XPATH,
                                f"//td[contains(@class, 'day') and not(contains(@class, 'disabled')) and not(contains(@class, 'old')) and not(contains(@class, 'new'))]//div[text()='{target_day}']",
                            )
                        )
                    )
                    date_cell.click()
                    time.sleep(2)
                    _notify_user(
                        f"[ACA2000] ✅ Selected date: {target_date}", "success"
                    )
                except Exception as e:
                    _notify_user(
                        f"[ACA2000] ⚠️ Could not select date: {type(e).__name__}",
                        "warning",
                    )
            else:
                # Arrow button navigation
                for _ in range(30):
                    try:
                        current_date_str = (
                            driver.find_element(By.ID, "iDate").get_attribute("value")
                            or ""
                        ).strip()
                        if current_date_str == target_date:
                            _notify_user(
                                f"[ACA2000] ✅ Reached target date: {target_date}",
                                "success",
                            )
                            break
                        current = datetime.strptime(current_date_str, "%Y-%m-%d")
                        target = datetime.strptime(target_date, "%Y-%m-%d")
                        if current < target:
                            driver.find_element(
                                By.XPATH,
                                "//a[contains(@onclick, 'nextDay')] | //a[contains(., '▶')]",
                            ).click()
                        else:
                            driver.find_element(
                                By.XPATH,
                                "//a[contains(@onclick, 'prevDay')] | //a[contains(., '◀')]",
                            ).click()
                        time.sleep(0.5)
                    except Exception:
                        break
        except Exception as e:
            _notify_user(f"[ACA2000] ⚠️ Could not select date: {e}", "warning")

        # Step 4: Get class list
        _notify_user("[ACA2000] Step 4: Fetching class list...", "info")
        class_info = {}
        try:
            wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        ".반목록, #반목록, .class-list, .depth1, li.depth1",
                    )
                )
            )
            class_elements = driver.find_elements(
                By.CSS_SELECTOR, "a[onclick*='selectClass']"
            )
            for elem in class_elements:
                try:
                    class_name = elem.text.strip()
                    onclick_attr = elem.get_attribute("onclick")
                    if onclick_attr and "selectClass" in onclick_attr:
                        match = re.search(r"selectClass\((\d+)\)", onclick_attr)
                        if match:
                            class_id = match.group(1)
                            if class_name and class_name not in class_info:
                                class_info[class_name] = class_id
                except Exception:
                    continue
            _notify_user(
                f"[ACA2000] ✅ Found {len(class_info)} classes from date {target_date}",
                "success",
            )
        except Exception as e:
            _notify_user(f"[ACA2000] ⚠️ Could not find class list: {e}", "warning")

        if not class_info:
            driver.quit()
            return {}, None

        # Return class list and keep driver alive
        return class_info, driver

    except Exception as e:
        _notify_user(f"[ACA2000] ❌ Error: {e}", "error")
        driver.quit()
        return {}, None


def get_students_for_classes(driver, class_ids):
    """
    Fetches student lists for selected classes using an existing driver.
    Quits the driver when done.

    Args:
        driver: Live WebDriver from get_class_list_from_aca2000()
        class_ids: {class_name: class_id} for selected classes only

    Returns:
        dict: {class_name: [student_names]}
    """
    all_students = {}
    wait = WebDriverWait(driver, 20)

    try:
        for class_name, class_id in class_ids.items():
            try:
                _notify_user(
                    f"[ACA2000] Processing class: {class_name} (ID: {class_id})...",
                    "info",
                )
                driver.execute_script(f"selectClass({class_id});")
                time.sleep(2)

                try:
                    wait.until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "span.name[onclick*='showDetail']")
                        )
                    )
                    student_name_elements = driver.find_elements(
                        By.CSS_SELECTOR, "span.name[onclick*='showDetail']"
                    )

                    students = []
                    for student_elem in student_name_elements:
                        student_name = student_elem.text.strip()
                        if not student_name:
                            continue
                        try:
                            parent_row = student_elem.find_element(
                                By.XPATH,
                                "./ancestor::tr | ./ancestor::div[contains(@class, 'row')]",
                            )
                            attended_buttons = parent_row.find_elements(
                                By.CSS_SELECTOR,
                                "button.att_btn.on01s[value='출석'], button.on01s[value='출석']",
                            )
                            if attended_buttons:
                                if student_name not in students:
                                    students.append(student_name)
                                    _notify_user(
                                        f"[ACA2000]   ✓ {student_name} - 출석", "info"
                                    )
                            else:
                                _notify_user(
                                    f"[ACA2000]   ✗ {student_name} - not attended",
                                    "info",
                                )
                        except Exception:
                            continue

                    all_students[class_name] = students
                    _notify_user(
                        f"[ACA2000] ✅ Found {len(students)} attended students in {class_name}",
                        "success",
                    )

                except Exception as e:
                    _notify_user(
                        f"[ACA2000] ⚠️ Error extracting students for {class_name}: {e}",
                        "warning",
                    )
                    all_students[class_name] = []

            except Exception as e:
                _notify_user(
                    f"[ACA2000] ⚠️ Error processing class {class_name}: {e}", "warning"
                )
                all_students[class_name] = []

        _notify_user(
            f"[ACA2000] ✅ Completed! Processed {len(all_students)} classes", "success"
        )

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return all_students


def find_missing_students(student_dict, emails):
    """
    Compare ACA2000 student names against fetched email data.

    Args:
        student_dict: {class_name: [student_entry, ...]} from get_students_from_aca2000()
        emails: list of dicts with keys: sender, subject, content, attachments

    Returns:
        dict: {class_name: {'matched': [(student_entry, email_subject), ...],
                            'missing': [student_entry, ...]}}
    """
    import re

    STOP_WORDS = {
        "대기",
        "휴강",
        "신규",
        "월",
        "화",
        "수",
        "목",
        "금",
        "토",
        "일",
        "월금",
        "화목",
    }

    def extract_korean_name(entry):
        matches = re.findall(r"[가-힣]+", entry)
        names = [m for m in matches if 2 <= len(m) <= 3 and m not in STOP_WORDS]
        return names[0] if names else None

    # Build searchable text per email
    email_texts = []
    for e in emails:
        combined = f"{e['subject']} {e['content']} {' '.join(e['attachments'])}"
        email_texts.append((combined, e["subject"]))

    results = {}
    for class_name, students in student_dict.items():
        matched = []
        missing = []
        for student_entry in students:
            name = extract_korean_name(student_entry)
            if not name:
                missing.append(student_entry)
                continue
            found_subject = None
            for text, subject in email_texts:
                if name in text:
                    found_subject = subject
                    break
            if found_subject:
                matched.append((student_entry, found_subject))
            else:
                missing.append(student_entry)
        results[class_name] = {"matched": matched, "missing": missing}

    return results


def fetch_naver_email(
    headless=False, naver_id=None, naver_passkey=None, start_date=None, end_date=None
):
    """
    Fetches Naver email using Selenium WebDriver.
    Parameters:
        headless (bool): Whether to run the browser in headless mode.
        naver_id (str): Naver login ID.
        naver_passkey (str): Naver login password or app password.
        start_date (datetime.date): Start date for email filtering (inclusive). Defaults to 7 days ago.
        end_date (datetime.date): End date for email filtering (inclusive). Defaults to today.
    Returns:
        list: List of dicts with sender, subject, content, and attachments from recent emails
              Example: [{"sender": "example@naver.com", "subject": "Hello", "content": "...", "attachments": ["a.pdf"]}, ...]
    """

    email_list = []

    def _extract_attachment_names(driver):
        names = set()

        def _add_name(value):
            if not value:
                return
            text = value.strip()
            if not text:
                return
            text = text.splitlines()[0].strip()
            if text:
                names.add(text)

        container_selectors = [
            "div.mail_view_attachment_area",
            "div.mail_view_attachment",
            "div.attachment",
            "div.file_area",
            "div.file_attachments",
            "div.file_attachments_inner",
            "ul.mail_view_attachment_list",
            "ul.attach_list",
            "ul.file_list",
            "li.file_item",
        ]

        # Note: span.text and span.file_extension are handled separately
        # in the combined logic below, so they're not included here
        name_selectors = [
            "span.file_name",
            "em.file_name",
            "strong.file_name",
            "span.filename",
            "a.file_download",
            "a.button_download",
            "a.link_download",
            "a[download]",
        ]

        elements = []
        for selector in container_selectors:
            try:
                elements.extend(driver.find_elements(By.CSS_SELECTOR, selector))
            except Exception:
                continue

        if elements:
            for container in elements:
                try:
                    for item in container.find_elements(
                        By.CSS_SELECTOR, "li.file_item"
                    ):
                        base = None
                        ext = None
                        try:
                            base_elem = item.find_element(
                                By.CSS_SELECTOR, "strong.file_title span.text"
                            )
                            base = base_elem.text.strip()
                        except Exception:
                            base = None
                        try:
                            ext_elem = item.find_element(
                                By.CSS_SELECTOR, "strong.file_title span.file_extension"
                            )
                            ext = ext_elem.text.strip()
                        except Exception:
                            ext = None

                        if base and ext:
                            _add_name(f"{base}{ext}")
                        elif base:
                            _add_name(base)
                except Exception:
                    pass

                for selector in name_selectors:
                    try:
                        for elem in container.find_elements(By.CSS_SELECTOR, selector):
                            _add_name(elem.text)
                            _add_name(elem.get_attribute("title"))
                            _add_name(elem.get_attribute("download"))
                            _add_name(elem.get_attribute("aria-label"))
                            _add_name(elem.get_attribute("data-file-name"))
                            _add_name(elem.get_attribute("data-filename"))
                            _add_name(elem.get_attribute("data-name"))
                    except Exception:
                        continue
        else:
            for selector in name_selectors:
                try:
                    for elem in driver.find_elements(By.CSS_SELECTOR, selector):
                        _add_name(elem.text)
                        _add_name(elem.get_attribute("title"))
                        _add_name(elem.get_attribute("download"))
                        _add_name(elem.get_attribute("aria-label"))
                        _add_name(elem.get_attribute("data-file-name"))
                        _add_name(elem.get_attribute("data-filename"))
                        _add_name(elem.get_attribute("data-name"))
                except Exception:
                    continue

        return sorted(names)

    # Step 1: Login to Naver using the reusable function
    driver = login_naver_selenium(
        headless=headless, naver_id=naver_id, naver_passkey=naver_passkey
    )

    if not driver:
        raise RuntimeError("Naver login failed. Check your ID and password.")

    wait = WebDriverWait(driver, 10)

    try:
        # Add random delay to appear more human-like
        time.sleep(random.uniform(1.5, 2.0))

        # Step 2: Navigate to Naver Mail
        _notify_user("[Naver] Navigating to mail...", "info")
        driver.get("https://mail.naver.com/")

        # Random delay after navigation
        time.sleep(random.uniform(1.5, 2.0))

        # Wait for mail list to load (using actual Naver Mail structure)
        wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "ol.mail_list, #mail_list_wrap, li.mail_item")
            )
        )

        # Ensure we're on '전체메일' (some accounts default to '받은메일함')
        try:
            all_mail_link = driver.find_element(
                By.CSS_SELECTOR, "a.mailbox_label[title='전체메일']"
            )
            all_mail_link.click()
            time.sleep(random.uniform(1.5, 2.5))  # to avoid bot detection
            wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "ol.mail_list, #mail_list_wrap, li.mail_item")
                )
            )
        except Exception:
            _notify_user(
                "[Naver] ⚠️ Could not navigate to '전체메일', using current view",
                "warning",
            )

        # Add another small random delay before extracting
        time.sleep(random.uniform(0.5, 1.5))

        # Step 3: Extract email subjects (only unread emails via CSS selector)
        _notify_user("[Naver] Fetching emails...", "info")

        # Keep track of all processed email IDs across pages
        processed_mail_ids = []

        # Date range for filtering emails
        if start_date is None or end_date is None:
            start_date = (datetime.now() - timedelta(days=7)).date()
            end_date = datetime.now().date()
        _notify_user(f"[Naver] Fetching emails from {start_date} to {end_date}", "info")
        date_limit_reached = False
        page_num = 1

        while True:
            # Get unread mail items on current page
            mail_items = driver.find_elements(
                By.CSS_SELECTOR, "li.mail_item:not(.read)"
            )

            if not mail_items:
                if page_num == 1:
                    _notify_user("[Naver] ⚠️ No unread mail items found", "warning")
                break

            _notify_user(
                f"[Naver] Page {page_num}: Found {len(mail_items)} unread mail items",
                "info",
            )

            page_mail_ids = []

            for mail_item in mail_items:
                try:
                    # Check email date — skip if older than date_limit
                    # Naver Mail date formats:
                    #   Today: "오후 03:32" (time only, no dot)
                    #   Past days: "01.30 16:25" (MM.DD HH:MM)
                    try:
                        date_elem = mail_item.find_element(
                            By.CSS_SELECTOR, "div.mail_date_wrap span.mail_date"
                        )
                        date_text = (
                            date_elem.text
                            or date_elem.get_attribute("textContent")
                            or ""
                        ).strip()
                        if re.search(r"\d{2}\.\d{2}", date_text):
                            # "MM.DD HH:MM" format (e.g. "02.03 14:32")
                            date_part = re.search(r"(\d{2}\.\d{2})", date_text).group(1)
                            mail_date = datetime.strptime(
                                f"{datetime.now().year}.{date_part}", "%Y.%m.%d"
                            ).date()
                        else:
                            # Time only (e.g. "오후 03:32") means today
                            mail_date = datetime.now().date()
                        if mail_date < start_date:
                            _notify_user(
                                f"[Naver] Reached emails older than start date ({date_text}), stopping",
                                "info",
                            )
                            date_limit_reached = True
                            break
                        if mail_date > end_date:
                            continue  # Skip emails newer than end_date
                    except Exception:
                        pass  # If date extraction fails, process the email anyway

                    # Get the mail ID from the class attribute (e.g., "mail-25317")
                    mail_id = None
                    class_attr = mail_item.get_attribute("class")
                    if class_attr:
                        for cls in class_attr.split():
                            if cls.startswith("mail-"):
                                mail_id = cls
                                break
                    # Extract sender (from actual Naver Mail HTML structure)
                    sender = None
                    try:
                        # First try button.button_sender with title attribute
                        sender_elem = mail_item.find_element(
                            By.CSS_SELECTOR, "button.button_sender"
                        )
                        if sender_elem:
                            # Get sender from title attribute (contains email)
                            sender = sender_elem.get_attribute("title")
                            if sender:
                                sender = sender.strip().strip(
                                    "<>"
                                )  # Remove < > brackets if present
                    except Exception:
                        # Fallback to other selectors
                        sender_selectors = [
                            "div.mail_sender",
                            "button.toggle_conversation_mail",
                            "span.mail_sender",
                            "[class*='sender']",
                        ]
                        for selector in sender_selectors:
                            try:
                                sender_elem = mail_item.find_element(
                                    By.CSS_SELECTOR, selector
                                )
                                if sender_elem and sender_elem.text.strip():
                                    sender = sender_elem.text.strip()
                                    # Clean up sender text (remove date if present)
                                    sender_lines = [
                                        line.strip()
                                        for line in sender.split("\n")
                                        if line.strip()
                                    ]
                                    if sender_lines:
                                        # Take first line that doesn't look like a date (format: 01-21)
                                        for line in sender_lines:
                                            if (
                                                not line.replace("-", "")
                                                .replace(".", "")
                                                .isdigit()
                                            ):
                                                sender = line
                                                break
                                    break
                            except Exception:
                                continue

                    # Extract subject
                    subject = None
                    subject_selectors = [
                        "div.mail_title span.text",  # Actual subject text element
                        "a.mail_title_link span.text",  # Alternative path to subject
                        "div.mail_title",
                        "span.mail_title",
                        "strong.mail_title",
                        "div.mail_inner",
                        "a.mail_subject",
                        "span.subject",
                        "[class*='subject']",
                        "[class*='title']",
                    ]

                    for selector in subject_selectors:
                        try:
                            subject_elem = mail_item.find_element(
                                By.CSS_SELECTOR, selector
                            )
                            if subject_elem and subject_elem.text.strip():
                                subject = subject_elem.text.strip()
                                # Split by newlines and take first non-empty line
                                subject_lines = [
                                    line.strip()
                                    for line in subject.split("\n")
                                    if line.strip()
                                ]
                                if subject_lines:
                                    subject = subject_lines[0]
                                break
                        except Exception:
                            continue

                    # Extract email content by clicking and reading
                    content = None
                    attachments = []
                    try:
                        # Click on the email title link to open the email
                        title_link = mail_item.find_element(
                            By.CSS_SELECTOR, "a.mail_title_link"
                        )
                        title_link.click()

                        # Wait for email content to load
                        time.sleep(random.uniform(1.0, 2.0))
                        wait.until(
                            EC.presence_of_element_located(
                                (
                                    By.CSS_SELECTOR,
                                    "div.mail_view_contents_inner, div.mail_view_contents",
                                )
                            )
                        )

                        # Extract content
                        content_selectors = [
                            "div.mail_view_contents_inner",
                            "div.mail_view_contents",
                        ]
                        for content_selector in content_selectors:
                            try:
                                content_elem = driver.find_element(
                                    By.CSS_SELECTOR, content_selector
                                )
                                if content_elem and content_elem.text.strip():
                                    content = content_elem.text.strip()
                                    break
                            except Exception:
                                continue

                        attachments = _extract_attachment_names(driver)

                        # Go back to mail list
                        driver.back()
                        time.sleep(random.uniform(1.0, 2.0))

                        # Wait for mail list to reload
                        wait.until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "ul.mail_list, li.mail_item")
                            )
                        )

                    except Exception as e:
                        _notify_user(
                            f"[Naver] ⚠️ Could not fetch content: {type(e).__name__}",
                            "warning",
                        )
                        # Try to go back if we're stuck
                        try:
                            driver.back()
                            time.sleep(1.0)
                        except Exception:
                            pass

                    # Track mail_id for unread revert (email was opened regardless of content)
                    if mail_id:
                        page_mail_ids.append(mail_id)

                    # Add to list if we have subject, content, or attachments
                    if subject or content or attachments:
                        email_data = {
                            "sender": sender if sender else "Unknown",
                            "subject": subject if subject else "(no subject)",
                            "content": content if content else "",
                            "attachments": attachments,
                        }
                        # Check for duplicates based on sender+subject combination
                        is_duplicate = any(
                            e["sender"] == email_data["sender"]
                            and e["subject"] == email_data["subject"]
                            for e in email_list
                        )
                        if not is_duplicate:
                            email_list.append(email_data)
                            _notify_user(
                                f"[Naver]   • {sender if sender else 'Unknown'}: {subject if subject else '(no subject)'}",
                                "info",
                            )

                except Exception as e:
                    _notify_user(
                        f"[Naver] ⚠️ Could not extract email: {type(e).__name__}",
                        "warning",
                    )
                    continue

            # Mark this page's processed emails as unread before moving on
            if page_mail_ids:
                _notify_user(
                    f"[Naver] Selecting {len(page_mail_ids)} emails on page {page_num}...",
                    "info",
                )
                checked_count = 0
                for mail_id in page_mail_ids:
                    try:
                        mail_item = driver.find_element(
                            By.CSS_SELECTOR, f"li.{mail_id}"
                        )
                        checkbox = mail_item.find_element(
                            By.CSS_SELECTOR, "label[role='checkbox']"
                        )
                        if checkbox.get_attribute("aria-checked") != "true":
                            checkbox.click()
                            time.sleep(random.uniform(0.2, 0.4))
                        checked_count += 1
                    except Exception as e:
                        _notify_user(
                            f"[Naver] ⚠️ Could not check {mail_id}: {type(e).__name__}",
                            "warning",
                        )

                if checked_count > 0:
                    _notify_user(
                        f"[Naver] Marking {checked_count} emails as unread...", "info"
                    )
                    try:
                        unread_button = wait.until(
                            EC.element_to_be_clickable(
                                (
                                    By.XPATH,
                                    "//button[contains(@class, 'button_task') and normalize-space(.)='안읽음']",
                                )
                            )
                        )
                        unread_button.click()
                        time.sleep(random.uniform(0.5, 1.0))
                        _notify_user("[Naver] ✅ Marked emails as unread", "success")
                    except Exception as e:
                        _notify_user(
                            f"[Naver] ⚠️ Could not mark as unread: {type(e).__name__}",
                            "warning",
                        )

                processed_mail_ids.extend(page_mail_ids)

            # Stop if date limit was reached
            if date_limit_reached:
                break

            # Try to go to the next page
            try:
                next_btn = driver.find_element(
                    By.CSS_SELECTOR, "button.button_next#next-page"
                )
                if next_btn.get_attribute("disabled") is not None:
                    _notify_user(f"[Naver] Reached last page (page {page_num})", "info")
                    break
                next_btn.click()
                page_num += 1
                time.sleep(random.uniform(1.5, 2.5))
                wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "ol.mail_list, li.mail_item")
                    )
                )
            except Exception:
                break

        # print for debugging
        import pprint

        print(f"processed_mail_ids: {processed_mail_ids}")
        print("email_list:")
        pprint.pprint(email_list)

        _notify_user(f"[Naver] ✅ Fetched {len(email_list)} emails", "success")

    except Exception as e:
        _notify_user(f"[Naver] ❌ Error: {e}", "error")
        driver.save_screenshot("naver_email_error.png")
    finally:
        driver.quit()

    return email_list


def login_naver_selenium(headless=False, naver_id=None, naver_passkey=None):
    """
    Logs into Naver using Selenium WebDriver and returns the driver.

    Parameters:
        headless (bool): Whether to run the browser in headless mode.
        naver_id (str): Naver login ID.
        naver_passkey (str): Naver login password or app password.

    Returns:
        webdriver: Logged-in Chrome WebDriver instance, or None if login failed.
    """

    _id = naver_id if naver_id else _get_secret("NAVER_ID", os.getenv("NAVER_ID"))
    _pw = (
        naver_passkey
        if naver_passkey
        else _get_secret("NAVER_PW", os.getenv("NAVER_PW"))
    )

    options = Options()
    if headless:
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # Use system chromedriver if available (Streamlit Cloud), otherwise default
    system_chromedriver = shutil.which("chromedriver")
    if system_chromedriver:
        from selenium.webdriver.chrome.service import Service

        driver = webdriver.Chrome(service=Service(system_chromedriver), options=options)
    else:
        driver = webdriver.Chrome(options=options)

    try:
        _notify_user("[Naver] Step 1: Opening login page...", "info")
        driver.get("https://nid.naver.com/nidlogin.login")
        time.sleep(2)

        _notify_user("[Naver] Step 2: Entering credentials...", "info")
        # Simple JS injection - same approach as working test_naver_login.py
        driver.execute_script(f"document.getElementsByName('id')[0].value='{_id}'")
        driver.execute_script(f"document.getElementsByName('pw')[0].value='{_pw}'")

        # Click login button
        _notify_user("[Naver] Step 3: Clicking login button...", "info")
        driver.find_element(By.ID, "log.login").click()
        time.sleep(3)

        _notify_user("[Naver] Step 4: Waiting for login to complete...", "info")
        # Wait for login to complete (longer timeout for 2FA verification)
        WebDriverWait(driver, 60).until(
            lambda d: "nid.naver.com/nidlogin.login" not in d.current_url
        )

        _notify_user("[Naver] ✅ Login successful", "success")
        return driver  # Return the logged-in driver

    except Exception as e:
        import traceback

        _notify_user(f"[Naver] ❌ Login failed: {e}", "error")
        _notify_user(f"[Naver] Current URL: {driver.current_url}", "error")
        _notify_user(f"[Naver] Traceback: {traceback.format_exc()}", "error")
        try:
            driver.save_screenshot("naver_login_error.png")
        except Exception:
            pass
        driver.quit()
        return None
