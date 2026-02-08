# import smtplib
from email.message import EmailMessage
import streamlit as st

import smtplib
import ssl
    
from imap_tools import MailBox, AND
from datetime import datetime, timedelta
from email.mime.text import MIMEText

import os
from dotenv import load_dotenv
try:
    import toml
except ImportError:
    # Fallback: try tomllib (Python 3.11+) or use simple parsing
    try:
        import tomllib
        toml = tomllib
    except ImportError:
        toml = None
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.chrome.options import Options
import random

from selenium_stealth import stealth

from PyKakao import Message  # Import PyKakao

import time
from contextlib import contextmanager

def _load_secrets_toml():
    """
    Load secrets from .streamlit/secrets.toml when running outside Streamlit.
    Returns a dictionary of secrets, or empty dict if file not found.
    """
    secrets = {}
    try:
        secrets_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
        if os.path.exists(secrets_path):
            with open(secrets_path, 'r', encoding='utf-8') as f:
                if toml:
                    secrets = toml.load(f)
                else:
                    # Simple fallback: parse as key-value pairs (basic TOML)
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '=' in line:
                            key, value = line.split('=', 1)
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

def _make_driver_read_only(driver):
    """
    Inject JavaScript to make the page read-only using a global approach.
    Intercepts ALL click events and form submissions, then allows only navigation/reading operations.
    Much simpler than manually disabling specific buttons.
    """
    read_only_script = """
    (function() {
        // Define what's allowed (navigation/reading operations)
        const allowedOperations = {
            // Navigation links (href attributes)
            isNavigationLink: function(element) {
                return element.tagName === 'A' && element.href && 
                       (element.href.startsWith('http') || element.href.startsWith('#') || element.href.startsWith('/'));
            },
            // Date/calendar selectors (for selecting dates)
            isDateSelector: function(element) {
                return element.type === 'date' || 
                       element.id && (element.id.includes('date') || element.id.includes('calendar')) ||
                       element.className && (element.className.includes('date') || element.className.includes('calendar'));
            },
            // Search/filter inputs (for filtering data)
            isSearchFilter: function(element) {
                return element.type === 'search' ||
                       element.id && (element.id.includes('search') || element.id.includes('filter')) ||
                       element.className && (element.className.includes('search') || element.className.includes('filter'));
            },
            // Class selection links (for navigating between classes)
            isClassSelector: function(element) {
                return element.onclick && element.onclick.toString().includes('selectClass') ||
                       element.getAttribute('onclick') && element.getAttribute('onclick').includes('selectClass') ||
                       (element.tagName === 'A' && element.textContent && 
                        (element.textContent.match(/^[A-Z]\\d+/) || element.className.includes('class')));
            }
        };
        
        // Global click interceptor - blocks ALL clicks except allowed ones
        document.addEventListener('click', function(e) {
            const target = e.target;
            const element = target.closest('button, a, input[type="submit"], input[type="button"]') || target;
            
            // Allow navigation links
            if (allowedOperations.isNavigationLink(element)) {
                return true;
            }
            
            // Allow class selection (for navigating between classes)
            if (allowedOperations.isClassSelector(element)) {
                return true;
            }
            
            // Block everything else (buttons, form submissions, etc.)
            // This is a global block - no need to list specific button types
            if (element.tagName === 'BUTTON' || 
                element.type === 'submit' || 
                element.type === 'button' ||
                element.onclick ||
                element.getAttribute('onclick')) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                return false;
            }
        }, true); // Use capture phase to intercept early
        
        // Global form submission blocker
        document.addEventListener('submit', function(e) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            return false;
        }, true);
        
        // Make all input fields read-only (except allowed ones)
        function makeInputsReadOnly() {
            const inputs = document.querySelectorAll('input[type="text"], input[type="number"], textarea');
            inputs.forEach(input => {
                if (!allowedOperations.isDateSelector(input) && 
                    !allowedOperations.isSearchFilter(input)) {
                    input.readOnly = true;
                    input.style.backgroundColor = '#f5f5f5';
                }
            });
        }
        
        // Apply to existing inputs
        makeInputsReadOnly();
        
        // Use MutationObserver to handle dynamically added inputs
        const observer = new MutationObserver(function(mutations) {
            makeInputsReadOnly();
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        console.log('Read-only mode activated - global protection enabled');
    })();
    """
    try:
        driver.execute_script(read_only_script)
    except Exception:
        pass  # Ignore if script fails

@contextmanager
def get_driver_context(headless=False, stealth=False, read_only=True):
    """
    Context manager for WebDriver that ensures proper cleanup.
    
    Usage:
        with get_driver_context(headless=True) as driver:
            driver.get("https://example.com")
            # driver is automatically closed when exiting the context
    
    Args:
        headless (bool): Whether to run in headless mode
        stealth (bool): Whether to use stealth mode (for headless)
        read_only (bool): Whether to enable read-only mode (prevents modifications, default: True)
    
    Yields:
        webdriver.Chrome: Configured Chrome WebDriver
    """
    driver = None
    try:
        if headless:
            if stealth:
                driver = get_headless_stealth_driver()
            else:
                options = webdriver.ChromeOptions()
                options.add_argument("--headless=new")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--disable-gpu")
                options.add_argument("--disable-software-rasterizer")
                options.add_argument("--disable-extensions")
                options.add_argument("--disable-background-timer-throttling")
                options.add_argument("--disable-backgrounding-occluded-windows")
                options.add_argument("--disable-renderer-backgrounding")
                options.add_argument("--disable-features=TranslateUI")
                options.add_argument("--disable-ipc-flooding-protection")
                driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=options
                )
        else:
            options = webdriver.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--disable-features=TranslateUI")
            options.add_argument("--disable-ipc-flooding-protection")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=options
            )
        
        # Enable read-only mode if requested (default: True)
        if read_only:
            _make_driver_read_only(driver)
        
        yield driver
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass  # Ignore errors during cleanup

def get_all_senders_clean(user_id, user_pw): # Add parameters here
    """
    Fetches unique email senders from all folders in the Naver mailbox,
    excluding Trash, Spam, and Drafts, for emails received in the last 7 days.
    Parameters:
        user_id (str): Naver email ID (without @naver.com).
        user_pw (str): Naver email password or app password.
    Returns:
        set: A set of unique email senders.
    """
    all_senders = set()
    date_limit = (datetime.now() - timedelta(days=7)).date()

    # Use the passed-in ID and PW
    with MailBox('imap.naver.com').login(user_id, user_pw) as mailbox:
        for folder in mailbox.folder.list():
            if any(skip in folder.name.upper() for skip in ["TRASH", "SPAM", "DRAFTS"]):
                continue
            
            mailbox.folder.set(folder.name)
            # Use gte (Greater Than or Equal)
            messages = mailbox.fetch(AND(date_gte=date_limit))

            for msg in messages:
                if msg.from_:
                    all_senders.add(msg.from_)
    
    return all_senders


def send_naver_report(send_email_id, user_app_pw, receive_email_id, text):
    """
    Sends an email report via Naver's SMTP server.
    Parameters:
        send_email_id (str): Naver email ID (without @naver.com).
        user_app_pw (str): Naver email app password.
        receive_email (str): Recipient's full Naver email address.
        text (str): The content of the email report.
    Returns:
        bool: True if email sent successfully, False otherwise.
        """
    smtp_name = "smtp.naver.com"
    smtp_port = 587

    send_email = f"{send_email_id}@naver.com"
    receive_email = f"{receive_email_id}@naver.com"
    
    try:
        # 1. Create the message
        msg = MIMEText(text)
        msg['Subject'] = "🤖 [Academy Agent] Sync Report"
        msg['From'] = send_email
        msg['To'] = receive_email
        print(msg.as_string())


        # 2. Connect and Send
        s = smtplib.SMTP(smtp_name, smtp_port)
        s.starttls() # Secure the connection
        s.login(send_email_id, user_app_pw) # Use App Password here
        s.sendmail(send_email, receive_email, msg.as_string())
        s.quit()
        return True
    except Exception as e:
        _notify_user(f"Email error: {e}", "error")
        return False
    
