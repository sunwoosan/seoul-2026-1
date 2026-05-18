"""
학급 평가 결과 분석 도구 — Streamlit 시작 골격

CSV 파일을 업로드하면 점수 분포를 표와 그래프로 빠르게 확인할 수 있습니다.
수행 평가, 단원 평가 등의 결과를 집계해 시각화하면 학생 수준을 신속하게 파악할 수 있고,
수준별 학습지 제공을 위한 참고 자료로도 활용할 수 있습니다.
"""

import io

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="학급 평가 결과 분석 도구",
    page_icon="📊",
    layout="wide",
)

st.title("📊 학급 평가 결과 분석 도구")
st.caption(
    "수행 평가·단원 평가 등 학급 평가 결과를 업로드하면 점수 분포를 빠르게 시각화합니다."
)


# ──────────────────────────────────────────────────────────────
# 공용 유틸 (수정 불필요) — 엑셀 CP949 / 메모장 UTF-8 자동 처리
# ──────────────────────────────────────────────────────────────
def read_csv_any(uploaded_file) -> pd.DataFrame:
    raw = uploaded_file.read()
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(io.BytesIO(raw), encoding="utf-8", errors="replace")


def score_band_label(score: float) -> str:
    if pd.isna(score):
        return "미분류"
    if score < 60:
        return "0~59"
    if score < 70:
        return "60~69"
    if score < 80:
        return "70~79"
    if score < 90:
        return "80~89"
    return "90~100"


# ──────────────────────────────────────────────────────────────
# 사이드바: 파일 업로더
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📂 데이터 업로드")
    uploaded = st.file_uploader("학급 평가 결과 CSV 파일", type=["csv"])
    st.markdown(
        """
        **예시 컬럼**
        - `이름`
        - `점수`
        - `평가명`

        학급 평가 결과 CSV를 업로드하면 점수 분포를 시각화합니다.
        """
    )

if uploaded is None:
    st.info("👈 왼쪽 사이드바에서 학급 평가 결과 CSV 파일을 업로드하세요.")
    st.stop()

df = read_csv_any(uploaded)


# ──────────────────────────────────────────────────────────────
# 기능 1. 표 + 상단 요약
# ──────────────────────────────────────────────────────────────
st.subheader("① 데이터 확인")
st.metric("응답자 수", len(df))
st.dataframe(df, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────
# 기능 2. 문항별 응답 분포
# ──────────────────────────────────────────────────────────────
st.subheader("② 문항별 응답 분포")

question_columns = df.columns.tolist()
selected_question = st.selectbox("문항 이름을 선택하세요.", question_columns)

response_counts = (
    df[selected_question]
    .fillna("(응답 없음)")
    .astype(str)
    .value_counts()
    .sort_values(ascending=False)
)

if response_counts.empty:
    st.info("선택한 문항에 표시할 응답이 없습니다.")
else:
    response_df = response_counts.rename_axis("응답").reset_index(name="개수")
    fig = px.bar(
        response_df,
        x="응답",
        y="개수",
        text="개수",
        title=f"{selected_question} 응답 분포",
    )
    fig.update_layout(xaxis_title="응답", yaxis_title="개수")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(response_df, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────
# 기능 3. 전체 요약 보기
# ──────────────────────────────────────────────────────────────
st.subheader("③ 전체 요약 보기")

numeric_columns = df.select_dtypes(include="number").columns.tolist()
summary_button = st.button("전체 요약 보기")

if summary_button:
    if not numeric_columns:
        st.warning("점수대로 재배치할 숫자형 문항이 없습니다.")
    else:
        summary_rows = []
        ordered_bands = ["0~59", "60~69", "70~79", "80~89", "90~100"]

        for column in numeric_columns:
            scores = pd.to_numeric(df[column], errors="coerce").dropna()
            for score in scores:
                summary_rows.append(
                    {
                        "문항": column,
                        "점수": score,
                        "점수대": score_band_label(score),
                    }
                )

        if not summary_rows:
            st.info("요약할 점수 데이터가 없습니다.")
        else:
            summary_df = pd.DataFrame(summary_rows)
            summary_df["점수대"] = pd.Categorical(
                summary_df["점수대"], categories=ordered_bands, ordered=True
            )
            summary_df = summary_df.sort_values(["점수대", "문항", "점수"]).reset_index(drop=True)

            st.write("모든 숫자형 문항을 점수대별로 재배치한 결과입니다.")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            band_summary = (
                summary_df.groupby(["점수대", "문항"]).size().unstack(fill_value=0)
            )
            st.bar_chart(band_summary)
