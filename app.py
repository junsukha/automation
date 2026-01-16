import streamlit as st
import time
from utils import (get_all_senders_clean, send_kakao_notification,
                   send_naver_report,)
# Selenium imports - uncomment when get_driver() is used
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from webdriver_manager.chrome import ChromeDriverManager

# 1. Page Configuration
st.set_page_config(page_title="Academy Automation Agent", page_icon="🤖")

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

# Section 2: KakaoTalk (Right below Naver)
# Ask for Kakao REST API Key and Redirect URL from Kakao Developers
st.header("💬 2. KakaoTalk Notification (Optional)")
kakao_api_key = st.text_input("Kakao REST API Key", type="password")
kakao_registered_redirect_url = st.text_input("Kakao Redirect URL", help="The Redirect URL you set in Kakao Developers (e.g., https://localhost:5000/)")
kakao_id = st.text_input("Kakao Login ID (Email or Phone)")
kakao_pw = st.text_input("Kakao Login Password", type="password")

st.divider()

if st.button('🚀 Run Automation'):
    # Validation: Ensure they didn't leave the fields empty
    if not user_email_id or not user_app_pw:
        st.warning("Please enter both your Naver ID and App Password.")
        st.stop()

    # Initialize variables to avoid scope issues
    success = False
    senders = set()
    kakao_success = False

    try:
        with st.status("Agent is running...", expanded=True) as status:
            # Step 1: Read Emails
            st.write("Reading Naver emails...")
            senders = get_all_senders_clean(user_email_id, user_app_pw)
            st.write(f"✅ Found {len(senders)} recent senders.")

            # Step 2: ACA2000 (Add your Selenium logic here later)
            st.write("Connecting to ACA2000...")
            # driver = get_driver()
            # try:
            #     driver.get("ACA2000_URL_HERE")
            #     student_list = get_students_from_aca2000(driver)  # Placeholder function
            # finally:
            #     driver.quit()  # Always cleanup driver
            time.sleep(1)  # Placeholder
            
            # Step 3: Send Report Email
            report_content = "The Academy Agent has finished syncing.\n\nNames processed:\n" + "\n".join(senders)
            success = send_naver_report(user_email_id, user_app_pw, user_email_id, report_content)
            if success:
                st.write("✅ Email delivered successfully.")
            else:
                st.write("⚠️ Email notification failed (Check settings).")

            # Step 4: Send KakaoTalk Message if Configured
            if kakao_api_key and kakao_registered_redirect_url:
                st.write("Sending report to KakaoTalk...")
                kakao_success = send_kakao_notification(
                    kakao_api_key, 
                    kakao_registered_redirect_url, 
                    report_content, 
                    kakao_id, 
                    kakao_pw
                )
                if kakao_success:
                    st.write("✅ Kakao message sent!")
                else:
                    st.write("⚠️ Kakao message failed (Check API key and redirect URL).")
            else:
                st.write("⏭️ Skipping Kakao notification (API key or redirect URL not provided).")
                   
            status.update(label="All Tasks Complete!", state="complete", expanded=False)
            
    except Exception as e:
        st.error(f"❌ An error occurred during automation: {e}")
        st.exception(e)
        st.stop()
        
    # This remains outside to give a clear final visual confirmation
    if success:
        st.success("Automation finished and report sent!")
        st.balloons()  # Optional fun effect for your user
    else:
        st.warning("Automation finished, but we couldn't send the email.")
        
    # Table Results
    if senders:
        st.subheader("Results")
        st.dataframe([{"Sender": s, "Status": "Processed"} for s in senders], width='stretch')