def get_email_from_gmail(gmail_id, gmail_pw):
    """
    Fetches email from Gmail inbox.
    Parameters:
        gmail_id (str): Gmail ID (without @gmail.com).
        gmail_pw (str): Gmail password.
    Returns:
        list: A list of email subjects.
    """
    all_emails = []
    date_limit = (datetime.now() - timedelta(days=3)).date()
    with MailBox('imap.gmail.com').login(gmail_id, gmail_pw) as mailbox:
        for folder in mailbox.folder.list():
            if any(skip in folder.name.upper() for skip in ["TRASH", "SPAM", "DRAFTS"]):
                continue
            mailbox.folder.set(folder.name)
            messages = mailbox.fetch(AND(date_gte=date_limit))
            for msg in messages:
                if msg.subject:
                    all_emails.append(msg.subject)
    return all_emails

from datetime import datetime, timedelta
from imap_tools import MailBox, AND, MailboxFolderSelectError


def get_email_from_gmail(gmail_id, gmail_pw):
    """
    Fetches email subjects from Gmail (last 3 days).
    """
    all_emails = []
    date_limit = (datetime.now() - timedelta(days=3)).date()

    SKIP_KEYWORDS = ["TRASH", "SPAM", "DRAFTS"]
    SKIP_EXACT = ["[GMAIL]"]  # Gmail root folder (select 불가)
    TARGET_FOLDERS = ["INBOX", "[Gmail]/All Mail"]

    with MailBox('imap.gmail.com').login(gmail_id, gmail_pw) as mailbox:
        # for folder in mailbox.folder.list():
            # folder_name = folder.name
        for folder_name in TARGET_FOLDERS:
            

            # 1️⃣ Gmail root 폴더 제거
            if folder_name.upper() in SKIP_EXACT:
                continue

            # 2️⃣ 불필요한 폴더 제거
            if any(skip in folder_name.upper() for skip in SKIP_KEYWORDS):
                continue

            # 3️⃣ 폴더 선택 안전 처리
            try:
                mailbox.folder.set(folder_name)
            except MailboxFolderSelectError:
                # 선택 불가능한 폴더 무시
                continue

            # 4️⃣ 메일 수집
            for msg in mailbox.fetch(AND(date_gte=date_limit)):
                if msg.subject:
                    all_emails.append(msg.subject)

           
    # show the number of emails for debugging
    print(f"Fetched {len(all_emails)} emails from {TARGET_FOLDERS}")
    return all_emails

# def get_students_from_aca2000():
#     # this is for testing purposes
#     return {
#         "M7 월금": ["김빛나", "김서준", "이현수"],
#         "M5 월금": ["김빛나", "김서준", "이현수"],
#     }

def get_class_list_from_aca2000(aca2000_url=None, cust_num=None, user_id=None, user_pw=None, headless=False):
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
        try:
            cust_num = st.secrets.get("ACA2000_CUST_NUM", "")
        except Exception:
            cust_num = os.getenv("ACA2000_CUST_NUM", "")
    if not user_id:
        try:
            user_id = st.secrets.get("ACA2000_USER_ID", "")
        except Exception:
            user_id = os.getenv("ACA2000_USER_ID", "")
    if not user_pw:
        try:
            user_pw = st.secrets.get("ACA2000_USER_PW", "")
        except Exception:
            user_pw = os.getenv("ACA2000_USER_PW", "")

    if not all([cust_num, user_id, user_pw]):
        _notify_user("❌ ACA2000 credentials (CUST_NUM, USER_ID, USER_PW) must be set", "error")
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
            service=Service(ChromeDriverManager().install()),
            options=options
        )
    
    # _make_driver_read_only(driver)

    wait = WebDriverWait(driver, 20)

    try:
        # Step 1: Login
        _notify_user("[ACA2000] Step 1: Logging in...", "info")
        driver.get(aca2000_url)

        cust_num_input = wait.until(EC.presence_of_element_located((By.ID, "custNum")))
        driver.execute_script("arguments[0].value = arguments[1];", cust_num_input, cust_num)
        user_id_input = wait.until(EC.presence_of_element_located((By.ID, "userID")))
        driver.execute_script("arguments[0].value = arguments[1];", user_id_input, user_id)
        user_pw_input = wait.until(EC.presence_of_element_located((By.ID, "userPW")))
        driver.execute_script("arguments[0].value = arguments[1];", user_pw_input, user_pw)

        try:
            login_btn = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                "//button[contains(text(), '로그인')] | //input[@value='로그인'] | //button[@type='submit'] | //input[@type='submit']"
            )))
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
        _notify_user(f"[ACA2000] Current URL after login attempt: {current_url}", "info")
        if "/Account/Login" in current_url or "ReturnUrl" in current_url:
            _notify_user("[ACA2000] ⚠️ Still on login page - checking for errors...", "warning")
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, ".error, .alert, .warning, [class*='error'], [class*='alert']")
                if error_elements:
                    error_text = " ".join([elem.text for elem in error_elements if elem.text])
                    _notify_user(f"[ACA2000] ⚠️ Login error detected: {error_text}", "error")
            except Exception:
                pass

        # Wait for redirect to /Attend
        try:
            wait_redirect = WebDriverWait(driver, 10)
            wait_redirect.until(lambda d: "/Attend" in d.current_url and "/Account/Login" not in d.current_url)
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
                    wait.until(lambda d: "/Attend" in d.current_url and "/Account/Login" not in d.current_url)
                except Exception:
                    _notify_user("[ACA2000] ❌ Could not navigate to /Attend", "error")
                    driver.quit()
                    return {}, None

        # Step 2: Navigate to 출석부
        _notify_user("[ACA2000] Step 2: Navigating to 출석부...", "info")
        try:
            attend_link = wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "a[href*='/Attend'], a[data-langnum='m3'], li[name='Attend'] a, .am3"
            )))
            attend_link.click()
        except Exception:
            if "/Attend" not in driver.current_url:
                driver.get(f"{aca2000_url.rstrip('/')}/Attend")

        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".attendL, .class-list, #반목록, .반목록")))
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
        _notify_user(f"[ACA2000] Target date (the latest Saturday): {target_date}", "info")

        try:
            # Try calendar popup
            try:
                date_input = driver.find_element(By.ID, "iDate")
                date_input.click()
                time.sleep(1)
            except Exception:
                pass
            try:
                calendar_btn = driver.find_element(By.CSS_SELECTOR, "img[src*='btn_calendar'], img[src*='calendar']")
                driver.execute_script("arguments[0].click();", calendar_btn)
                time.sleep(1)
            except Exception:
                pass

            calendar_opened = False
            try:
                wait.until(EC.visibility_of_element_located((
                    By.CSS_SELECTOR, ".datepicker-dropdown, div.datepicker[style*='display: block']"
                )))
                calendar_opened = True
            except Exception:
                pass

            if calendar_opened:
                # Navigate calendar to correct month
                for _ in range(12):
                    try:
                        header = driver.find_element(By.CSS_SELECTOR, "th.datepicker-switch").text.strip()
                        match = re.search(r'(\d{4})년\s*(\d{1,2})월', header)
                        if match:
                            cy, cm = int(match.group(1)), int(match.group(2))
                            if cy == target_year and cm == target_month:
                                break
                            elif (cy < target_year) or (cy == target_year and cm < target_month):
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
                    date_cell = wait.until(EC.element_to_be_clickable((
                        By.XPATH,
                        f"//td[contains(@class, 'day') and not(contains(@class, 'disabled')) and not(contains(@class, 'old')) and not(contains(@class, 'new'))]//div[text()='{target_day}']"
                    )))
                    date_cell.click()
                    time.sleep(2)
                    _notify_user(f"[ACA2000] ✅ Selected date: {target_date}", "success")
                except Exception as e:
                    _notify_user(f"[ACA2000] ⚠️ Could not select date: {type(e).__name__}", "warning")
            else:
                # Arrow button navigation
                for _ in range(30):
                    try:
                        current_date_str = (driver.find_element(By.ID, "iDate").get_attribute("value") or "").strip()
                        if current_date_str == target_date:
                            _notify_user(f"[ACA2000] ✅ Reached target date: {target_date}", "success")
                            break
                        current = datetime.strptime(current_date_str, "%Y-%m-%d")
                        target = datetime.strptime(target_date, "%Y-%m-%d")
                        if current < target:
                            driver.find_element(By.XPATH, "//a[contains(@onclick, 'nextDay')] | //a[contains(., '▶')]").click()
                        else:
                            driver.find_element(By.XPATH, "//a[contains(@onclick, 'prevDay')] | //a[contains(., '◀')]").click()
                        time.sleep(0.5)
                    except Exception:
                        break
        except Exception as e:
            _notify_user(f"[ACA2000] ⚠️ Could not select date: {e}", "warning")

        # Step 4: Get class list
        _notify_user("[ACA2000] Step 4: Fetching class list...", "info")
        class_info = {}
        try:
            wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, ".반목록, #반목록, .class-list, .depth1, li.depth1"
            )))
            class_elements = driver.find_elements(By.CSS_SELECTOR, "a[onclick*='selectClass']")
            for elem in class_elements:
                try:
                    class_name = elem.text.strip()
                    onclick_attr = elem.get_attribute("onclick")
                    if onclick_attr and "selectClass" in onclick_attr:
                        match = re.search(r'selectClass\((\d+)\)', onclick_attr)
                        if match:
                            class_id = match.group(1)
                            if class_name and class_name not in class_info:
                                class_info[class_name] = class_id
                except Exception:
                    continue
            _notify_user(f"[ACA2000] ✅ Found {len(class_info)} classes from date {target_date}", "success")
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
                _notify_user(f"[ACA2000] Processing class: {class_name} (ID: {class_id})...", "info")
                driver.execute_script(f"selectClass({class_id});")
                time.sleep(2)

                try:
                    wait.until(EC.presence_of_element_located((
                        By.CSS_SELECTOR, "span.name[onclick*='showDetail']"
                    )))
                    student_name_elements = driver.find_elements(By.CSS_SELECTOR,
                        "span.name[onclick*='showDetail']"
                    )

                    students = []
                    for student_elem in student_name_elements:
                        student_name = student_elem.text.strip()
                        if not student_name:
                            continue
                        try:
                            parent_row = student_elem.find_element(By.XPATH, "./ancestor::tr | ./ancestor::div[contains(@class, 'row')]")
                            attended_buttons = parent_row.find_elements(By.CSS_SELECTOR,
                                "button.att_btn.on01s[value='출석'], button.on01s[value='출석']"
                            )
                            if attended_buttons:
                                if student_name not in students:
                                    students.append(student_name)
                                    _notify_user(f"[ACA2000]   ✓ {student_name} - 출석", "info")
                            else:
                                _notify_user(f"[ACA2000]   ✗ {student_name} - not attended", "info")
                        except Exception:
                            continue

                    all_students[class_name] = students
                    _notify_user(f"[ACA2000] ✅ Found {len(students)} attended students in {class_name}", "success")

                except Exception as e:
                    _notify_user(f"[ACA2000] ⚠️ Error extracting students for {class_name}: {e}", "warning")
                    all_students[class_name] = []

            except Exception as e:
                _notify_user(f"[ACA2000] ⚠️ Error processing class {class_name}: {e}", "warning")
                all_students[class_name] = []

        _notify_user(f"[ACA2000] ✅ Completed! Processed {len(all_students)} classes", "success")

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return all_students

