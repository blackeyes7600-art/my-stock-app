import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# 1. 페이지 설정 및 가독성 스타일
st.set_page_config(page_title="Premium 미국 주식 인텔리전스", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .stMetric { background-color: #ffffff; padding: 12px; border-radius: 8px; border: 1px solid #f0f2f6; }
    div[data-testid="stExpander"] { border: 1px solid #f0f2f6; border-radius: 8px; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# 2. 데이터 처리 함수
@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        res = requests.get("https://open.er-api.com/v6/latest/USD")
        return res.json()['rates']['KRW']
    except: return 1450.0 # 실패 시 최근 환율 근사치

def get_access_token():
    auth = st.secrets["auth"]
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": auth["APP_KEY"], "appsecret": auth["APP_SECRET"]}
    res = requests.post(f"{auth['URL_BASE']}/oauth2/tokenP", headers=headers, json=body)
    return res.json().get("access_token")

def fetch_balance(token):
    auth = st.secrets["auth"]
    headers = {"content-type": "application/json", "authorization": f"Bearer {token}",
               "appkey": auth["APP_KEY"], "appsecret": auth["APP_SECRET"], "tr_id": "JTTT3012R"}
    params = {"CANO": auth["CANO"], "ACNT_PRDT_CD": auth["ACNT_PRDT_CD"],
              "OVRS_EXCG_CD": "NASD", "TR_CRCY_CD": "USD", "CTX_AREA_FK200": "", "CTX_AREA_NK200": ""}
    return requests.get(f"{auth['URL_BASE']}/uapi/overseas-stock/v1/trading/inquire-balance", headers=headers, params=params).json()

# 3. 메인 로직 시작
token = get_access_token()
exch_rate = get_exchange_rate()
data = fetch_balance(token)

st.title("🗽 My WallStreet Dashboard")
st.caption(f"기준: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 실시간 환율: ₩{exch_rate:,.1f}")

if data.get('rt_cd') == '0':
    output1 = data['output1']
    output2 = data['output2']
    
    # [설정] 통화 선택 버튼
    currency_mode = st.radio("표시 통화 선택", ["USD (달러)", "KRW (원화)"], horizontal=True)
    curr_symbol = "$" if "USD" in currency_mode else "₩"
    curr_rate = 1.0 if "USD" in currency_mode else exch_rate

    # [섹션 1] 요약 정보
    total_usd = float(output2['tot_evlu_pfls_amt'])
    total_profit_usd = float(output2['ovrs_tot_pfls'])
    
    m1, m2, m3 = st.columns(3)
    m1.metric(f"총 자산 ({curr_symbol})", f"{curr_symbol}{total_usd * curr_rate:,.1f}")
    m2.metric(f"누적 손익 ({curr_symbol})", f"{curr_symbol}{total_profit_usd * curr_rate:,.1f}")
    m3.metric("환율 정보", f"₩{exch_rate:,.1f}", "실시간")

    st.divider()

    # [섹션 2] 보유 종목 포트폴리오
    if output1:
        df = pd.DataFrame(output1)
        df['현재가'] = df['now_pric2'].astype(float)
        df['매입가'] = df['pchs_avg_pric'].astype(float)
        df['수량'] = df['ovrs_cblc_qty'].astype(float)
        df['평가금액'] = df['ovrs_stck_evlu_amt'].astype(float)
        df['수익률'] = df['evlu_pfls_rt'].astype(float)
        
        # 실제 비중 계산 (소수점 첫째 자리)
        df['비중(%)'] = (df['평가금액'] / total_usd * 100).round(1)
        
        st.subheader("📋 보유 종목 포트폴리오")
        
        # 메인 테이블 데이터 구성 (가독성 최적화)
        display_df = df[['ovrs_pdno', 'ovrs_item_name', '수량', '매입가', '현재가', '비중(%)', '수익률']].copy()
        display_df.columns = ['티커', '종목명', '수량', '매입단가', '현재가', '비중(%)', '수익률(%)']
        
        # 원화 변환 적용 시 가격 컬럼 수정
        if "KRW" in currency_mode:
            display_df['매입단가'] = (display_df['매입단가'] * exch_rate).round(0)
            display_df['현재가'] = (display_df['현재가'] * exch_rate).round(0)

        # 표 출력
        st.dataframe(
            display_df.style.format({
                '수량': '{:.0f}', '매입단가': '{:,.1f}', '현재가': '{:,.1f}', 
                '비중(%)': '{:.1f}%', '수익률(%)': '{:+.2f}%'
            }).applymap(lambda x: 'color: red' if x > 0 else 'color: blue', subset=['수익률(%)']),
            use_container_width=True, hide_index=True
        )

        # [상세 분석 팝업] 종목 선택 시 아래에 차트와 목표 비중 설정 등장
        st.write("")
        selected_stock = st.selectbox("🔍 상세 분석할 종목을 선택하세요", ["선택 안 함"] + df['ovrs_item_name'].tolist())
        
        if selected_stock != "선택 안 함":
            row = df[df['ovrs_item_name'] == selected_stock].iloc[0]
            
            with st.container():
                st.markdown(f"### 📊 {selected_stock} 상세 분석")
                c1, c2 = st.columns([1, 2])
                
                with c1:
                    # 목표 비중 및 적정가 설정
                    target_ratio = st.slider("목표 비중 (%)", 0.0, 50.0, 10.0, step=0.5)
                    fair_price = st.number_input("나의 적정가 ($)", value=row['현재가'] * 0.9, step=0.1)
                    
                    diff_ratio = target_ratio - row['비중(%)']
                    st.write(f"현재 비중: **{row['비중(%)']}%**")
                    st.write(f"목표 대비: **{diff_ratio:+.1f}%** " + ("(추가 매수 필요)" if diff_ratio > 0 else "(비중 과다)"))
                    
                    diff_price = row['현재가'] - fair_price
                    price_color = "red" if diff_price > 0 else "blue"
                    st.markdown(f"적정가 대비: <span style='color:{price_color}'>**${diff_price:,.2f}**</span>", unsafe_allow_html=True)

                with c2:
                    # 가상 일봉 차트 (나중에 실제 데이터 연동 가능)
                    dates = pd.date_range(end=datetime.now(), periods=20)
                    fig = go.Figure(data=[go.Candlestick(x=dates,
                        open=[p*0.99 for p in [row['현재가']]*20], high=[p*1.02 for p in [row['현재가']]*20],
                        low=[p*0.98 for p in [row['현재가']]*20], close=[row['현재가']]*20)])
                    fig.update_layout(xaxis_rangeslider_visible=False, height=300, margin=dict(l=0,r=0,t=0,b=0))
                    st.plotly_chart(fig, use_container_width=True)

    # [섹션 3] 섹터 비중 (최하단)
    st.divider()
    st.subheader("🍕 전체 자산 비중")
    fig_pie = px.pie(df, values='평가금액', names='ovrs_item_name', hole=0.5, 
                     color_discrete_sequence=px.colors.qualitative.Pastel)
    fig_pie.update_traces(textinfo='percent+label')
    st.plotly_chart(fig_pie, use_container_width=True)

# app.py 맨 하단 수정
else:
    # 어떤 에러인지 상세하게 출력합니다.
    error_msg = data.get('msg1', '알 수 없는 에러')
    st.error(f"❌ 데이터 로드 실패: {error_msg}")
    
    # 개발자 모드: 서버에서 받은 전체 응답을 보여줍니다. (범인 검거용)
    with st.expander("상세 에러 로그 보기"):
        st.write(data)