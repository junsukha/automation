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

@contextmanager
def get_driver_context(headless=False, stealth=False):
    """
    Context manager for WebDriver that ensures proper cleanup.
    
    Usage:
        with get_driver_context(headless=True) as driver:
            driver.get("https://example.com")
            # driver is automatically closed when exiting the context
    
    Args:
        headless (bool): Whether to run in headless mode
        stealth (bool): Whether to use stealth mode (for headless)
    
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
    
    
def get_students_from_aca2000():
    # TODO: Implement actual logic to fetch student data from ACA2000
    # Placeholder function to simulate fetching student data
    return ["Student A", "Student B", "Student C"]




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
    with get_driver_context(headless=headless, stealth=stealth) as driver:
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
    
    with get_driver_context(headless=False, stealth=False) as driver:
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
    # NAVER_ID = os.getenv("NAVER_ID")
    # NAVER_APP_PW = os.getenv("NAVER_APP_PW")
    # login_to_naver(headless=False, naver_id=NAVER_ID, naver_passkey=NAVER_APP_PW)
    
    # test kakao OAuth
    get_kakao_token_via_webdriver(
        rest_api_key=os.getenv("KAKAO_REST_API_KEY"),
        redirect_uri=os.getenv("KAKAO_REDIRECT_URL"),
        kakao_id=os.getenv("KAKAO_ID"),
        kakao_pw=os.getenv("KAKAO_PW")
    )