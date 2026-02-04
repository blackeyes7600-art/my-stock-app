import streamlit as st
import requests
import json

st.title("🔑 API 연결 테스트")

# 금고에서 열쇠 꺼내기
key = st.secrets["auth"]["APP_KEY"]
secret = st.secrets["auth"]["APP_SECRET"]
url = st.secrets["auth"]["URL_BASE"]

if st.button("내 계좌 연결 확인하기"):
    # 토큰 발급 요청
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": key,
        "appsecret": secret
    }
    
    # 한국투자증권 서버로 전송
    res = requests.post(f"{url}/oauth2/tokenP", headers=headers, data=json.dumps(body))

    # 결과 확인
    if res.status_code == 200:
        st.balloons()
        st.success("✅ 연결 성공! 증권사 서버와 통신이 됩니다.")
    else:
        st.error("❌ 연결 실패... 키 값을 다시 확인해주세요.")
        st.write(res.text)