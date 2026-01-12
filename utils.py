import smtplib
from email.message import EmailMessage
import streamlit as st

def send_naver_report(user_id, user_pw, recipient_email, report_text):
    msg = EmailMessage()
    msg.set_content(report_text)
    msg['Subject'] = '✅ [Academy Agent] Sync Report'
    msg['From'] = f"{user_id}@naver.com"
    msg['To'] = recipient_email

    # Connect to Naver SMTP server
    try:
        with smtplib.SMTP_SSL('smtp.naver.com', 465) as smtp:
            smtp.login(user_id, user_pw)
            smtp.send_message(msg)
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False