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
numeric_columns = df.select_dtypes(include="number").columns.tolist()


# ──────────────────────────────────────────────────────────────
# 기능 1. 표 + 응답자 수 메트릭
# ──────────────────────────────────────────────────────────────
st.subheader("① 데이터 확인")
st.metric("응답자 수", len(df))
st.dataframe(df, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────
# 기능 2. 점수 분포
# ──────────────────────────────────────────────────────────────
st.subheader("② 점수 분포")

if not numeric_columns:
    st.warning("선택할 수 있는 숫자형 점수 컬럼이 없습니다.")
else:
    selected_score_column = st.selectbox(
        "점수 컬럼을 선택하세요.", numeric_columns
    )

    score_series = pd.to_numeric(df[selected_score_column], errors="coerce").dropna()

    if score_series.empty:
        st.info("선택한 컬럼에 표시할 점수 데이터가 없습니다.")
    else:
        score_band_df = pd.DataFrame({"점수": score_series})
        score_band_df["점수대"] = score_band_df["점수"].apply(score_band_label)

        ordered_bands = ["0~59", "60~69", "70~79", "80~89", "90~100"]
        band_counts = (
            score_band_df["점수대"]
            .value_counts()
            .reindex(ordered_bands, fill_value=0)
            .rename_axis("점수대")
            .reset_index(name="학생 수")
        )

        fig = px.bar(
            band_counts,
            x="점수대",
            y="학생 수",
            text="학생 수",
            title=f"{selected_score_column} 점수 분포",
        )
        fig.update_layout(xaxis_title="점수대", yaxis_title="학생 수")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(band_counts, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────
# 기능 3. 전체 요약 보기
# ──────────────────────────────────────────────────────────────
st.subheader("③ 전체 요약 보기")

summary_button = st.button("전체 요약 보기")

if summary_button:
    if not numeric_columns:
        st.warning("요약할 숫자형 문항이 없습니다.")
    else:
        stats_rows = []
        summary_rows = []
        ordered_bands = ["0~59", "60~69", "70~79", "80~89", "90~100"]

        for column in numeric_columns:
            scores = pd.to_numeric(df[column], errors="coerce").dropna()

            if not scores.empty:
                stats_rows.append(
                    {
                        "문항": column,
                        "응답 수": len(scores),
                        "평균": round(scores.mean(), 2),
                        "최고점": scores.max(),
                        "최저점": scores.min(),
                    }
                )

            for score in scores:
                summary_rows.append(
                    {
                        "문항": column,
                        "점수": score,
                        "점수대": score_band_label(score),
                    }
                )

        if stats_rows:
            stats_df = pd.DataFrame(stats_rows)
            st.write("문항별 기본 통계입니다.")
            st.dataframe(stats_df, use_container_width=True, hide_index=True)

        if not summary_rows:
            st.info("요약할 점수 데이터가 없습니다.")
        else:
            summary_df = pd.DataFrame(summary_rows)
            summary_df["점수대"] = pd.Categorical(
                summary_df["점수대"], categories=ordered_bands, ordered=True
            )
            summary_df = summary_df.sort_values(["점수대", "문항", "점수"]).reset_index(
                drop=True
            )

            st.write("모든 숫자형 문항을 점수대별로 재배치한 결과입니다.")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            band_summary = (
                summary_df.groupby(["점수대", "문항"]).size().unstack(fill_value=0)
            )
            st.bar_chart(band_summary)
