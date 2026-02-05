import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
import time

# 1. 페이지 설정
st.set_page_config(
    page_title="Premium 미국 주식 인텔리전스",
    page_icon="📈",
    layout="wide"
)

# 가독성을 위한 커스텀 스타일(폰트 및 간격)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .stMetric { background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 1px solid #eee; }
    </style>
    """, unsafe_allow_html=True)

# 2. 보안 키 및 환경 설정
try:
    auth = st.secrets["auth"]
    APP_KEY = auth["APP_KEY"]
    APP_SECRET = auth["APP_SECRET"]
    URL_BASE = auth["URL_BASE"]
    CANO = auth["CANO"]
    ACNT_PRDT_CD = auth["ACNT_PRDT_CD"]
except Exception:
    st.error("Secrets 설정이 필요합니다.")
    st.stop()

# 3. 필수 함수 정의
@st.cache_data(ttl=3600) # 환율은 1시간마다 갱신
def get_exchange_rate():
    try:
        res = requests.get("https://open.er-api.com/v6/latest/USD")
        return res.json()['rates']['KRW']
    except:
        return 1350.0  # 실패 시 기본값

def get_access_token():
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    res = requests.post(f"{URL_BASE}/oauth2/tokenP", headers=headers, json=body)
    return res.json().get("access_token")

# 4. 데이터 로드 (버튼 없이 자동 실행)
token = get_access_token()
exch_rate = get_exchange_rate()

def fetch_balance():
    headers = {
        "content-type": "application/json", "authorization": f"Bearer {token}",
        "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "JTTT3012R"
    }
    params = {
        "CANO": CANO, "ACNT_PRDT_CD": ACNT_PRDT_CD,
        "OVRS_EXCG_CD": "NASD", "TR_CRCY_CD": "USD",
        "CTX_AREA_FK200": "", "CTX_AREA_NK200": ""
    }
    res = requests.get(f"{URL_BASE}/uapi/overseas-stock/v1/trading/inquire-balance", headers=headers, params=params)
    return res.json()

data = fetch_balance()

# 5. 메인 UI 레이아웃
st.title("🚀 미국 주식 포트폴리오 매니저")
st.caption(f"최근 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (실시간 환율: ₩{exch_rate:,.2f})")

if data.get('rt_cd') == '0':
    output1 = data['output1']
    output2 = data['output2']
    
    # 상단 요약 정보 (달러 & 원화 병기)
    total_usd = float(output2['tot_evlu_pfls_amt'])
    total_krw = total_usd * exch_rate
    total_profit_usd = float(output2['ovrs_tot_pfls'])
    
    m1, m2, m3 = st.columns(3)
    m1.metric("총 자산 (USD)", f"${total_usd:,.2f}")
    m2.metric("총 자산 (KRW)", f"₩{int(total_krw):,}")
    m3.metric("총 손익", f"${total_profit_usd:,.2f}", delta=f"{total_profit_usd:,.2f}")

    tab1, tab2 = st.tabs(["📊 내 보유 주식", "⭐ 관심 및 매도 종목"])

    with tab1:
        if output1:
            df = pd.DataFrame(output1)
            # 데이터 전처리
            df['평가금액'] = df['ovrs_stck_evlu_amt'].astype(float)
            df['수수료'] = df['ovrs_stck_evlu_amt'].astype(float) * 0.002 # 예시 수수료
            
            col_chart, col_list = st.columns([1.5, 2])
            
            with col_list:
                st.subheader("보유 종목 상세")
                # 종목 클릭 시 팝업(Expander)으로 상세 정보 및 그래프 표현
                for i, row in df.iterrows():
                    with st.expander(f"{row['ovrs_item_name']} ({row['ovrs_pdno']}) | 수익률: {row['evlu_pfls_rt']}%"):
                        c1, c2 = st.columns(2)
                        c1.write(f"**현재가:** ${row['now_pric2']}")
                        c1.write(f"**매입가:** ${row['pchs_avg_pric']}")
                        
                        # 가상의 적정가/목표가 입력 (추후 DB 연동 가능)
                        target_price = st.number_input(f"{row['ovrs_pdno']} 목표가", value=float(row['now_pric2'])*1.2, key=f"t_{i}")
                        fair_price = st.number_input(f"{row['ovrs_pdno']} 적정가", value=float(row['now_pric2'])*1.1, key=f"f_{i}")
                        
                        diff = float(row['now_pric2']) - fair_price
                        st.info(f"적정가 대비 현재가 차이: **${diff:.2f}**")
                        
                        if float(row['now_pric2']) >= target_price:
                            st.success("🎯 목표가 도달! 매도를 검토하세요.")
                        
                        # 종목별 가상 차트 (Plotly)
                        chart_data = pd.DataFrame({'날짜': pd.date_range(end=datetime.now(), periods=10), '주가': [float(row['now_pric2']) * (1 + (x-5)*0.01) for x in range(10)]})
                        fig_stock = px.line(chart_data, x='날짜', y='주가', title=f"{row['ovrs_item_name']} 주가 추이")
                        st.plotly_chart(fig_stock, use_container_width=True)

            with col_chart:
                st.subheader("섹터/종목 비중")
                fig_pie = px.pie(df, values='평가금액', names='ovrs_item_name', hole=0.5, color_discrete_sequence=px.colors.qualitative.Safe)
                st.plotly_chart(fig_pie, use_container_width=True)

    with tab2:
        st.subheader("관심 종목 및 매도 완료 리스트")
        # 관심 종목 검색 및 추가 UI (예시)
        search_ticker = st.text_input("관심 종목 티커 입력 (예: NVDA, TSLA)")
        if search_ticker:
            st.write(f"🔍 {search_ticker} 정보 조회 중...")
            # 여기서 실제 API로 관심종목 시세를 가져오는 로직 추가 가능
        
        st.info("이전에 전량 매도한 주식 목록이 여기에 표시됩니다. (기능 구현 중)")

else:
    st.warning("데이터를 불러올 수 없습니다. API 연결을 확인하세요.")

# 주기적 자동 새로고침 (60초마다)
# time.sleep(60)
# st.rerun()