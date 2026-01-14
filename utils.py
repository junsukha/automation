# import smtplib
from email.message import EmailMessage
import streamlit as st

import smtplib
import ssl
    
from imap_tools import MailBox, AND
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText

import os
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# deprecated
def send_naver_report(user_id, user_pw, recipient_user_id, report_text):
    """
    Sends an email report via Naver's SMTP server.
     Parameters:
         user_id (str): Naver email ID (without @naver.com).
         user_pw (str): Naver email password or app password.
         recipient_user_id (str): Recipient's Naver email ID (without @naver.com).
         report_text (str): The content of the email report.

     Returns:
         bool: True if email sent successfully, False otherwise.
    """
    msg = EmailMessage()
    msg.set_content(report_text)
    msg['Subject'] = '✅ Academy Sync Report'
    msg['From'] = f"{user_id}@naver.com"
    msg['To'] = f"{recipient_user_id}@naver.com"

    context = ssl.create_default_context()

    try:
        # Use SMTP_SSL with port 465 (direct SSL connection)
        with smtplib.SMTP_SSL('smtp.naver.com', 465, context=context, timeout=10) as smtp:
            smtp.login(user_id, user_pw)
            smtp.send_message(msg)
        return True
    except smtplib.SMTPAuthenticationError:
        st.error("Authentication failed. Check your Naver ID and password.")
        return False
    except smtplib.SMTPException as e:
        st.error(f"SMTP error occurred: {e}")
        return False
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False
    

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
        st.error(f"Email error: {e}")
        return False
    
    


def get_students_from_aca2000(driver):
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

from selenium_stealth import stealth

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

def login_to_naver(headless=False, naver_id=None, naver_passkey=None):
    """
    Logs into Naver using Selenium WebDriver.
    Parameters:
        headless (bool): Whether to run the browser in headless mode.
        naver_id (str): Naver login ID.
        naver_passkey (str): Naver login password or app password.
    """
    # 1. Setup Chrome Options
    options = webdriver.ChromeOptions()

    if headless:
        driver = get_headless_stealth_driver() # Use this for headless mode
    else:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), 
            options=options
        )
    
    # Set a max wait time of 10 seconds
    wait = WebDriverWait(driver, 10)
    try:
        driver.get("https://nid.naver.com/nidlogin.login")

        # 1. Wait until the ID input is actually clickable
        id_input = wait.until(EC.element_to_be_clickable((By.NAME, "id")))
        
        # 2. Instead of time.sleep, use JS injection for safety on Naver
        # check if naver_id and naver_passkey are defined
        if not naver_id or not naver_passkey:
            raise ValueError("NAVER_ID and NAVER_PW must be set before calling login_to_naver()")
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
    driver.quit()
    
if __name__ == "__main__":
    load_dotenv()
    NAVER_ID = os.getenv("NAVER_ID")
    NAVER_APP_PW = os.getenv("NAVER_APP_PW")
    login_to_naver(headless=False, naver_id=NAVER_ID, naver_passkey=NAVER_APP_PW)