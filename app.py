import streamlit as st
import time
from utils import (get_all_senders_clean, send_kakao_notification,
                   send_naver_report,)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from PyKakao import Message  # Import PyKakao

# 1. Page Configuration
st.set_page_config(page_title="Academy Automation Agent", page_icon="🤖")

# 2. Browser Setup (Headless for Cloud)
@st.cache_resource
def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # On Streamlit Cloud, it uses the Chromium installed via packages.txt
    try:
        # Try local/standard path first
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    except:  # noqa: E722
        # Fallback for Linux Server environment
        driver = webdriver.Chrome(options=options)
    return driver

# 3. Main UI
st.title("🤖 Academy Automation Agent")
st.write("Sync Naver Emails with ACA2000 and get notifications via KakaoTalk.")

# Section 1: Naver
st.header("📧 1. Naver Configuration")
col1, col2 = st.columns(2)
with col1:
    user_email_id = st.text_input("Naver ID", placeholder="without @naver.com")
with col2:
    user_app_pw = st.text_input("Naver App Password", type="password", help="Use a 16-digit App Password, not your login PW.")

if st.button("🔍 Test Naver Login"):
    try:
        from imap_tools import MailBox
        with MailBox('imap.naver.com').login(user_email_id, user_app_pw):
            st.success("✅ Naver IMAP Ready!")
    except Exception as e:
        st.error(f"❌ Login Failed. Check ID/App PW. {e}")

st.divider()

# st.write("Sync Naver Emails with ACA2000.")

# st.subheader("🔑 Authentication")
# user_email_id = st.text_input("Naver ID") # st.secrets["NAVER_ID"]
# # type="password" hides the characters as they type
# user_app_pw = st.text_input("Naver App Password", type="password") # st.secrets["NAVER_APP_PW"]

# Section 2: KakaoTalk (Right below Naver)
# Ask for Kakao REST API Key and Redirect URL from Kakao Developers
st.header("💬 2. KakaoTalk Notification (Optional)")
kakao_api_key = st.text_input("Kakao REST API Key", type="password")
kakao_registered_redirect_url = st.text_input("Kakao Redirect URL", help="The Redirect URL you set in Kakao Developers (e.g., https://localhost:5000/)")
kakao_id = st.text_input("Kakao Login ID (Email or Phone)")
kakao_pw = st.text_input("Kakao Login Password", type="password")
# below will be replaced with automation
# if kakao_api_key:
#     # We initialize just to get the URL
#     temp_api = Message(service_key=kakao_api_key)
#     kakao_auth_url = temp_api.get_url_for_generating_code()
    
#     st.info("To enable Kakao alerts, follow these two steps:")
#     st.markdown(f"1. [**Click here to Login to Kakao**]({kakao_auth_url})")
#     kakao_redirect_url = st.text_input("2. Paste the URL of the page you were redirected to:")
# else:
#     st.caption("Leave API Key blank to skip Kakao notifications.")

st.divider()

if st.button('🚀 Run Automation'):
    # Validation: Ensure they didn't leave the fields empty
    if not user_email_id or not user_app_pw:
        st.warning("Please enter both your Naver ID and App Password.")
        st.stop()

    with st.status("Agent is running...", expanded=True) as status:
        # Step 1: Read Emails
        st.write("Reading Naver emails...")
        # Note: We pass the credentials from st.secrets to your function
        senders = get_all_senders_clean(user_email_id, user_app_pw)
        st.write(f"✅ Found {len(senders)} recent senders.")

        # Step 2: ACA2000 (Add your Selenium logic here later)
        st.write("Connecting to ACA2000...")
        # driver = get_driver()
        # driver.get("ACA2000_URL_HERE")
        # student_list = get_students_from_aca2000(driver)  # Placeholder function
        time.sleep(1)  # Placeholder
        
        # Step 3: Send Report Email
        report_content = "The Academy Agent has finished syncing.\n\nNames processed:\n" + "\n".join(senders)
        success = send_naver_report(user_email_id, user_app_pw, user_email_id, report_content)
        if success:
            st.write("✅ Email delivered successfully.")
        else:
            # We don't use st.error inside status because it might break the layout
            st.write("⚠️ Email notification failed (Check settings).")
            
 

        # Step 4: Send KakaoTalk Message if Configured
        st.write("Sending report to KakaoTalk...")
        kakao_success = send_kakao_notification(kakao_api_key, 
                                                kakao_registered_redirect_url, report_content, kakao_id, kakao_pw)
        if kakao_success:
            st.write("✅ Kakao message sent!")
        else:
            st.write("⚠️ Kakao message failed (Check API key and redirect URL).")
       
            
        status.update(label="All Tasks Complete!", state="complete", expanded=False)
        
    # This remains outside to give a clear final visual confirmation
    if success:
        st.success("Automation finished and report sent!")
        st.balloons() # Optional fun effect for your user
    else:
        st.warning("Automation finished, but we couldn't send the email.")
        st.stop()
        
    # Table Results
    st.subheader("Results")
    st.dataframe([{"Sender": s, "Status": "Processed"} for s in senders], width='stretch')