def get_students_from_aca2000(aca2000_url=None, cust_num=None, user_id=None, user_pw=None, headless=False):
    """
    Fetches student lists from ACA2000 attendance system for ALL classes.
    
    ⚠️ READ-ONLY MODE: This function only READS data and does NOT modify any information.
    All write operations (attendance buttons, edit buttons, save buttons) are disabled.
    
    Steps:
    1. Login to ACA2000 at https://t.aca2000.co.kr/
    2. Click 출석부 (Attendance) menu
    3. Select the latest Saturday date
    4. Get all classes and fetch students for each
    5. Extract student names who participated
    
    Args:
        aca2000_url (str): Base URL for ACA2000 system (defaults to https://t.aca2000.co.kr/)
        cust_num (str): Academy number (학원번호)
        user_id (str): User ID (아이디)
        user_pw (str): User password (비밀번호)
        headless (bool): Whether to run in headless mode
    
    Returns:
        dict: Dictionary with class names as keys and lists of student names as values
        Example: {"M7 월금": ["김빛나", "김서준", ...], "M5 월금": [...]}
    """
    # Default URL
    if not aca2000_url:
        aca2000_url = "https://t.aca2000.co.kr/"
    
    # Get credentials from secrets if not provided
    if not cust_num:
        try:
            cust_num = st.secrets.get("ACA2000_CUST_NUM", "")
        except Exception:
            cust_num = os.getenv("ACA2000_CUST_NUM", "")
    
    if not user_id:
        try:
            user_id = st.secrets.get("ACA2000_USER_ID", "")
        except Exception:
            user_id = os.getenv("ACA2000_USER_ID", "")
    
    if not user_pw:
        try:
            user_pw = st.secrets.get("ACA2000_USER_PW", "")
        except Exception:
            user_pw = os.getenv("ACA2000_USER_PW", "")
    
    if not all([cust_num, user_id, user_pw]):
        _notify_user("❌ ACA2000 credentials (CUST_NUM, USER_ID, USER_PW) must be set", "error")
        return {}
    
    all_students = {}  # {class_name: [student_names]}
    
    # Use read-only mode to prevent any modifications
    with get_driver_context(headless=headless, stealth=False, read_only=True) as driver:
        wait = WebDriverWait(driver, 20)
        
        try:
            # Step 1: Login
            _notify_user("[ACA2000] Step 1: Logging in...", "info")
            driver.get(aca2000_url)
            
            # Wait for login form and fill credentials
            cust_num_input = wait.until(EC.presence_of_element_located((By.ID, "custNum")))
            driver.execute_script("arguments[0].value = arguments[1];", cust_num_input, cust_num)
            
            user_id_input = wait.until(EC.presence_of_element_located((By.ID, "userID")))
            driver.execute_script("arguments[0].value = arguments[1];", user_id_input, user_id)
            
            user_pw_input = wait.until(EC.presence_of_element_located((By.ID, "userPW")))
            driver.execute_script("arguments[0].value = arguments[1];", user_pw_input, user_pw)
            
            # Find and click login button
            # Based on the website, look for login button with text "로그인"
            try:
                # Try multiple selectors for login button
                login_btn = wait.until(EC.element_to_be_clickable((
                    By.XPATH, 
                    "//button[contains(text(), '로그인')] | //input[@value='로그인'] | //button[@type='submit'] | //input[@type='submit']"
                )))
                login_btn.click()
                _notify_user("[ACA2000] Login button clicked", "info")
            except Exception:
                # If no explicit button found, try submitting the form
                try:
                    user_pw_input.submit()
                    _notify_user("[ACA2000] Form submitted", "info")
                except Exception:
                    # Try pressing Enter on password field
                    from selenium.webdriver.common.keys import Keys
                    user_pw_input.send_keys(Keys.RETURN)
                    _notify_user("[ACA2000] Enter key pressed", "info")
            
            
            # Check for login errors or if we're still on login page
            current_url = driver.current_url
            _notify_user(f"[ACA2000] Current URL after login attempt: {current_url}", "info")
            
            # Check if login failed (still on login page with ReturnUrl parameter)
            if "/Account/Login" in current_url or "ReturnUrl" in current_url:
                _notify_user("[ACA2000] ⚠️ Still on login page - checking for errors...", "warning")
                
                # Check for error messages on the page
                try:
                    error_elements = driver.find_elements(By.CSS_SELECTOR, ".error, .alert, .warning, [class*='error'], [class*='alert']")
                    if error_elements:
                        error_text = " ".join([elem.text for elem in error_elements if elem.text])
                        _notify_user(f"[ACA2000] ⚠️ Login error detected: {error_text}", "error")
                except Exception:
                    pass
                
                # Check if login form is still present
                try:
                    if driver.find_elements(By.ID, "custNum"):
                        _notify_user("[ACA2000] ⚠️ Login form still present - login may have failed", "error")
                        driver.save_screenshot("aca2000_login_failed.png")
                        # Try login again with explicit form submission
                        try:
                            login_form = driver.find_element(By.CSS_SELECTOR, "form")
                            login_form.submit()
                            _notify_user("[ACA2000] Retrying login with form submission", "info")
                            time.sleep(3)
                        except Exception:
                            pass
                except Exception:
                    pass
            
            # Wait for login to complete and automatic redirect to /Attend
            # The page should automatically redirect to https://t.aca2000.co.kr/Attend after successful login
            _notify_user("[ACA2000] Waiting for login redirect to /Attend...", "info")
            try:
                # Wait for redirect to /Attend page (this happens automatically after login)
                # Wait up to 10 seconds for redirect
                wait_redirect = WebDriverWait(driver, 10)
                wait_redirect.until(lambda d: "/Attend" in d.current_url and "/Account/Login" not in d.current_url)
                _notify_user(f"[ACA2000] ✅ Login successful and redirected to: {driver.current_url}", "success")
            except Exception:
                # If redirect doesn't happen, check current URL
                current_url = driver.current_url
                _notify_user(f"[ACA2000] ⚠️ Redirect timeout. Current URL: {current_url}", "warning")
                
                # If still on login page, login likely failed
                if "/Account/Login" in current_url or "ReturnUrl" in current_url:
                    _notify_user("[ACA2000] ❌ Login failed - still on login page. Please check credentials.", "error")
                    driver.save_screenshot("aca2000_login_failed.png")
                    return {}
                else:
                    # On a different page, try navigating to /Attend
                    _notify_user("[ACA2000] On different page, navigating to /Attend...", "info")
                    try:
                        driver.get(f"{aca2000_url.rstrip('/')}/Attend")
                        wait.until(lambda d: "/Attend" in d.current_url and "/Account/Login" not in d.current_url)
                        _notify_user(f"[ACA2000] ✅ Navigated to: {driver.current_url}", "success")
                    except Exception as nav_error:
                        _notify_user(f"[ACA2000] ⚠️ Could not navigate to /Attend: {nav_error}", "warning")
                        driver.save_screenshot("aca2000_navigation_failed.png")
                        return {}
            
          
            
            # Verify we're on the Attend page (not login page)
            final_url = driver.current_url
            _notify_user(f"[ACA2000] Final URL after login: {final_url}", "info")
            
            if "/Attend" not in final_url or "/Account/Login" in final_url:
                _notify_user("[ACA2000] ⚠️ Not on /Attend page, attempting to navigate...", "warning")
                try:
                    driver.get(f"{aca2000_url.rstrip('/')}/Attend")
                    wait.until(lambda d: "/Attend" in d.current_url and "/Account/Login" not in d.current_url)
                    _notify_user(f"[ACA2000] ✅ Now on: {driver.current_url}", "success")
                except Exception:
                    _notify_user("[ACA2000] ❌ Could not reach /Attend page. Login may have failed.", "error")
                    driver.save_screenshot("aca2000_final_check_failed.png")
                    return {}
            
            # Step 2: Click 출석부 (Attendance) menu
            _notify_user("[ACA2000] Step 2: Navigating to 출석부 (Attendance)...", "info")
            try:
                # Try multiple selectors for the 출석부 link
                attend_link = wait.until(EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "a[href*='/Attend'], a[data-langnum='m3'], li[name='Attend'] a, .am3"
                )))
                attend_link.click()
            except Exception:
                # If direct click doesn't work, navigate directly
                if "/Attend" not in driver.current_url:
                    driver.get(f"{aca2000_url.rstrip('/')}/Attend")
            
            # Wait for attendance page to load
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".attendL, .class-list, #반목록, .반목록")))
            _notify_user("[ACA2000] ✅ Navigated to 출석부", "success")
            
            # for debugging
            time.sleep(5) # wait for 5 seconds to see the page
            
            # Check what date is currently displayed
            try:
                current_date_display = driver.find_element(By.CSS_SELECTOR, ".date-display, .current-date, div[class*='date']").text
                _notify_user(f"[ACA2000] Current date displayed: {current_date_display}", "info")
            except Exception:
                _notify_user("[ACA2000] Could not read current date display", "info")
            
            driver.save_screenshot("aca2000_before_date_selection.png")
            _notify_user("[ACA2000] 📸 Screenshot before date selection: aca2000_before_date_selection.png", "info")
            
            # Step 3: Select the latest Saturday date
            _notify_user("[ACA2000] Step 3: Selecting latest Saturday date...", "info")
            today = datetime.now()
            # Find the most recent Saturday
            days_since_saturday = (today.weekday() - 5) % 7
            if days_since_saturday == 0 and today.weekday() != 5:
                # If today is not Saturday, go back to last Saturday
                days_since_saturday = 7
            latest_saturday = today - timedelta(days=days_since_saturday)
            target_date = latest_saturday.strftime("%Y-%m-%d")
            target_year = latest_saturday.year
            target_month = latest_saturday.month
            target_day = latest_saturday.day
            
            _notify_user(f"[ACA2000] Target date: {target_date} (latest Saturday)", "info")
            
            try:
                # Step 3a: Try clicking on the date text or calendar icon to open calendar
                _notify_user("[ACA2000] Attempting to open calendar...", "info")
                
                # Try clicking the date input field (might open calendar)
                try:
                    date_input = driver.find_element(By.ID, "iDate")
                    date_input.click()
                    time.sleep(1)
                except Exception:
                    pass
                
                # Or try clicking the calendar icon
                try:
                    calendar_btn = driver.find_element(By.CSS_SELECTOR, "img[src*='btn_calendar'], img[src*='calendar']")
                    driver.execute_script("arguments[0].click();", calendar_btn)
                    time.sleep(1)
                except Exception:
                    pass
                
                # Check if calendar popup appeared
                calendar_opened = False
                try:
                    calendar_popup = wait.until(EC.visibility_of_element_located((
                        By.CSS_SELECTOR, 
                        ".datepicker-dropdown, div.datepicker[style*='display: block']"
                    )))
                    calendar_opened = True
                    _notify_user("[ACA2000] ✅ Calendar popup opened", "success")
                except Exception:
                    _notify_user("[ACA2000] Calendar popup not found, will use arrow navigation", "info")
                
                driver.save_screenshot("aca2000_after_calendar_attempt.png")
                _notify_user("[ACA2000] 📸 Screenshot: aca2000_after_calendar_attempt.png", "info")
                
                # Step 3b: Navigate to the target date
                if calendar_opened:
                    # If calendar popup is open, navigate within the popup
                    _notify_user("[ACA2000] Navigating calendar popup...", "info")
                    max_navigation_attempts = 12
                    calendar_navigated = False
                    
                    for attempt in range(max_navigation_attempts):
                        try:
                            # Find the calendar header showing current month/year (e.g., "2026년 1월")
                            _notify_user(f"[ACA2000] Looking for calendar header (attempt {attempt + 1})...", "info")
                            calendar_header = driver.find_element(By.CSS_SELECTOR, "th.datepicker-switch")
                            header_text = calendar_header.text.strip()
                            _notify_user(f"[ACA2000] Calendar showing: {header_text}", "info")
                            
                            # Extract year and month from header (format: "2026년 1월")
                            import re
                            match = re.search(r'(\d{4})년\s*(\d{1,2})월', header_text)
                            if match:
                                current_year = int(match.group(1))
                                current_month = int(match.group(2))
                                
                                # Check if we're on the correct month
                                if current_year == target_year and current_month == target_month:
                                    _notify_user(f"[ACA2000] ✅ On correct month: {target_year}-{target_month:02d}", "success")
                                    calendar_navigated = True
                                    break
                                elif (current_year < target_year) or (current_year == target_year and current_month < target_month):
                                    # Need to go forward
                                    next_btn = driver.find_element(By.CSS_SELECTOR, "th.next")
                                    next_btn.click()
                                    time.sleep(0.5)
                                else:
                                    # Need to go backward
                                    prev_btn = driver.find_element(By.CSS_SELECTOR, "th.prev")
                                    prev_btn.click()
                                    time.sleep(0.5)
                            else:
                                # Can't parse header, try clicking the date anyway
                                _notify_user("[ACA2000] ⚠️ Could not parse calendar header, proceeding with date selection", "warning")
                                calendar_navigated = True
                                break
                        except Exception as e:
                            # Calendar might have closed or element not found - this is okay if we already navigated
                            if not calendar_navigated:
                                _notify_user(f"[ACA2000] ⚠️ Calendar navigation issue: {type(e).__name__}", "warning")
                                driver.save_screenshot("aca2000_calendar_nav_error.png")
                                _notify_user("[ACA2000] 📸 Error screenshot saved: aca2000_calendar_nav_error.png", "info")
                            break
                
                    # Step 3c: Click on the target Saturday date in calendar popup
                    # Date structure: <td class="day"><div>16</div></td>
                    try:
                        date_cell = wait.until(EC.element_to_be_clickable((
                            By.XPATH, 
                            f"//td[contains(@class, 'day') and not(contains(@class, 'disabled'))]//div[text()='{target_day}']"
                        )))
                        _notify_user(f"[ACA2000] Clicking on date: {target_day}", "info")
                        date_cell.click()
                        time.sleep(2)
                        _notify_user(f"[ACA2000] ✅ Selected date: {target_date}", "success")
                    except Exception as e:
                        _notify_user(f"[ACA2000] ⚠️ Could not click date in calendar: {e}", "warning")
                
                else:
                    # No calendar popup - use arrow buttons to navigate to target date
                    _notify_user("[ACA2000] Using arrow button navigation...", "info")
                    
                    max_clicks = 30  # Safety limit
                    for click_count in range(max_clicks):
                        try:
                            # Read the date from the input field with id="iDate"
                            current_date_elem = driver.find_element(By.ID, "iDate")
                            current_date_str = current_date_elem.get_attribute("value").strip()
                            _notify_user(f"[ACA2000] Current: {current_date_str}, Target: {target_date}", "info")
                            
                            if current_date_str == target_date:
                                _notify_user(f"[ACA2000] ✅ Reached target date: {target_date}", "success")
                                break
                            
                            # Parse dates for comparison
                            current = datetime.strptime(current_date_str, "%Y-%m-%d")
                            target = datetime.strptime(target_date, "%Y-%m-%d")
                            
                            if current < target:
                                # Need to go forward - click right arrow
                                next_btn = driver.find_element(By.XPATH, "//a[contains(@onclick, 'nextDay')] | //a[contains(., '▶')]")
                                next_btn.click()
                                _notify_user("[ACA2000] Clicked next day →", "info")
                                time.sleep(0.5)
                            else:
                                # Need to go backward - click left arrow
                                prev_btn = driver.find_element(By.XPATH, "//a[contains(@onclick, 'prevDay')] | //a[contains(., '◀')]")
                                prev_btn.click()
                                _notify_user("[ACA2000] Clicked prev day ←", "info")
                                time.sleep(0.5)
                                
                        except Exception as e:
                            _notify_user(f"[ACA2000] ⚠️ Arrow navigation failed: {str(e)[:100]}", "warning")
                            break
                    
                    driver.save_screenshot("aca2000_after_date_navigation.png")
                    _notify_user("[ACA2000] 📸 Screenshot: aca2000_after_date_navigation.png", "info")
                
            except Exception as e:
                _notify_user(f"[ACA2000] ⚠️ Could not select date: {e}", "warning")
                driver.save_screenshot("aca2000_date_selection_failed.png")
                _notify_user("[ACA2000] Using current date instead", "info")
            
            # Step 4: Get all classes with their IDs
            _notify_user("[ACA2000] Step 4: Fetching class list...", "info")
            try:
                # Wait for class list to be visible
                wait.until(EC.presence_of_element_located((
                    By.CSS_SELECTOR, 
                    ".반목록, #반목록, .class-list, .depth1, li.depth1"
                )))
                
                # Find all class links/items with onclick="selectClass(ID)"
                # HTML structure: <a href="#" class="depth1" onclick="selectClass(2246)">
                #                   <span id="2246">M5 월금</span>
                #                 </a>
                class_elements = driver.find_elements(By.CSS_SELECTOR, 
                    "a[onclick*='selectClass']"
                )
                
                class_info = {}  # {class_name: class_id}
                for elem in class_elements:
                    try:
                        # Get class name from the span inside the link
                        class_name = elem.text.strip()
                        
                        # Extract class ID from onclick="selectClass(2246)"
                        onclick_attr = elem.get_attribute("onclick")
                        if onclick_attr and "selectClass" in onclick_attr:
                            # Extract ID from "selectClass(2246)"
                            import re
                            match = re.search(r'selectClass\((\d+)\)', onclick_attr)
                            if match:
                                class_id = match.group(1)
                                if class_name and class_name not in class_info:
                                    class_info[class_name] = class_id
                                    _notify_user(f"[ACA2000] Found class: {class_name} (ID: {class_id})", "info")
                    except Exception as e:
                        _notify_user(f"[ACA2000] ⚠️ Could not parse class element: {e}", "warning")
                        continue
                
                _notify_user(f"[ACA2000] ✅ Found {len(class_info)} classes", "success")
                
            except Exception as e:
                _notify_user(f"[ACA2000] ⚠️ Could not find class list: {e}", "warning")
                class_info = {}
                
            # here
            
            # Step 5: For each class, select it and extract student list
            for class_name, class_id in class_info.items():
                try:
                    _notify_user(f"[ACA2000] Processing class: {class_name} (ID: {class_id})...", "info")
                    
                    # Click on the class using JavaScript to trigger selectClass(ID)
                    driver.execute_script(f"selectClass({class_id});")
                    time.sleep(2)  # Wait for class selection to load students
                    
                    # Extract student names who ATTENDED (green "출석" button)
                    try:
                        # Wait for student list to load
                        wait.until(EC.presence_of_element_located((
                            By.CSS_SELECTOR, 
                            "span.name[onclick*='showDetail']"
                        )))
                        
                        # Find all student name elements
                        # Structure: <span class="name" onclick="showDetail(...)">김나영</span>
                        student_name_elements = driver.find_elements(By.CSS_SELECTOR, 
                            "span.name[onclick*='showDetail']"
                        )
                        
                        students = []
                        for student_elem in student_name_elements:
                            student_name = student_elem.text.strip()
                            if not student_name:
                                continue
                            
                            try:
                                # Find the attendance button for this student
                                # The button should be in the same row/parent container
                                # Look for green "출석" button: <button class="att_btn on01s" value="출석">출석</button>
                                parent_row = student_elem.find_element(By.XPATH, "./ancestor::tr | ./ancestor::div[contains(@class, 'row')]")
                                
                                # Check if there's a green "출석" button (on01s class indicates green/attended)
                                attended_buttons = parent_row.find_elements(By.CSS_SELECTOR, 
                                    "button.att_btn.on01s[value='출석'], button.on01s[value='출석']"
                                )
                                
                                if attended_buttons:
                                    # Student has green "출석" status
                                    if student_name not in students:
                                        students.append(student_name)
                                        _notify_user(f"[ACA2000]   ✓ {student_name} - 출석", "info")
                                else:
                                    _notify_user(f"[ACA2000]   ✗ {student_name} - not attended", "info")
                                    
                            except Exception as e:
                                _notify_user(f"[ACA2000] ⚠️ Could not check attendance for {student_name}: {e}", "warning")
                                continue
                        
                        if students:
                            all_students[class_name] = students
                            _notify_user(f"[ACA2000] ✅ Found {len(students)} attended students in {class_name}", "success")
                        else:
                            all_students[class_name] = []
                            _notify_user(f"[ACA2000] ⚠️ No attended students found for {class_name}", "warning")
                    
                    except Exception as e:
                        _notify_user(f"[ACA2000] ⚠️ Error extracting students for {class_name}: {e}", "warning")
                        all_students[class_name] = []
                        continue
                
                except Exception as e:
                    _notify_user(f"[ACA2000] ⚠️ Error processing class {class_name}: {e}", "warning")
                    all_students[class_name] = []
                    continue
            
            _notify_user(f"[ACA2000] ✅ Completed! Processed {len(all_students)} classes", "success")
            return all_students
            
        except Exception as e:
            _notify_user(f"[ACA2000] ❌ Error during crawling: {e}", "error")
            driver.save_screenshot("aca2000_error.png")
            return all_students




