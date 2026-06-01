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

ORDERED_BANDS = ["0~59", "60~69", "70~79", "80~89", "90~100"]
LEVEL_ORDER = ["노력요함", "보통", "잘함", "매우잘함"]


# ──────────────────────────────────────────────────────────────
# 공용 유틸
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


def student_level_label(score: float) -> str:
    if pd.isna(score):
        return "미분류"
    if score < 60:
        return "노력요함"
    if score < 80:
        return "보통"
    if score < 90:
        return "잘함"
    return "매우잘함"


def feedback_message(level: str) -> str:
    feedback_map = {
        "노력요함": "교과서, 배움공책 내용을 좀 더 꼼꼼하게 복습하세요.",
        "보통": "보통맛 학습지를 한 번 더 풀어보세요.",
        "잘함": "매운맛 학습지를 한 번 더 풀어보세요.",
        "매우잘함": "핵불닭맛 학습지를 풀어보세요.",
    }
    return feedback_map.get(level, "피드백이 없습니다.")


# ──────────────────────────────────────────────────────────────
# 사이드바: 파일 업로더
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📂 데이터 업로드")
    uploaded = st.file_uploader("학급 평가 결과 CSV 파일", type=["csv"])
    st.markdown(
        """
        **예시 컬럼**
        - `번호`
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
student_id_column = "번호" if "번호" in df.columns else None


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
    selected_score_column = st.selectbox("점수 컬럼을 선택하세요.", numeric_columns)

    score_series = pd.to_numeric(df[selected_score_column], errors="coerce").dropna()

    if score_series.empty:
        st.info("선택한 컬럼에 표시할 점수 데이터가 없습니다.")
    else:
        score_band_df = pd.DataFrame({"점수": score_series})
        score_band_df["점수대"] = score_band_df["점수"].apply(score_band_label)

        band_counts = (
            score_band_df["점수대"]
            .value_counts()
            .reindex(ORDERED_BANDS, fill_value=0)
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
                summary_df["점수대"], categories=ORDERED_BANDS, ordered=True
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


# ──────────────────────────────────────────────────────────────
# 기능 4. 학생 수준 분류표 자동 생성
# ──────────────────────────────────────────────────────────────
st.subheader("④ 학생 수준 분류표")

if not numeric_columns:
    st.warning("수준 분류에 사용할 숫자형 점수 컬럼이 없습니다.")
elif student_id_column is None:
    st.warning("학생 수준 분류표를 만들려면 `번호` 컬럼이 필요합니다.")
else:
    selected_level_column = st.selectbox(
        "수준 분류에 사용할 점수 컬럼을 선택하세요.",
        numeric_columns,
        key="level_column",
    )

    level_df = df[[student_id_column, selected_level_column]].copy()
    level_df[selected_level_column] = pd.to_numeric(
        level_df[selected_level_column], errors="coerce"
    )
    level_df = level_df.dropna(subset=[selected_level_column])

    if level_df.empty:
        st.info("수준 분류에 사용할 점수 데이터가 없습니다.")
    else:
        level_df["수준"] = level_df[selected_level_column].apply(student_level_label)
        level_df["피드백"] = level_df["수준"].apply(feedback_message)
        level_df = level_df.rename(
            columns={student_id_column: "번호", selected_level_column: "점수"}
        )
        level_df = level_df[["번호", "점수", "수준", "피드백"]]
        level_df["수준"] = pd.Categorical(
            level_df["수준"], categories=LEVEL_ORDER, ordered=True
        )
        level_df = level_df.sort_values(["수준", "점수", "번호"], ascending=[True, False, True])

        st.write("학생별 점수를 기준으로 수준을 자동 분류한 결과입니다.")
        st.dataframe(level_df, use_container_width=True, hide_index=True)

        level_counts = (
            level_df["수준"]
            .value_counts()
            .reindex(LEVEL_ORDER, fill_value=0)
            .rename_axis("수준")
            .reset_index(name="학생 수")
        )
        st.bar_chart(level_counts.set_index("수준"))

        st.write("학생 번호를 선택하면 개별 피드백을 확인할 수 있습니다.")
        selected_student = st.selectbox(
            "피드백을 확인할 학생 번호를 선택하세요.",
            level_df["번호"].tolist(),
            key="feedback_student",
        )

        selected_student_row = level_df[level_df["번호"] == selected_student].iloc[0]
        with st.expander(f"{selected_student}번 학생 피드백 보기"):
            st.write(f"**점수:** {selected_student_row['점수']}")
            st.write(f"**수준:** {selected_student_row['수준']}")
            st.info(selected_student_row["피드백"])


# ──────────────────────────────────────────────────────────────
# 기능 5. 기준 점수 미달 학생 목록
# ──────────────────────────────────────────────────────────────
st.subheader("⑤ 기준 점수 미달 학생 목록")

if not numeric_columns:
    st.warning("미달 학생 추출에 사용할 숫자형 점수 컬럼이 없습니다.")
elif student_id_column is None:
    st.warning("미달 학생 목록을 만들려면 `번호` 컬럼이 필요합니다.")
else:
    selected_below_column = st.selectbox(
        "미달 학생을 찾을 점수 컬럼을 선택하세요.",
        numeric_columns,
        key="below_column",
    )

    threshold = 70
    below_df = df[[student_id_column, selected_below_column]].copy()
    below_df[selected_below_column] = pd.to_numeric(
        below_df[selected_below_column], errors="coerce"
    )
    below_df = below_df.dropna(subset=[selected_below_column])
    below_df = below_df[below_df[selected_below_column] < threshold]

    if below_df.empty:
        st.success(f"{threshold}점 미만 학생이 없습니다.")
    else:
        below_df = below_df.rename(
            columns={student_id_column: "번호", selected_below_column: "점수"}
        )
        below_df = below_df.sort_values(["점수", "번호"], ascending=[True, True])

        st.write(f"{selected_below_column}에서 {threshold}점 미만인 학생 목록입니다.")
        st.metric("미달 학생 수", len(below_df))
        st.dataframe(below_df, use_container_width=True, hide_index=True)
