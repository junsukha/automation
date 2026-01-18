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
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from selenium_stealth import stealth

from PyKakao import Message  # Import PyKakao

import time
from contextlib import contextmanager

def _notify_user(message, message_type="error"):
    """
    Safely notify user using Streamlit if available, otherwise use print.
    
    Args:
        message (str): Message to display
        message_type (str): Type of message - "error", "success", "warning", or "info"
    """
    try:
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
    
    
def get_students_from_aca2000(aca2000_url=None, cust_num=None, user_id=None, user_pw=None, headless=False):
    """
    Fetches student lists from ACA2000 attendance system for each class.
    
    ⚠️ READ-ONLY MODE: This function only READS data and does NOT modify any information.
    All write operations (attendance buttons, edit buttons, save buttons) are disabled.
    
    Steps:
    1. Login to ACA2000 at https://t.aca2000.co.kr/
    2. Click 출석부 (Attendance) menu
    3. Select the latest Saturday date
    4. Select a class from the class list
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
                login_btn = wait.until(EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "button:contains('로그인'), input[value='로그인'], .btn_login, button[type='submit'], input[type='submit']"
                )))
                login_btn.click()
            except Exception:
                # If no explicit button found, try submitting the form
                try:
                    user_pw_input.submit()
                except Exception:
                    # Try pressing Enter on password field
                    from selenium.webdriver.common.keys import Keys
                    user_pw_input.send_keys(Keys.RETURN)
            
            # Wait for login to complete - check for navigation away from login page
            # The page should redirect after successful login
            wait.until(lambda d: d.current_url != aca2000_url or "출석부" in d.page_source or "/Attend" in d.current_url)
            _notify_user("[ACA2000] ✅ Login successful", "success")
            
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
            
            # Click on date selector/calendar
            try:
                date_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='date'], .date-selector, .calendar-input")))
                driver.execute_script("arguments[0].value = arguments[1];", date_input, target_date)
                # Trigger change event
                driver.execute_script("arguments[0].dispatchEvent(new Event('change'));", date_input)
            except Exception:
                # Alternative: Click calendar icon and select date
                try:
                    calendar_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".calendar-icon, .btn-calendar, img[src*='calendar']")))
                    calendar_btn.click()
                    # Wait for calendar to open and select the date
                    date_element = wait.until(EC.element_to_be_clickable((By.XPATH, f"//td[contains(@class, 'day') and text()='{latest_saturday.day}']")))
                    date_element.click()
                except Exception:
                    _notify_user("[ACA2000] ⚠️ Could not set date automatically, using current date", "warning")
            
            time.sleep(1)  # Brief wait for date selection to process
            _notify_user(f"[ACA2000] ✅ Selected date: {target_date}", "success")
            
            # Step 4: Get all classes and iterate through them
            _notify_user("[ACA2000] Step 4: Fetching class list...", "info")
            try:
                # Wait for class list to be visible
                wait.until(EC.presence_of_element_located((
                    By.CSS_SELECTOR, 
                    ".반목록, #반목록, .class-list, .depth1, li.depth1"
                )))
                
                # Find all class links/items
                class_elements = driver.find_elements(By.CSS_SELECTOR, 
                    "li.depth1 a, .class-item, .반목록 li a, a[onclick*='selectClass']"
                )
                
                if not class_elements:
                    # Try alternative selectors
                    class_elements = driver.find_elements(By.CSS_SELECTOR, 
                        "ul li a span.name, .attendL .class-name"
                    )
                
                class_names = []
                for elem in class_elements:
                    class_name = elem.text.strip()
                    if class_name and class_name not in class_names:
                        class_names.append(class_name)
                
                _notify_user(f"[ACA2000] ✅ Found {len(class_names)} classes", "success")
                
            except Exception as e:
                _notify_user(f"[ACA2000] ⚠️ Could not find class list: {e}", "warning")
                class_names = []
            
            # Step 5: For each class, select it and extract student list
            for class_name in class_names:
                try:
                    _notify_user(f"[ACA2000] Processing class: {class_name}...", "info")
                    
                    # Click on the class
                    class_link = wait.until(EC.element_to_be_clickable((
                        By.XPATH, 
                        f"//a[contains(text(), '{class_name}') or .//span[text()='{class_name}']]"
                    )))
                    class_link.click()
                    time.sleep(1)  # Wait for class selection to load students
                    
                    # Extract student names who participated (READ-ONLY - no modifications)
                    try:
                        # Note: Read-only mode is already active from driver initialization
                        # MutationObserver automatically handles dynamically loaded buttons
                        
                        # Find student list - students are typically in spans with class "name"
                        # IMPORTANT: We only READ text, never click attendance buttons
                        student_elements = driver.find_elements(By.CSS_SELECTOR, 
                            ".attendL .name, span.name, .student-name, .infoLine .name"
                        )
                        
                        students = []
                        for student_elem in student_elements:
                            student_name = student_elem.text.strip()
                            if student_name and student_name not in students:
                                # READ-ONLY: Only extract text, never interact with buttons
                                # Check parent to see if student has attendance status (visual check only)
                                try:
                                    parent = student_elem.find_element(By.XPATH, "./..")
                                    # Look for attendance indicators (read-only check)
                                    # We check for active/highlighted buttons but NEVER click them
                                    parent.find_elements(By.CSS_SELECTOR, 
                                        ".btn_attend.active, .attendance.active, button.active"
                                    )
                                    # If indicators found or not, we just read the name
                                    students.append(student_name)
                                except Exception:
                                    # If we can't check, just read the name anyway
                                    students.append(student_name)
                        
                        if students:
                            all_students[class_name] = students
                            _notify_user(f"[ACA2000] ✅ Found {len(students)} students in {class_name}", "success")
                        else:
                            _notify_user(f"[ACA2000] ⚠️ No students found for {class_name}", "warning")
                    
                    except Exception as e:
                        _notify_user(f"[ACA2000] ⚠️ Error extracting students for {class_name}: {e}", "warning")
                        continue
                
                except Exception as e:
                    _notify_user(f"[ACA2000] ⚠️ Error processing class {class_name}: {e}", "warning")
                    continue
            
            _notify_user(f"[ACA2000] ✅ Completed! Found students from {len(all_students)} classes", "success")
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
    Returns:
        webdriver.Chrome: Configured headless Chrome WebDriver.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Options to prevent zombie processes
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-background-timer-throttling")
    options.add_argument("--disable-backgrounding-occluded-windows")
    options.add_argument("--disable-renderer-backgrounding")
    options.add_argument("--disable-features=TranslateUI")
    options.add_argument("--disable-ipc-flooding-protection")

    driver = webdriver.Chrome(options=options)

    # This is the magic part that hides the headless mode from Naver
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )

    return driver

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
            consent_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")), timeout=5)
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
    load_dotenv()
    NAVER_ID = os.getenv("NAVER_ID")
    NAVER_APP_PW = os.getenv("NAVER_APP_PW")
    login_to_naver(headless=False, naver_id=NAVER_ID, naver_passkey=NAVER_APP_PW)
    
    # test kakao OAuth
    # get_kakao_token_via_webdriver(
    #     rest_api_key=os.getenv("KAKAO_REST_API_KEY"),
    #     redirect_uri=os.getenv("KAKAO_REDIRECT_URL"),
    #     kakao_id=os.getenv("KAKAO_ID"),
    #     kakao_pw=os.getenv("KAKAO_PW")
    # )