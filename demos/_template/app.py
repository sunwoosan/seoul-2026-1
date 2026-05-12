"""
{{프로젝트 제목}} — Streamlit 시작 골격

⚠️ 이 파일은 빈 골격입니다. Copilot에게 다음 순서로 프롬프트하세요.
   1) 사이드바 CSV 업로더 만들기
   2) 표 + 응답자 수 메트릭 카드 추가
   3) 본인 명세의 기능 2, 3 추가

학생들이 손대지 않아도 되는 영역(인코딩 처리, 페이지 설정)은 미리 작성되어 있습니다.
"""

import io

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="{{프로젝트 제목}}",
    page_icon="📊",
    layout="wide",
)

st.title("📊 {{프로젝트 제목}}")
st.caption("{{한 줄 요약}}")


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


# ──────────────────────────────────────────────────────────────
# 사이드바: 파일 업로더
# ──────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📂 데이터 업로드")
    uploaded = st.file_uploader("CSV 파일", type=["csv"])
    st.markdown(
        """
        **필수 컬럼** (본인 명세에 맞게 수정)
        - `이름`
        - `1회차`
        - `2회차`
        - `3회차`

        샘플 파일이 필요하면 `sample_data.csv`를 사용하세요.
        """
    )

if uploaded is None:
    st.info("👈 왼쪽 사이드바에서 CSV 파일을 업로드하세요.")
    st.stop()

df = read_csv_any(uploaded)


# ──────────────────────────────────────────────────────────────
# 기능 1. (TODO) 표 + 상단 요약
# ──────────────────────────────────────────────────────────────
st.subheader("① 데이터 확인")
st.dataframe(df, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────
# 기능 2. 학생별 성적(3회차) 그룹 막대그래프
# ──────────────────────────────────────────────────────────────
st.subheader("② 학생별 성적 막대그래프")

REQUIRED_COLS = ["이름", "1회차", "2회차", "3회차"]
missing = [c for c in REQUIRED_COLS if c not in df.columns]
if missing:
    st.error(f"필수 컬럼 누락: {missing}. 필요한 컬럼: {REQUIRED_COLS}")
    st.stop()

# 숫자 변환(문자/공백 등 섞여 있어도 안전하게 처리)
for col in ["1회차", "2회차", "3회차"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

if df[["1회차", "2회차", "3회차"]].isna().any().any():
    st.error("1~3회차 컬럼에 숫자가 아닌 값이 있습니다. CSV를 확인하세요.")
    st.stop()

sort_by = st.radio(
    "정렬 기준",
    ["이름", "1회차", "2회차", "3회차"],
    horizontal=True,
)

plot_df = df[["이름", "1회차", "2회차", "3회차"]].copy()
if sort_by == "이름":
    plot_df = plot_df.sort_values("이름")
else:
    plot_df = plot_df.sort_values(sort_by, ascending=False)

long_df = plot_df.melt(
    id_vars=["이름"],
    value_vars=["1회차", "2회차", "3회차"],
    var_name="회차",
    value_name="성적",
)

fig = px.bar(
    long_df,
    x="이름",
    y="성적",
    color="회차",
    barmode="group",
    text="성적",
    title="학생별 성적 변화 (1~3회차)",
)
fig.update_traces(textposition="outside")
fig.update_layout(
    xaxis_title="학생",
    yaxis_title="성적",
    height=520,
    margin=dict(t=70, b=40, l=20, r=20),
    legend_title_text="",
)

st.plotly_chart(fig, use_container_width=True)


# ──────────────────────────────────────────────────────────────
# 기능 3. (TODO) 본인 명세의 기능 3을 여기에 작성
# ──────────────────────────────────────────────────────────────
st.subheader("③ (작성 예정)")
st.write("Copilot에게: '기능 3을 추가해줘. ___'")
