from dotenv import load_dotenv
import streamlit as st
import sys
import os
import time
from datetime import datetime, timedelta
from utils import (
    get_class_list_from_aca2000,
    get_students_for_classes,
    fetch_naver_email,
    find_missing_students,
)
# Selenium imports - uncomment when get_driver() is used
# from selenium import webdriver
# from selenium.webdriver.chrome.service import Service
# from selenium.webdriver.chrome.options import Options
# from webdriver_manager.chrome import ChromeDriverManager


# Check for --test argument or TEST_MODE environment variable to enable secrets pre-filling
USE_TEST_MODE = "--test" in sys.argv or os.getenv("TEST_MODE", "").lower() in (
    "true",
    "1",
    "yes",
)

# Page Configuration
st.set_page_config(page_title="Academy Automation Agent", page_icon="🤖")

# Main UI
st.title("🤖 Academy Automation Agent")
st.write("Sync Naver Emails with ACA2000 Student Lists")


# Helper function to safely get value from st.secrets
def get_secret(key, default=""):
    """Get value from Streamlit secrets (.streamlit/secrets.toml for local, st.secrets for cloud)."""
    try:
        return st.secrets.get(key, default)
    except (AttributeError, KeyError):
        return default

# Load Naver credentials from secrets
user_email_id = get_secret("NAVER_ID")
user_pw = get_secret("NAVER_PW")

# # Quick IMAP connectivity check
# if st.button("🔍 Test Naver Login"):
#     try:
#         from imap_tools import MailBox

#         with MailBox("imap.naver.com").login(user_email_id, user_app_pw):
#             st.success("✅ Naver IMAP Ready!")
#     except Exception as e:
#         st.error(f"❌ Login Failed. Check ID/App PW. {e}")

# st.divider()

# # Section 2: KakaoTalk (Right below Naver)
# # Ask for Kakao REST API Key and Redirect URL from Kakao Developers
# st.header("💬 2. KakaoTalk Notification (Optional)")
# # Only pre-fill when --test flag is used
# kakao_api_key_value = get_secret("KAKAO_REST_API_KEY") if USE_TEST_MODE else ""
# kakao_redirect_value = get_secret("KAKAO_REDIRECT_URL") if USE_TEST_MODE else ""
# kakao_id_value = get_secret("KAKAO_ID") if USE_TEST_MODE else ""
# kakao_pw_value = get_secret("KAKAO_PW") if USE_TEST_MODE else ""

# if USE_TEST_MODE and (kakao_api_key_value or kakao_id_value):
#     st.caption(
#         "💡 Test mode: Credentials pre-filled from secrets. You can edit them if needed."
#     )
# kakao_api_key = st.text_input(
#     "Kakao REST API Key", value=kakao_api_key_value, type="password"
# )
# kakao_registered_redirect_url = st.text_input(
#     "Kakao Redirect URL",
#     value=kakao_redirect_value,
#     help="The Redirect URL you set in Kakao Developers (e.g., https://localhost:5000/)",
# )
# kakao_id = st.text_input("Kakao Login ID (Email or Phone)", value=kakao_id_value)
# kakao_pw = st.text_input("Kakao Login Password", value=kakao_pw_value, type="password")

# st.divider()

# Step 1: Fetch class list from ACA2000 (login + scrape class names, keep driver alive)
if st.button("🔍 Fetch Classes from ACA2000"):
    # Clear previous logs
    st.session_state.process_logs = []

    # Clean up any stale driver from previous run
    if "aca_driver" in st.session_state and st.session_state.aca_driver:
        try:
            st.session_state.aca_driver.quit()
        except Exception:
            pass
        st.session_state.aca_driver = None

    with st.status("Connecting to ACA2000...", expanded=True) as status:
        try:
            class_info, driver = get_class_list_from_aca2000(headless=True)
            if class_info and driver:
                st.session_state.class_info = class_info
                st.session_state.aca_driver = driver
                st.session_state.fetch_status = f"✅ Found {len(class_info)} classes!"
                try:
                    driver.minimize_window()  # Only works in non-headless mode
                except Exception:
                    pass
                status.update(label=st.session_state.fetch_status, state="complete", expanded=False)
            else:
                st.session_state.fetch_status = "❌ No classes found or connection failed."
                status.update(label=st.session_state.fetch_status, state="error", expanded=False)
        except Exception as e:
            st.session_state.fetch_status = f"❌ Error: {e}"
            status.update(label=st.session_state.fetch_status, state="error", expanded=False)

# Show persistent logs from all steps
if "process_logs" in st.session_state and st.session_state.process_logs:
    with st.expander("📋 Process Logs", expanded=False):
        for log in st.session_state.process_logs:
            msg, msg_type = log["message"], log["type"]
            if msg_type == "error":
                st.error(msg)
            elif msg_type == "success":
                st.success(msg)
            elif msg_type == "warning":
                st.warning(msg)
            else:
                st.info(msg)

