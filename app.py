from dotenv import load_dotenv
import streamlit as st
import sys
import os
import time
from utils import (get_students_from_aca2000,
                   get_class_list_from_aca2000,
                   get_students_for_classes,
                   fetch_naver_email,
                   find_missing_students,)
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

# Step 1: Fetch all classes and students from ACA2000 (one visit, efficient)
if st.button('🔍 Fetch Classes & Students from ACA2000'):
    with st.spinner("Connecting to ACA2000..."):
        try:
            all_students = get_students_from_aca2000()
            if all_students:
                st.session_state.all_students = all_students
                st.success(f"✅ Found {len(all_students)} classes with {sum(len(s) for s in all_students.values())} total students!")
            else:
                st.error("❌ No classes found or connection failed.")
        except Exception as e:
            st.error(f"❌ Error: {e}")

# Step 2: Show class selection if data is fetched
if 'all_students' in st.session_state and st.session_state.all_students:
    all_students = st.session_state.all_students
    class_info = {class_name: len(students) for class_name, students in all_students.items()}
    
    with st.form("class_selection_form"):
        st.write(f"**Select Classes to Include in Report ({len(class_info)} available):**")
        
        # Display checkboxes in 3 columns
        cols = st.columns(3)
        class_selections = {}
        
        for idx, (class_name, count) in enumerate(class_info.items()):
            col_idx = idx % 3
            class_selections[class_name] = cols[col_idx].checkbox(
                f"{class_name} ({count})",
                value=False,  # All unchecked by default
                key=f"class_{class_name}"
            )
        
        # Submit button
        submitted = st.form_submit_button("🚀 Run Automation with Selected Classes")

    if submitted:
        selected_classes = [name for name, selected in class_selections.items() if selected]
        if not selected_classes:
            st.warning("⚠️ Please select at least one class.")
            st.stop()
        if not user_email_id or not user_app_pw:
            st.warning("Please enter both your Naver ID and App Password.")
            st.stop()

        student_list = {name: all_students[name] for name in selected_classes if name in all_students}

        try:
            with st.status("Agent is running...", expanded=True) as status:
                st.write("Reading Naver emails...")
                emails = fetch_naver_email(naver_id=user_email_id, naver_passkey=user_app_pw)
                senders = {e['sender'] for e in emails}
                st.write(f"✅ Found {len(emails)} emails from {len(senders)} senders.")

                st.write(f"✅ Using {len(student_list)} selected classes with {sum(len(s) for s in student_list.values())} total students")

                st.write("Comparing students against emails...")
                results = find_missing_students(student_list, emails)
                total_missing = sum(len(r['missing']) for r in results.values())
                st.write(f"✅ Found {total_missing} students who didn't send an email.")

                status.update(label="All Tasks Complete!", state="complete", expanded=False)

        except Exception as e:
            st.error(f"❌ An error occurred during automation: {e}")
            st.exception(e)
            st.stop()

        st.success("Automation finished!")
        st.balloons()

        # Block 1: Comparison results per class
        st.subheader("Results")
        for class_name, data in results.items():
            st.markdown(f"**{class_name}**")
            if data['matched']:
                for student, subject in data['matched']:
                    st.markdown(f"- ✅ {student} → _{subject}_")
            if data['missing']:
                for s in data['missing']:
                    st.markdown(f"- ❌ {s}")
            # example output:
            # M5 월금
            # - ✅ 김빛나 → FW: 첨부파일테스트 (2)
            # - ✅ 이현수 → 과제 제출합니다
            # - ❌ 박서준

        # Block 2: Missing students summary
        if total_missing > 0:
            st.divider()
            st.subheader(f"Missing Homework ({total_missing} students)")
            for class_name, data in results.items():
                if data['missing']:
                    st.markdown(f"**{class_name}:**")
                    for s in data['missing']:
                        st.markdown(f"- {s}")
            # example output:
            # Missing Homework (1 students)
            # M5 월금:
            # - 박서준
            
        else:
            st.divider()
            st.markdown("All students submitted homework!")