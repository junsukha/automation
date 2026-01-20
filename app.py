from dotenv import load_dotenv
import streamlit as st
import sys
import os
import time
from utils import (get_all_senders_clean, 
                   send_kakao_notification,
                   send_naver_report,
                   get_students_from_aca2000,)
# Selenium imports - uncomment when get_driver() is used
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from webdriver_manager.chrome import ChromeDriverManager


# Check for --test argument or TEST_MODE environment variable to enable secrets pre-filling
USE_TEST_MODE = "--test" in sys.argv or os.getenv("TEST_MODE", "").lower() in ("true", "1", "yes")

# 1. Page Configuration
st.set_page_config(page_title="Academy Automation Agent", page_icon="🤖")

# 3. Main UI
st.title("🤖 Academy Automation Agent")
st.write("Sync Naver Emails with ACA2000 and get notifications via KakaoTalk.")

# Helper function to safely get value from st.secrets
def get_secret(key, default=""):
    """Get value from Streamlit secrets (.streamlit/secrets.toml for local, st.secrets for cloud)."""
    try:
        return st.secrets.get(key, default)
    except (AttributeError, KeyError):
        return default

# Section 1: Naver
st.header("📧 1. Naver Configuration")
# Only pre-fill when --test flag is used
naver_id_value = get_secret("NAVER_ID") if USE_TEST_MODE else ""
naver_pw_value = get_secret("NAVER_APP_PW") if USE_TEST_MODE else ""

if USE_TEST_MODE and (naver_id_value or naver_pw_value):
    st.caption("💡 Test mode: Credentials pre-filled from secrets. You can edit them if needed.")
col1, col2 = st.columns(2)
with col1:
    user_email_id = st.text_input("Naver ID", value=naver_id_value, placeholder="without @naver.com")
with col2:
    user_app_pw = st.text_input("Naver App Password", value=naver_pw_value, type="password", help="Use a 16-digit App Password, not your login PW.")

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
# Only pre-fill when --test flag is used
kakao_api_key_value = get_secret("KAKAO_REST_API_KEY") if USE_TEST_MODE else ""
kakao_redirect_value = get_secret("KAKAO_REDIRECT_URL") if USE_TEST_MODE else ""
kakao_id_value = get_secret("KAKAO_ID") if USE_TEST_MODE else ""
kakao_pw_value = get_secret("KAKAO_PW") if USE_TEST_MODE else ""

if USE_TEST_MODE and (kakao_api_key_value or kakao_id_value):
    st.caption("💡 Test mode: Credentials pre-filled from secrets. You can edit them if needed.")
kakao_api_key = st.text_input("Kakao REST API Key", value=kakao_api_key_value, type="password")
kakao_registered_redirect_url = st.text_input("Kakao Redirect URL", value=kakao_redirect_value, help="The Redirect URL you set in Kakao Developers (e.g., https://localhost:5000/)")
kakao_id = st.text_input("Kakao Login ID (Email or Phone)", value=kakao_id_value)
kakao_pw = st.text_input("Kakao Login Password", value=kakao_pw_value, type="password")

st.divider()

# Step 1: Fetch classes from ACA2000 first
if st.button('🔍 Fetch Classes from ACA2000'):
    with st.spinner("Connecting to ACA2000..."):
        try:
            all_students = get_students_from_aca2000()
            if all_students:
                st.session_state.all_students = all_students
                st.success(f"✅ Found {len(all_students)} classes!")
            else:
                st.error("❌ No classes found or connection failed.")
        except Exception as e:
            st.error(f"❌ Error: {e}")

# Step 2: Show class selection if classes are fetched
if 'all_students' in st.session_state and st.session_state.all_students:
    all_students = st.session_state.all_students
    class_info = {class_name: len(students) for class_name, students in all_students.items()}
    
    with st.form("class_selection_form"):
        st.write(f"**Select Classes to Include ({len(class_info)} available):**")
        
        # Display checkboxes in 3 columns
        cols = st.columns(3)
        class_selections = {}
        
        for idx, (class_name, count) in enumerate(class_info.items()):
            col_idx = idx % 3
            class_selections[class_name] = cols[col_idx].checkbox(
                f"{class_name} ({count})",
                value=True,  # All checked by default
                key=f"class_{class_name}"
            )
        
        # Submit button
        if st.form_submit_button("🚀 Run Automation with Selected Classes"):
            selected_classes = [name for name, selected in class_selections.items() if selected]
            if selected_classes:
                st.session_state.selected_classes = selected_classes
                st.session_state.run_automation = True
            else:
                st.warning("⚠️ Please select at least one class.")

# Step 3: Run automation if classes are selected
if st.session_state.get('run_automation', False):
    selected_classes = st.session_state.selected_classes
    all_students = st.session_state.all_students
    
    # Filter student list based on selection
    student_list = {name: all_students[name] for name in selected_classes}
    # Validation
    if not user_email_id or not user_app_pw:
        st.warning("Please enter both your Naver ID and App Password.")
        st.stop()
    if not kakao_id or not kakao_pw:
        st.warning("Please enter both your Kakao ID and Password.")
        st.stop()
    if not kakao_api_key or not kakao_registered_redirect_url:
        st.warning("Please enter both your Kakao API Key and Redirect URL.")
        st.stop()
    
    # Initialize variables
    success = False
    senders = set()
    kakao_success = False

    try:
        with st.status("Agent is running...", expanded=True) as status:
            # Step 1: Read Emails
            st.write("Reading Naver emails...")
            senders = get_all_senders_clean(user_email_id, user_app_pw)
            st.write(f"✅ Found {len(senders)} recent senders.")
            
            # Step 2: Show selected classes
            st.write(f"✅ Processing {len(student_list)} selected classes with {sum(len(s) for s in student_list.values())} total students")
            
            
            # Step 3: Send Report Email
            # Build report content with both email senders and ACA2000 students
            report_content = "The Academy Agent has finished syncing.\n\n"
            
            # Add email senders section
            report_content += f"📧 Email Senders ({len(senders)}):\n"
            report_content += "\n".join(f"  - {sender}" for sender in sorted(senders))
            report_content += "\n\n"
            
            # Add ACA2000 students section
            report_content += "🎓 ACA2000 Students (Latest Saturday):\n"
            for class_name, students in student_list.items():
                report_content += f"\n{class_name} ({len(students)} students):\n"
                report_content += "\n".join(f"  - {student}" for student in students)
                report_content += "\n"
            
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
        # Reset state on error
        st.session_state.run_automation = False
        st.stop()
        
    # This remains outside to give a clear final visual confirmation
    if success:
        st.success("Automation finished and report sent!")
        st.balloons()  # Optional fun effect for your user
    else:
        st.warning("Automation finished, but we couldn't send the email.")
    
    # Reset state after completion
    st.session_state.run_automation = False
    if st.button("Run Again"):
        st.session_state.clear()
        st.rerun()
        
    # Table Results
    if senders:
        st.subheader("Results")
        st.dataframe([{"Sender": s, "Status": "Processed"} for s in senders], width='stretch')