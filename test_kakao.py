from PyKakao import Message
from dotenv import load_dotenv
import os
# 1. Configuration
# Paste your REST API Key from Kakao Developers
def test_kakao():
    load_dotenv()
    REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
    msg_api = Message(service_key=REST_API_KEY)
    print(f'REST API Key Loaded: {REST_API_KEY is not None}')
    
    auth_code = None
    access_token = None
    
    try:
        # 2. Get Login URL
        auth_url = msg_api.get_url_for_generating_code()
        print(f"1. Open this link in your browser and log in:\n{auth_url}\n")

        # 3. Handle Redirect
        redirected_url = input("2. Paste the FULL URL from your browser address bar here: ")
        
        # CLEANUP: Remove backslashes added by Zsh/Mac terminal
        clean_url = redirected_url.replace("\\", "")

        # Extract the code manually
        if "code=" in clean_url:
            auth_code = clean_url.split("code=")[1].split("&")[0]
            print(f"✅ Code Extracted: {auth_code[:10]}...")
            
            # Use the code to get the token
            access_token = msg_api.get_access_token_by_code(auth_code)
            msg_api.set_access_token(access_token)
            print("✅ Token Set Successfully!")

            # 4. Send Message to Yourself
            response = msg_api.send_message_to_me(
                message_type="text",
                text="Naver-ACA2000 Test: Success! 🚀",
                link={"web_url": "https://naver.com", "mobile_web_url": "https://naver.com"},
                button_title="Check Report"
            )
            
            print("\n🚀 SUCCESS! Check your KakaoTalk (My Chatroom).")
            return True
            
        else:
            print("❌ Error: No 'code=' found in the URL. Did you copy the whole thing?")
            return False

    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup: Kill any remaining chromedriver processes
        # (in case you used Selenium before this)
        import subprocess
        try:
            subprocess.run(['pkill', '-9', 'chromedriver'], 
                         stderr=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL)
        except:
            pass
    
    
# def test_v2():
#     import requests
#     import json
#     load_dotenv()
#     url = 'https://kauth.kakao.com/oauth/token'
#     rest_api_key = os.getenv("KAKAO_REST_API_KEY")
#     redirect_uri = os.getenv("KAKAO_REDIRECT_URL")
#     authorize_code = os.getenv("TOKEN")

#     print(f'REST API Key Loaded: {rest_api_key}')
#     print(f'Redirect URI Loaded: {redirect_uri}')
#     print(f'Authorize Code Loaded: {authorize_code}')

#     data = {
#         'grant_type': 'authorization_code',
#         'client_id': rest_api_key,
#         'redirect_uri': redirect_uri,
#         'code': authorize_code,
#     }

#     response = requests.post(url, data=data)
#     tokens = response.json()
#     print(f'token: {tokens}')

#     if 'access_token' not in tokens:
#         print(f"❌ Failed to get access token: {tokens}")
#         return

#     with open("kakao_code.json", "w") as fp:
#         json.dump(tokens, fp)

#     # Send Kakao message
#     url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
#     headers = {
#         "Authorization": "Bearer " + tokens["access_token"]
#     }
#     data = {
#         "template_object": json.dumps({
#             "object_type": "text",
#             "text": "안녕? 나는 잉빈이야",
#             "link": {
#                 "web_url": "https://naver.com",
#                 "mobile_web_url": "https://naver.com"
#             },
#             "button_title": "헤헤"
#         })
#     }

#     response = requests.post(url, headers=headers, data=data)
#     print(f"Kakao API status: {response.status_code}")
#     try:
#         print(f"Kakao API response: {response.json()}")
#     except Exception:
#         print(f"Kakao API response: {response.text}")

#     if response.status_code == 200:
#         print("🚀 SUCCESS! Check your KakaoTalk (My Chatroom).")
#     else:
#         print("❌ Failed to send message.")
    
if __name__ == "__main__":
    # test_v2()
    test_kakao()