# Step 2: Select classes, fetch students + emails, and compare
if "class_info" in st.session_state and st.session_state.class_info:
    class_info = st.session_state.class_info

    with st.form("class_selection_form"):
        st.write(
            f"**Select Classes to Include ({len(class_info)} available):**"
        )

        # Display checkboxes in 3 columns
        cols = st.columns(3)
        class_selections = {}

        for idx, class_name in enumerate(class_info.keys()):
            col_idx = idx % 3
            class_selections[class_name] = cols[col_idx].checkbox(
                class_name,
                value=False,
                key=f"class_{class_name}",
            )

        # Date range for email filtering
        st.write("**Email Date Range:**")
        date_cols = st.columns(2)
        email_start_date = date_cols[0].date_input("Start Date", value=datetime.now().date() - timedelta(days=7))
        email_end_date = date_cols[1].date_input("End Date", value=datetime.now().date())

        # Submit button
        submitted = st.form_submit_button("🚀 Find lazy students from Selected Classes")

    # On submit: fetch students for selected classes, fetch emails, compare, display
    if submitted:
        selected_classes = [
            name for name, selected in class_selections.items() if selected
        ]
        if not selected_classes:
            st.warning("⚠️ Please select at least one class.")
            st.stop()
        if not user_email_id or not user_pw:
            st.warning("Please enter both your Naver ID and Password.")
            st.stop()

        # Build selected class_ids dict
        selected_class_ids = {
            name: class_info[name]
            for name in selected_classes
        }

        try:
            with st.status("Agent is running...", expanded=True) as status:
                # Fetch students for selected classes using existing driver
                st.write("Fetching students for selected classes...")
                driver = st.session_state.pop("aca_driver", None)
                if not driver:
                    st.error("❌ ACA2000 session expired. Please fetch classes again.")
                    st.stop()
                student_list = get_students_for_classes(driver, selected_class_ids)
                # Driver is now quit by get_students_for_classes
                total_students = sum(len(s) for s in student_list.values())
                st.write(
                    f"✅ Found {total_students} students in {len(student_list)} classes"
                )

                # TODO: Uncomment this check after verifying Naver login works
                # if total_students == 0:
                #     st.warning("⚠️ No students found in selected classes. Check ACA2000 data.")
                #     st.stop()

                # Fetch unread emails via Selenium (subject, content, attachments)
                st.write("Reading Naver emails...")
                emails = fetch_naver_email(
                    headless=False, naver_id=user_email_id, naver_passkey=user_pw,
                    start_date=email_start_date, end_date=email_end_date
                )
                senders = {e["sender"] for e in emails}
                st.write(f"✅ Found {len(emails)} emails from {len(senders)} senders.")

                # Match student names (Korean, 2-3 chars) against email text
                st.write("Comparing students against emails...")
                results = find_missing_students(student_list, emails)
                total_missing = sum(len(r["missing"]) for r in results.values())
                st.write(f"✅ Found {total_missing} students who didn't send an email.")

                status.update(
                    label="All Tasks Complete!", state="complete", expanded=False
                )

        except Exception as e:
            st.error(f"❌ An error occurred during automation: {e}")
            st.exception(e)
            # Clean up driver if still alive
            if "aca_driver" in st.session_state and st.session_state.aca_driver:
                try:
                    st.session_state.aca_driver.quit()
                except Exception:
                    pass
                st.session_state.pop("aca_driver", None)
            st.stop()

        st.success("Automation finished!")
        st.balloons()

        # Block 1: Per-class breakdown showing matched (student → email) and missing
        st.subheader("Results")
        for class_name, data in results.items():
            st.markdown(f"**{class_name}**")
            if data["matched"]:
                for student, subject in data["matched"]:
                    st.markdown(f"- ✅ {student} → _{subject}_")
            if data["missing"]:
                for s in data["missing"]:
                    st.markdown(f"- ❌ {s}")
            # example output:
            # M5 월금
            # - ✅ 김빛나 → FW: 첨부파일테스트 (2)
            # - ✅ 이현수 → 과제 제출합니다
            # - ❌ 박서준

        # Block 2: Condensed list of only missing students for quick reference
        if total_missing > 0:
            st.divider()
            st.subheader(f"Missing Homework ({total_missing} students)")
            for class_name, data in results.items():
                if data["missing"]:
                    st.markdown(f"**{class_name}:**")
                    for s in data["missing"]:
                        st.markdown(f"- {s}")
            # example output:
            # Missing Homework (1 students)
            # M5 월금:
            # - 박서준

        else:
            st.divider()
            st.markdown("All students submitted homework!")
