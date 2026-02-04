import streamlit as st
import requests
import pandas as pd
import plotly.express as px  # 예쁜 그래프를 그려주는 도구

# 1. 페이지 설정 (화면을 넓게 씁니다)
st.set_page_config(
    page_title="내 미국 주식 포트폴리오", 
    page_icon="🗽", 
    layout="wide" 
)

st.title("🗽 내 미국 주식 대시보드")

# 2. 금고에서 키 꺼내기
try:
    key = st.secrets["auth"]["APP_KEY"]
    secret = st.secrets["auth"]["APP_SECRET"]
    url = st.secrets["auth"]["URL_BASE"]
    cano = st.secrets["auth"]["CANO"]
    acnt_prdt_cd = st.secrets["auth"]["ACNT_PRDT_CD"]
except Exception:
    st.error("secrets.toml 파일을 찾을 수 없습니다.")
    st.stop()

# 3. 토큰 발급 함수
def get_access_token():
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": key, "appsecret": secret}
    res = requests.post(f"{url}/oauth2/tokenP", headers=headers, json=body)
    return res.json().get("access_token")

# 4. 메인 기능 시작
if st.button("내 자산 분석하기 🔄", type="primary"):
    with st.spinner("미국 주식 정보를 가져오는 중입니다..."):
        token = get_access_token()
        if not token:
            st.stop()

        try:
            # API 요청 설정
            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {token}",
                "appkey": key,
                "appsecret": secret,
                "tr_id": "JTTT3012R"
            }
            params = {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "OVRS_EXCG_CD": "NASD",
                "TR_CRCY_CD": "USD",
                "CTX_AREA_FK200": "",
                "CTX_AREA_NK200": ""
            }

            res = requests.get(f"{url}/uapi/overseas-stock/v1/trading/inquire-balance", headers=headers, params=params)
            data = res.json()

            if res.status_code == 200 and data['rt_cd'] == '0':
                output1 = data['output1'] # 종목 리스트
                output2 = data['output2'] # 계좌 총 자산 정보

                # --- [섹션 1] 상단 요약 정보 ---
                total_usd = float(output2['tot_evlu_pfls_amt']) # 총 평가금액 (달러)
                total_profit = float(output2['ovrs_tot_pfls'])   # 총 손익금 (달러)
                
                # 수익률 계산 (손익금 / (총평가 - 손익금) * 100) -> 근사치 계산
                # API가 주는 수익률이 있으면 그걸 쓰는 게 좋습니다. 여기선 output2에 수익률 필드가 없어서 직접 계산하거나 생략
                # 안전하게 평가 금액만 먼저 보여줍니다.
                
                # 화면을 2칸으로 나눠서 큼지막하게 보여주기
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(label="💰 총 자산 (달러)", value=f"${total_usd:,.2f}")
                with col2:
                    # 수익이면 초록(Green), 손실이면 빨강(Red) - 미국 스타일
                    st.metric(
                        label="📊 총 손익금", 
                        value=f"${total_profit:,.2f}", 
                        delta=f"{total_profit:,.2f}"
                    )

                st.divider() # 가로줄 긋기

                # --- [섹션 2] 그래프와 표 ---
                if output1:
                    df = pd.DataFrame(output1)
                    
                    # 데이터를 숫자로 변환 (문자로 오기 때문에 계산을 위해 변환 필수)
                    df['평가금액'] = df['ovrs_stck_evlu_amt'].astype(float)
                    df['수량'] = df['ovrs_cblc_qty'].astype(float)
                    df['수익률'] = df['evlu_pfls_rt'].astype(float)
                    df['현재가'] = df['now_pric2'].astype(float)
                    df['매입가'] = df['pchs_avg_pric'].astype(float)
                    df['종목명'] = df['ovrs_item_name'] # 한글 종목명
                    df['티커'] = df['ovrs_pdno']       # 티커 (TSLA 등)

                    # 화면 나누기 (왼쪽: 차트 / 오른쪽: 상세 표)
                    chart_col, table_col = st.columns([1, 1.5]) 

                    with chart_col:
                        st.subheader("🍰 자산 비중 (Top 5)")
                        # 평가금액 기준 상위 5개만 추리기 (나머지는 기타 처리하면 좋지만 일단 간단하게)
                        fig = px.pie(
                            df, 
                            values='평가금액', 
                            names='종목명', 
                            hole=0.4, # 도넛 모양
                            color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        # 차트 안에 글씨 넣기
                        fig.update_traces(textposition='inside', textinfo='percent+label')
                        fig.update_layout(showlegend=False) # 범례 숨기기 (깔끔하게)
                        st.plotly_chart(fig, use_container_width=True)

                    with table_col:
                        st.subheader("📋 보유 종목 상세")
                        
                        # 표에 보여줄 데이터만 깔끔하게 정리
                        display_df = df[['티커', '종목명', '수량', '매입가', '현재가', '수익률', '평가금액']]
                        
                        # Streamlit의 최신 기능으로 표 꾸미기
                        st.dataframe(
                            display_df,
                            column_config={
                                "평가금액": st.column_config.NumberColumn(format="$%.2f"),
                                "현재가": st.column_config.NumberColumn(format="$%.2f"),
                                "매입가": st.column_config.NumberColumn(format="$%.2f"),
                                "수익률": st.column_config.NumberColumn(
                                    format="%.2f%%",
                                ),
                            },
                            hide_index=True, # 0, 1, 2... 번호 숨기기
                            use_container_width=True,
                            height=500
                        )

                st.success("대시보드 업데이트 완료! 멋진 포트폴리오네요! 🎉")

            else:
                st.error("데이터 조회 실패")
                st.write(data['msg1'])

        except Exception as e:
            st.error(f"에러 발생: {e}")