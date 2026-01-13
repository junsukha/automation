# import smtplib
from email.message import EmailMessage
import streamlit as st

# def send_naver_report(user_id, user_pw, recipient_email, report_text):
#     msg = EmailMessage()
#     msg.set_content(report_text)
#     msg['Subject'] = '✅ [Academy Agent] Sync Report'
#     msg['From'] = f"{user_id}@naver.com"
#     msg['To'] = recipient_email

#     # Connect to Naver SMTP server
#     try:
#         with smtplib.SMTP_SSL('smtp.naver.com', 587) as smtp:
#             smtp.ehlo()         # Identify yourself to the server
#             smtp.starttls()     # "Upgrade" the connection to secure encrypted TLS
#             smtp.ehlo()         # Re-identify over the secure connection
#             smtp.login(user_id, user_pw)
#             smtp.send_message(msg)
#         return True
#     except Exception as e:
#         st.error(f"Failed to send email: {e}")
#         return False

import smtplib
import ssl

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
    
    
from imap_tools import MailBox, AND
from datetime import datetime, timedelta

def get_all_senders_clean(user_id, user_pw): # Add parameters here
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