# def get_headless_driver():
#     options = Options()
    
#     # The primary command for headless
#     options.add_argument("--headless=new") 
    
#     # Essential settings for servers/background stability
#     options.add_argument("--no-sandbox")
#     options.add_argument("--disable-dev-shm-usage")
#     options.add_argument("--disable-gpu")
    
#     # Optional: Set a window size so the "invisible" browser 
#     # doesn't default to a tiny mobile view
#     options.add_argument("--window-size=1920,1080")

#     # Optional: Pretend to be a real user to avoid bot detection
#     options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

#     driver = webdriver.Chrome(
#         service=Service(ChromeDriverManager().install()), 
#         options=options
#     )
#     return driver


def get_headless_stealth_driver():
    """
    Creates a headless Chrome WebDriver with stealth settings to avoid detection.
    Uses undetected-chromedriver which patches Chrome to avoid bot detection.
    Falls back to regular selenium with stealth if undetected-chromedriver fails.
    Returns:
        webdriver.Chrome: Configured headless Chrome WebDriver.
    """
    import shutil
    from selenium_stealth import stealth

    # Try undetected-chromedriver first
    try:
        import undetected_chromedriver as uc

        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")

        # Use system chrome binary if available (Streamlit Cloud)
        system_chrome = shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
        if system_chrome:
            options.binary_location = system_chrome

        driver = uc.Chrome(options=options, headless=True, use_subprocess=False)
        _notify_user("[Naver] Using undetected-chromedriver", "info")
        return driver

    except Exception as e:
        _notify_user(f"[Naver] undetected-chromedriver failed ({e}), falling back to selenium-stealth", "warning")

    # Fallback to regular selenium with stealth
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    system_chromedriver = shutil.which("chromedriver")
    if system_chromedriver:
        from selenium.webdriver.chrome.service import Service
        driver = webdriver.Chrome(service=Service(system_chromedriver), options=options)
    else:
        driver = webdriver.Chrome(options=options)

    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    return driver

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

    STOP_WORDS = {'대기', '휴강', '신규', '월', '화', '수', '목', '금', '토', '일', '월금', '화목'}

    def extract_korean_name(entry):
        matches = re.findall(r'[가-힣]+', entry)
        names = [m for m in matches if 2 <= len(m) <= 3 and m not in STOP_WORDS]
        return names[0] if names else None

    # Build searchable text per email
    email_texts = []
    for e in emails:
        combined = f"{e['subject']} {e['content']} {' '.join(e['attachments'])}"
        email_texts.append((combined, e['subject']))

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
        results[class_name] = {'matched': matched, 'missing': missing}

    return results


