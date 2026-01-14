mkdir .streamlit

touch secrets.toml
```
# secrets.toml
NAVER_ID="you NAVER ID"
NAVER_APP_PW="your NAVER passkey"
IMAP_SERVER="imap.naver.com"
```
---

uv sync

---

Need packages.txt and requirements.txt to serve the app on streamlit Cloud


---
# How to RUN locally
uv run streamlit run app.py

# How to serve the app on Streamlit Cloud
1. Push the code to git
2. Register the git repo from Streamlit website