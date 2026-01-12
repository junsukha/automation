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


def get_students_from_aca2000(driver):
    # Placeholder function to simulate fetching student data
    return ["Student A", "Student B", "Student C"]




def get_headless_driver():
    options = Options()
    
    # The primary command for headless
    options.add_argument("--headless=new") 
    
    # Essential settings for servers/background stability
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    
    # Optional: Set a window size so the "invisible" browser 
    # doesn't default to a tiny mobile view
    options.add_argument("--window-size=1920,1080")

    # Optional: Pretend to be a real user to avoid bot detection
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=options
    )
    return driver

def login_to_naver():
    # 1. Setup Chrome Options
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless") # Run without window (don't use for testing login)
    
    # driver = get_headless_driver() # Use this for headless mode
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
        driver.execute_script("arguments[0].value = arguments[1];", id_input, NAVER_ID)

        # 3. Wait for PW input
        pw_input = wait.until(EC.element_to_be_clickable((By.NAME, "pw")))
        driver.execute_script("arguments[0].value = arguments[1];", pw_input, NAVER_PW)

        # 4. Wait for and click Login Button
        login_btn = wait.until(EC.element_to_be_clickable((By.ID, "log.login")))
        login_btn.click()

        # 5. Verify login by waiting for a specific element on the HOME page
        # This confirms we are actually logged in before the script continues
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "MyView-module__my_info___Xm677")))
        print("✅ Successfully logged in and redirected!")

    except Exception as e:
        print(f"❌ Automation timed out or failed: {e}")
        driver.save_screenshot("debug_timeout.png")
    # Keeping the browser open for you to see the result
    input("Press Enter to close the browser...")
    driver.quit()