def fetch_naver_email(headless=False, naver_id=None, naver_passkey=None):
    """
    Fetches Naver email using Selenium WebDriver.
    Parameters:
        headless (bool): Whether to run the browser in headless mode.
        naver_id (str): Naver login ID.
        naver_passkey (str): Naver login password or app password.
    Returns:
        list: List of dicts with sender, subject, content, and attachments from recent emails
              Example: [{"sender": "example@naver.com", "subject": "Hello", "content": "...", "attachments": ["a.pdf"]}, ...]
    """
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import random
    import re

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
                    for item in container.find_elements(By.CSS_SELECTOR, "li.file_item"):
                        base = None
                        ext = None
                        try:
                            base_elem = item.find_element(By.CSS_SELECTOR, "strong.file_title span.text")
                            base = base_elem.text.strip()
                        except Exception:
                            base = None
                        try:
                            ext_elem = item.find_element(By.CSS_SELECTOR, "strong.file_title span.file_extension")
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
        headless=headless,
        naver_id=naver_id,
        naver_passkey=naver_passkey
    )
    
    if not driver:
        raise RuntimeError("Naver login failed. Check your ID and password.")
    
    wait = WebDriverWait(driver, 10)
    
    try:
        # Add random delay to appear more human-like
        time.sleep(random.uniform(1.5, 3.0))

        # Step 2: Navigate to Naver Mail
        _notify_user("[Naver] Navigating to mail...", "info")
        driver.get("https://mail.naver.com/")

        # Random delay after navigation
        time.sleep(random.uniform(2.0, 4.0))

        # Wait for mail list to load (using actual Naver Mail structure)
        wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR,
            "ol.mail_list, #mail_list_wrap, li.mail_item"
        )))

        # Ensure we're on '전체메일' (some accounts default to '받은메일함')
        try:
            all_mail_link = driver.find_element(
                By.CSS_SELECTOR, "a.mailbox_label[title='전체메일']"
            )
            all_mail_link.click()
            time.sleep(random.uniform(1.5, 2.5))
            wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "ol.mail_list, #mail_list_wrap, li.mail_item"
            )))
        except Exception:
            _notify_user("[Naver] ⚠️ Could not navigate to '전체메일', using current view", "warning")

        # Add another small random delay before extracting
        time.sleep(random.uniform(0.5, 1.5))

        # Step 3: Extract email subjects (only unread emails via CSS selector)
        _notify_user("[Naver] Fetching emails...", "info")

        # Keep track of all processed email IDs across pages
        processed_mail_ids = []

        # Only process emails from today (for testing; change to timedelta(days=7) for production)
        # date_limit = datetime.now().date()
        date_limit = (datetime.now() - timedelta(days=2)).date()
        date_limit_reached = False
        page_num = 1

        while True:
            # Get unread mail items on current page
            mail_items = driver.find_elements(By.CSS_SELECTOR, "li.mail_item:not(.read)")

            if not mail_items:
                if page_num == 1:
                    _notify_user("[Naver] ⚠️ No unread mail items found", "warning")
                break

            _notify_user(f"[Naver] Page {page_num}: Found {len(mail_items)} unread mail items", "info")

            page_mail_ids = []

            for mail_item in mail_items:
                try:
                    # Check email date — skip if older than date_limit
                    # Naver Mail date formats:
                    #   Today: "오후 03:32" (time only, no dot)
                    #   Past days: "01.30 16:25" (MM.DD HH:MM)
                    try:
                        date_elem = mail_item.find_element(By.CSS_SELECTOR, "div.mail_date_wrap span.mail_date")
                        date_text = (date_elem.text or date_elem.get_attribute("textContent") or "").strip()
                        if re.search(r'\d{2}\.\d{2}', date_text):
                            # "MM.DD HH:MM" format (e.g. "02.03 14:32")
                            date_part = re.search(r'(\d{2}\.\d{2})', date_text).group(1)
                            mail_date = datetime.strptime(f"{datetime.now().year}.{date_part}", "%Y.%m.%d").date()
                        else:
                            # Time only (e.g. "오후 03:32") means today
                            mail_date = datetime.now().date()
                        if mail_date < date_limit:
                            _notify_user(f"[Naver] Reached emails older than date limit ({date_text}), stopping", "info")
                            date_limit_reached = True
                            break
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
                        sender_elem = mail_item.find_element(By.CSS_SELECTOR, "button.button_sender")
                        if sender_elem:
                            # Get sender from title attribute (contains email)
                            sender = sender_elem.get_attribute("title")
                            if sender:
                                sender = sender.strip().strip('<>')  # Remove < > brackets if present
                    except Exception:
                        # Fallback to other selectors
                        sender_selectors = [
                            "div.mail_sender",
                            "button.toggle_conversation_mail",
                            "span.mail_sender",
                            "[class*='sender']"
                        ]
                        for selector in sender_selectors:
                            try:
                                sender_elem = mail_item.find_element(By.CSS_SELECTOR, selector)
                                if sender_elem and sender_elem.text.strip():
                                    sender = sender_elem.text.strip()
                                    # Clean up sender text (remove date if present)
                                    sender_lines = [line.strip() for line in sender.split('\n') if line.strip()]
                                    if sender_lines:
                                        # Take first line that doesn't look like a date (format: 01-21)
                                        for line in sender_lines:
                                            if not line.replace('-', '').replace('.', '').isdigit():
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
                        "[class*='title']"
                    ]

                    for selector in subject_selectors:
                        try:
                            subject_elem = mail_item.find_element(By.CSS_SELECTOR, selector)
                            if subject_elem and subject_elem.text.strip():
                                subject = subject_elem.text.strip()
                                # Split by newlines and take first non-empty line
                                subject_lines = [line.strip() for line in subject.split('\n') if line.strip()]
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
                        title_link = mail_item.find_element(By.CSS_SELECTOR, "a.mail_title_link")
                        title_link.click()

                        # Wait for email content to load
                        time.sleep(random.uniform(1.0, 2.0))
                        wait.until(EC.presence_of_element_located((
                            By.CSS_SELECTOR,
                            "div.mail_view_contents_inner, div.mail_view_contents"
                        )))

                        # Extract content
                        content_selectors = [
                            "div.mail_view_contents_inner",
                            "div.mail_view_contents"
                        ]
                        for content_selector in content_selectors:
                            try:
                                content_elem = driver.find_element(By.CSS_SELECTOR, content_selector)
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
                        wait.until(EC.presence_of_element_located((
                            By.CSS_SELECTOR,
                            "ul.mail_list, li.mail_item"
                        )))

                    except Exception as e:
                        _notify_user(f"[Naver] ⚠️ Could not fetch content: {type(e).__name__}", "warning")
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
                            "attachments": attachments
                        }
                        # Check for duplicates based on sender+subject combination
                        is_duplicate = any(
                            e["sender"] == email_data["sender"] and e["subject"] == email_data["subject"]
                            for e in email_list
                        )
                        if not is_duplicate:
                            email_list.append(email_data)
                            _notify_user(f"[Naver]   • {sender if sender else 'Unknown'}: {subject if subject else '(no subject)'}", "info")

                except Exception as e:
                    _notify_user(f"[Naver] ⚠️ Could not extract email: {type(e).__name__}", "warning")
                    continue

            # Mark this page's processed emails as unread before moving on
            if page_mail_ids:
                _notify_user(f"[Naver] Selecting {len(page_mail_ids)} emails on page {page_num}...", "info")
                checked_count = 0
                for mail_id in page_mail_ids:
                    try:
                        mail_item = driver.find_element(By.CSS_SELECTOR, f"li.{mail_id}")
                        checkbox = mail_item.find_element(By.CSS_SELECTOR, "label[role='checkbox']")
                        if checkbox.get_attribute("aria-checked") != "true":
                            checkbox.click()
                            time.sleep(random.uniform(0.2, 0.4))
                        checked_count += 1
                    except Exception as e:
                        _notify_user(f"[Naver] ⚠️ Could not check {mail_id}: {type(e).__name__}", "warning")

                if checked_count > 0:
                    _notify_user(f"[Naver] Marking {checked_count} emails as unread...", "info")
                    try:
                        unread_button = wait.until(EC.element_to_be_clickable((
                            By.XPATH,
                            "//button[contains(@class, 'button_task') and normalize-space(.)='안읽음']"
                        )))
                        unread_button.click()
                        time.sleep(random.uniform(0.5, 1.0))
                        _notify_user("[Naver] ✅ Marked emails as unread", "success")
                    except Exception as e:
                        _notify_user(f"[Naver] ⚠️ Could not mark as unread: {type(e).__name__}", "warning")

                processed_mail_ids.extend(page_mail_ids)

            # Stop if date limit was reached
            if date_limit_reached:
                break

            # Try to go to the next page
            try:
                next_btn = driver.find_element(By.CSS_SELECTOR, "button.button_next#next-page")
                if next_btn.get_attribute("disabled") is not None:
                    _notify_user(f"[Naver] Reached last page (page {page_num})", "info")
                    break
                next_btn.click()
                page_num += 1
                time.sleep(random.uniform(1.5, 2.5))
                wait.until(EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "ol.mail_list, li.mail_item"
                )))
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
    import shutil

    _id = naver_id if naver_id else st.secrets.get("NAVER_ID")
    _pw = naver_passkey if naver_passkey else st.secrets.get("NAVER_PW")

    options = Options()
    if headless:
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
    options.add_argument(
        'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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
        WebDriverWait(driver, 60).until(lambda d: "nid.naver.com/nidlogin.login" not in d.current_url)

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

# test using webdriver before implementing aca2000 logics
def login_to_naver(headless=False, stealth=False, naver_id=None, naver_passkey=None):
    """
    Logs into Naver using Selenium WebDriver.
    Parameters:
        headless (bool): Whether to run the browser in headless mode.
        naver_id (str): Naver login ID.
        naver_passkey (str): Naver login password or app password.
    """    
    # Disable read-only mode for login (we need to submit the form)
    with get_driver_context(headless=headless, stealth=stealth, read_only=False) as driver:
        # Set a max wait time of 10 seconds
        wait = WebDriverWait(driver, 10)
        try:
            driver.get("https://nid.naver.com/nidlogin.login")

            # 1. Wait until the ID input is actually clickable
            id_input = wait.until(EC.element_to_be_clickable((By.NAME, "id")))
            
            # 2. Instead of time.sleep, use JS injection for safety on Naver
            # check if naver_id and naver_passkey are defined
            if not naver_id or not naver_passkey:
                _notify_user("❌ NAVER_ID and NAVER_PW must be set before calling login_to_naver()", "error")
                return False
            driver.execute_script("arguments[0].value = arguments[1];", id_input, naver_id)

            # 3. Wait for PW input
            pw_input = wait.until(EC.element_to_be_clickable((By.NAME, "pw")))
            driver.execute_script("arguments[0].value = arguments[1];", pw_input, naver_passkey)

            # 4. Wait for and click Login Button
            login_btn = wait.until(EC.element_to_be_clickable((By.ID, "log.login")))
            login_btn.click()

            # 5. Verify login by waiting for a specific element on the HOME page
            # This confirms we are actually logged in before the script continues
            profile_btn = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "MyView-module__nickname___fcxwI")))
            profile_btn.click()
            print("✅ Successfully logged in and redirected!")

        except Exception as e:
            print(f"❌ Automation timed out or failed: {e}")
            driver.save_screenshot("debug_timeout.png")
        # Keeping the browser open for you to see the result
        input("Press Enter to close the browser...")
    
