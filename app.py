import streamlit as st
import time
from my_email_script import get_all_senders_clean
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

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
    except:
        # Fallback for Linux Server environment
        driver = webdriver.Chrome(options=options)
    return driver

# 3. Main UI
st.title("🤖 Academy Automation Agent")
st.write("Sync Naver Emails with ACA2000.")

st.subheader("🔑 Authentication")
user_email_id = st.text_input("Naver ID") # st.secrets["NAVER_ID"]
# type="password" hides the characters as they type
user_app_pw = st.text_input("Naver App Password", type="password") # st.secrets["NAVER_APP_PW"]

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
        driver = get_driver()
        # driver.get("ACA2000_URL_HERE")
        time.sleep(2) # Placeholder
        
        status.update(label="Sync Complete!", state="complete", expanded=False)

    st.success("Automation finished successfully!")
    
    # Table Results
    st.subheader("Results")
    st.table([{"Sender": s, "Status": "Processed"} for s in senders])