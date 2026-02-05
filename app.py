import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# 1. 페이지 설정
st.set_page_config(
    page_title="Premium 미국 주식 인텔리전스",
    page_icon="📈",
    layout="wide"
)

# 가독성 및 색상 스타일 정의
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;700&display=swap');
    html, body, [class*="css"] { font-family: 'Pretendard', sans-serif; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #f0f2f6; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stExpander"] { border: none !important; box-shadow: none !important; background-color: #fbfbfb; margin-bottom: 10px; }
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

# 3. 데이터 로직 함수
@st.cache_data(ttl=3600)
def get_exchange_rate():
    try:
        res = requests.get("https://open.er-api.com/v6/latest/USD")
        return res.json()['rates']['KRW']
    except: return 1400.0

def get_access_token():
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    res = requests.post(f"{URL_BASE}/oauth2/tokenP", headers=headers, json=body)
    return res.json().get("access_token")

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

# 가상의 일봉 데이터를 생성하는 함수 (실제는 주가 상세 API 사용 권장)
def draw_ohlc_chart(ticker, current_price):
    # 실제 운영 시에는 한국투자증권의 '해외주식 기간별시세' API를 연결해야 합니다.
    # 여기서는 시각화를 위해 현재가 기준 가상의 20일치 일봉을 생성합니다.
    dates = pd.date_range(end=datetime.now(), periods=20)
    prices = [float(current_price) * (1 + (i-10)*0.01) for i in range(20)]
    fig = go.Figure(data=[go.Candlestick(x=dates,
                open=[p*0.99 for p in prices], high=[p*1.02 for p in prices],
                low=[p*0.98 for p in prices], close=prices)])
    fig.update_layout(title=f"{ticker} 20일 일봉 차트 (가상)", xaxis_rangeslider_visible=False, height=400)
    return fig

# 4. 메인 화면 구성
data = fetch_balance()
st.title("🗽 My WallStreet Dashboard")
st.caption(f"기준 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 적용 환율: ₩{exch_rate:,.2f}")

if data.get('rt_cd') == '0':
    output1 = data['output1']
    output2 = data['output2']
    
    # [섹션 1] 상단 요약 정보
    total_usd = float(output2['tot_evlu_pfls_amt'])
    total_krw = total_usd * exch_rate
    total_profit_usd = float(output2['ovrs_tot_pfls'])
    profit_rate = (total_profit_usd / (total_usd - total_profit_usd)) * 100 if total_usd != total_profit_usd else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("총 자산 (USD)", f"${total_usd:,.2f}")
    m2.metric("총 자산 (KRW)", f"₩{int(total_krw):,}")
    m3.metric("누적 손익 (수수료 미포함)", f"${total_profit_usd:,.2f}", f"{profit_rate:.2f}%")

    st.divider()

    # [섹션 2] 보유 종목 상세 (표 형식 정렬)
    if output1:
        df = pd.DataFrame(output1)
        # 데이터 정제 및 계산
        df['현재가'] = df['now_pric2'].astype(float)
        df['매입가'] = df['pchs_avg_pric'].astype(float)
        df['보유수량'] = df['ovrs_cblc_qty'].astype(float)
        df['평가금액'] = df['ovrs_stck_evlu_amt'].astype(float)
        df['수익률'] = df['evlu_pfls_rt'].astype(float)
        
        # 가상의 적정가 계산 (현재가 기준 5% 할인으로 예시 설정)
        df['적정가'] = df['현재가'] * 0.95
        df['적정가대비'] = ((df['현재가'] - df['적정가']) / df['적정가']) * 100

        st.subheader("📋 보유 종목 포트폴리오")
        
        # 메인 테이블 가독성을 위해 데이터프레임 스타일 적용
        def color_profit(val):
            color = 'red' if val > 0 else 'blue'
            return f'color: {color}'

        display_df = df[['ovrs_pdno', 'ovrs_item_name', '보유수량', '매입가', '현재가', '수익률', '적정가대비']].copy()
        display_df.columns = ['티커', '종목명', '수량', '평균단가', '현재가격', '수익률(%)', '적정가대비(%)']
        
        st.dataframe(
            display_df.style.applymap(color_profit, subset=['수익률(%)', '적정가대비(%)']),
            use_container_width=True,
            hide_index=True
        )

        # 개별 종목 일봉 차트 및 상세 분석 (선택 박스)
        st.write("")
        selected_stock = st.selectbox("📊 상세 분석 및 차트를 볼 종목을 선택하세요", df['ovrs_item_name'].tolist())
        
        if selected_stock:
            stock_row = df[df['ovrs_item_name'] == selected_stock].iloc[0]
            col_info, col_chart = st.columns([1, 2])
            
            with col_info:
                st.info(f"**{selected_stock} ({stock_row['ovrs_pdno']})** 상세 데이터")
                st.write(f"🔹 보유수량: {stock_row['보유수량']}주")
                st.write(f"🔹 평가손익: ${float(stock_row['frcr_evlu_pfls_amt']):,.2f}")
                
                # 목표가 설정 (화면에서 직접 조정)
                target = st.number_input("나의 목표가 설정 ($)", value=stock_row['현재가']*1.15)
                if stock_row['현재가'] >= target:
                    st.success("🔥 목표가 도달! 수익 실현을 고려해보세요.")
                else:
                    st.write(f"🎯 목표가까지 **${target - stock_row['현재가']:.2f}** 남음")
            
            with col_chart:
                st.plotly_chart(draw_ohlc_chart(stock_row['ovrs_pdno'], stock_row['현재가']), use_container_width=True)

    st.divider()

    # [섹션 3] 섹터 및 비중 그래프 (최하단 배치)
    st.subheader("🍕 자산 배분 현황")
    c1, c2 = st.columns([1, 1])
    
    with c1:
        # 종목별 비중
        fig_pie = px.pie(df, values='평가금액', names='ovrs_item_name', hole=0.4, title="종목별 자산 비중")
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with c2:
        # 섹터 정보 (API에서 섹터 정보를 주지 않으므로 가상의 매핑 데이터 생성)
        # 실제로는 별도의 섹터 매핑 딕셔너리를 관리하는 것이 좋습니다.
        sector_map = {"AAPL": "IT", "TSLA": "경기관련소비재", "NVDA": "IT", "MSFT": "IT", "GOOGL": "커뮤니케이션"}
        df['섹터'] = df['ovrs_pdno'].map(sector_map).fillna("기타/미분류")
        
        fig_sector = px.sunburst(df, path=['섹터', 'ovrs_item_name'], values='평가금액', title="섹터별 상세 비중")
        st.plotly_chart(fig_sector, use_container_width=True)

else:
    st.error("데이터 로드 실패: API 응답을 확인하세요.")