def send_kakao_notification(api_key, kakao_registered_redirect_url, message_text, kakao_id=None, kakao_pw=None):
    try:
        # Initialize Kakao Message API
        msg_api = Message(service_key=api_key)

        # automate OAuth login and get token to send message
        access_token = get_kakao_token_via_webdriver(
            rest_api_key=api_key,
            kakao_registered_redirect_url=kakao_registered_redirect_url,
            kakao_id=kakao_id,
            kakao_pw=kakao_pw
            )
        # Exchange the URL for a token
        # access_token = msg_api.get_access_token_by_redirected_url(redirect_url)
        
        # set token to message API
        msg_api.set_access_token(access_token)
        
        # Send to "My Chatroom"
        msg_api.send_message_to_me(
            message_type="text",
            text=message_text,
            link={"web_url": "https://naver.com", "mobile_web_url": "https://naver.com"},
            button_title="Check Report"
        )
        
        # close msg_api session if needed
        # msg_api.close()
        
        return True
    except Exception as e:
        _notify_user(f"Kakao Error: {e}", "error")
        return False
    
def get_kakao_token_via_webdriver(rest_api_key, redirect_uri, kakao_id=None, kakao_pw=None):
    """
    Automate the Kakao OAuth login and consent flow to get the authorization code.
    If already logged in, skips login and goes straight to consent/redirect.
    
    Flow: oauth_url -> (login) -> (consent) -> redirect_uri with code token -> code token extraction -> return code token which will be used to send message
    
    Args:
        rest_api_key (str): Kakao REST API Key
        redirect_uri (str): Redirect URI registered in Kakao Developers
        kakao_id (str): Kakao account ID (optional)
        kakao_pw (str): Kakao account password (optional)
        scope (str): OAuth scope (default: 'talk_message')
    Returns:
        str: The authorization code from the redirect URL
    """


    # Use PyKakao to generate the OAuth URL (recommended)
    msg_api = Message(service_key=rest_api_key)
    oauth_url = msg_api.get_url_for_generating_code()
    _notify_user(f'[Kakao OAuth] Navigating to URL: {oauth_url}', "info")
    
    # Disable read-only mode for OAuth login (we need to submit forms)
    with get_driver_context(headless=False, stealth=False, read_only=False) as driver:
        driver.get(oauth_url)
        wait = WebDriverWait(driver, 300)
            # Try to find login form. If not present, skip login.
        try:
            id_input = wait.until(EC.presence_of_element_located((By.NAME, "loginId")))
            pw_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))
            
            if kakao_id and kakao_pw:
                _notify_user("[Kakao OAuth] Filling in login credentials...", "info")
                
                # Clear and fill the inputs
                id_input.clear()
                id_input.send_keys(kakao_id)
                
                pw_input.clear()
                pw_input.send_keys(kakao_pw)
                
                wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn_g.highlight.submit"))).click()  # Give the form a moment to register the input
                _notify_user("[Kakao OAuth] Login button clicked, waiting for redirect...", "info")
                
        except Exception as e:
            _notify_user(f"[Kakao OAuth] Login form not found or already logged in: {e}", "error")
            pass  # Login form not present, already logged in
        
        # Consent (if needed)
        try:
            consent_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
            consent_btn.click()
            _notify_user("[Kakao OAuth] Consent button clicked...", "info")
        except Exception:
            _notify_user("[Kakao OAuth] No consent needed or already granted", "info")
            pass  # Consent may not be required if already granted
        
        # Wait for redirect
        _notify_user("[Kakao OAuth] Waiting for redirect...", "info")
        wait.until(lambda d: redirect_uri in d.current_url)
        redirected_url = driver.current_url # capture current URL
        
        # parse the redirected URL to extract the access token
        access_token = msg_api.get_access_token_by_redirected_url(redirected_url)
        _notify_user(f"[Kakao OAuth] Redirected URL: {redirected_url}", "info")
        _notify_user(f"[Kakao OAuth] Extracted code: {access_token}", "info")

        return access_token

if __name__ == "__main__":
    # Load from secrets.toml (preferred) or fallback to .env
    # NAVER_ID = _get_secret("NAVER_ID") or os.getenv("NAVER_ID")
    # NAVER_APP_PW = _get_secret("NAVER_APP_PW") or os.getenv("NAVER_APP_PW")
    
    # if not NAVER_ID or not NAVER_APP_PW:
    #     print("❌ NAVER_ID and NAVER_APP_PW must be set in .streamlit/secrets.toml or .env file")
    # else:
    #     login_to_naver(headless=False, naver_id=NAVER_ID, naver_passkey=NAVER_APP_PW)
    
    # test kakao OAuth
    # get_kakao_token_via_webdriver(
    #     rest_api_key=_get_secret("KAKAO_REST_API_KEY") or os.getenv("KAKAO_REST_API_KEY"),
    #     redirect_uri=_get_secret("KAKAO_REDIRECT_URL") or os.getenv("KAKAO_REDIRECT_URL"),
    #     kakao_id=_get_secret("KAKAO_ID") or os.getenv("KAKAO_ID"),
    #     kakao_pw=_get_secret("KAKAO_PW") or os.getenv("KAKAO_PW")
    # )
    
    
    # test aca2000 attendance system
    # use stealit.secrets to get the credentials
    # cust_num = st.secrets.get("ACA2000_CUST_NUM")
    # user_id = st.secrets.get("ACA2000_USER_ID")
    # user_pw = st.secrets.get("ACA2000_USER_PW")
    # get_students_from_aca2000(headless=False, cust_num=cust_num, user_id=user_id, user_pw=user_pw)
    
    
    # test get_email_from_gmail
    # gmail_id = st.secrets.get("GMAIL_ID")
    # gmail_pw = st.secrets.get("GMAIL_PW")
    # get_email_from_gmail(gmail_id, gmail_pw)
    
    
    # test login_naver_selenium
    # login_naver_selenium()
    
    # test fetch_naver_email
    # use stealit.secrets to get the credentials
    naver_id = st.secrets.get("NAVER_ID")
    naver_passkey = st.secrets.get("NAVER_PW")
    fetch_naver_email(headless=False, stealth=False, naver_id=naver_id, naver_passkey=naver_passkey)


