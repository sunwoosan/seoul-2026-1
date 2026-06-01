import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import numpy as np
from sklearn.linear_model import LinearRegression

st.set_page_config(
    page_title="타자 성장 트래커",
    page_icon="⌨️",
    layout="wide",
)

# 배경색을 연한 핑크로 설정
st.markdown("""
    <style>
        .stApp {
            background-color: #FFE4E1;
        }
    </style>
""", unsafe_allow_html=True)

st.title("⌨️ 타자 성장 트래커")
st.caption("결과보다 성장 과정을 본다 — 학생들의 1·2·3회차 타자 속도 변화 시각화 도구")


REQUIRED_COLS = ["이름", "종류", "1회차", "2회차", "3회차"]


def read_csv_any(uploaded_file) -> pd.DataFrame:
    """엑셀 기본 CP949와 UTF-8을 모두 자동 처리한다."""
    raw = uploaded_file.read()
    for enc in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=enc)
        except UnicodeDecodeError:
            continue
    return pd.read_csv(io.BytesIO(raw), encoding="utf-8", errors="replace")


def validate(df: pd.DataFrame) -> list[str]:
    errors = []
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        errors.append(f"필수 컬럼 누락: {missing}. 필요한 컬럼: {REQUIRED_COLS}")
        return errors
    
    valid_types = ["단어", "문장", "긴글연습"]
    if not df["종류"].isin(valid_types).all():
        errors.append(f"종류 컬럼에 유효하지 않은 값이 있습니다. 허용 값: {valid_types}")
    
    for col in ["1회차", "2회차", "3회차"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[["1회차", "2회차", "3회차"]].isna().any().any():
        errors.append("1~3회차 컬럼에 숫자가 아닌 값이 있습니다. CSV를 확인하세요.")
    if (df["1회차"] <= 0).any():
        errors.append("1회차에 0 또는 음수가 있어 성장률 계산이 불가능한 학생이 있습니다.")
    return errors


def predict_4th_attempt(row):
    """선형 회귀를 이용해 4회차 예상 타자 횟수를 예측"""
    X = np.array([1, 2, 3]).reshape(-1, 1)
    y = np.array([row["1회차"], row["2회차"], row["3회차"]])
    
    model = LinearRegression()
    model.fit(X, y)
    
    prediction = model.predict([[4]])[0]
    return max(0, prediction)  # 음수 방지


def get_encouragement_message(growth_rate, prediction_4th, current_3rd):
    """성장률과 예측값을 바탕으로 격려 메시지 생성"""
    if growth_rate >= 50:
        emoji = "🌟"
        message = "놀라운 성장입니다!"
    elif growth_rate >= 25:
        emoji = "🚀"
        message = "좋은 진전을 보이고 있어요!"
    elif growth_rate >= 0:
        emoji = "📈"
        message = "계속 노력하고 있군요!"
    else:
        emoji = "💪"
        message = "다음 회차에 도전해봐요!"
    
    increase = int(prediction_4th - current_3rd)
    if increase > 0:
        detail = f"지금의 속도라면 4회차에는 약 {int(prediction_4th)}타(+{increase}타)를 기대할 수 있어요!"
    else:
        detail = f"지금의 속도를 유지하면 4회차에는 약 {int(prediction_4th)}타를 기대할 수 있어요!"
    
    return emoji, message, detail


with st.sidebar:
    st.header("📂 데이터 업로드")
    uploaded = st.file_uploader("학생 타자 기록 CSV", type=["csv"])
    st.markdown(
        """
        **필수 컬럼**
        - `이름` (문자열)
        - `종류` (단어/문장/긴글연습 중 하나)
        - `1회차` (정수, 타수)
        - `2회차` (정수, 타수)
        - `3회차` (정수, 타수)

        샘플 파일이 필요하면 저장소의 `sample_data.csv`를 사용하세요.
        """
    )

if uploaded is None:
    st.info("👈 왼쪽 사이드바에서 CSV 파일을 업로드하세요.")
    with st.expander("📑 입력 CSV 예시 보기"):
        st.code(
            "이름,종류,1회차,2회차,3회차\n김민준,단어,120,145,180\n이서연,문장,95,110,135\n...",
            language="csv",
        )
    st.stop()

df = read_csv_any(uploaded)

errs = validate(df)
if errs:
    for e in errs:
        st.error(e)
    st.stop()

df["성장 퍼센티지"] = ((df["3회차"] - df["1회차"]) / df["1회차"] * 100).round(2)
df["4회차 예상"] = df.apply(predict_4th_attempt, axis=1).round(0).astype(int)

# 컬럼 순서 재정렬: 이름, 종류, 1회차, 2회차, 3회차, 성장 퍼센티지
df = df[["이름", "종류", "1회차", "2회차", "3회차", "성장 퍼센티지", "4회차 예상"]]


# ──────────────────────────────────────────────────────────────
# 기능 1. CSV 업로드 → 데이터 표 + 응답자 수 요약
# ──────────────────────────────────────────────────────────────
st.subheader("① 전체 기록")

col1, col2, col3, col4 = st.columns(4)
col1.metric("👥 응답자 수", f"{len(df)}명")
col2.metric("📈 평균 1회차", f"{df['1회차'].mean():.0f}타")
col3.metric("🚀 평균 3회차", f"{df['3회차'].mean():.0f}타")
col4.metric("✨ 평균 성장률", f"+{df['성장 퍼센티지'].mean():.2f}%")

# 종류 컬럼에 색상 적용하는 함수
def color_category(v):
    if v == "단어":
        return "background-color: #E8F5E9; color: #2E7D32; font-weight: bold;"
    elif v == "문장":
        return "background-color: #FFFDE7; color: #F57C00; font-weight: bold;"
    elif v == "긴글연습":
        return "background-color: #E1F5FE; color: #0277BD; font-weight: bold;"
    return ""

# 스타일링 적용
styled_df = df.style.map(color_category, subset=["종류"]).format(
    {"성장 퍼센티지": "+{:.2f}%"}
)
st.dataframe(styled_df, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────
# 기능 2. 학생 선택 → 1·2·3회차 꺾은선 그래프
# ──────────────────────────────────────────────────────────────
st.subheader("② 학생별 성장 추이")

student = st.selectbox("학생을 선택하세요", df["이름"].tolist())
row = df[df["이름"] == student].iloc[0]
values = [row["1회차"], row["2회차"], row["3회차"]]
class_avg = [df["1회차"].mean(), df["2회차"].mean(), df["3회차"].mean()]

fig = go.Figure()
fig.add_trace(
    go.Scatter(
        x=["1회차", "2회차", "3회차"],
        y=class_avg,
        mode="lines+markers",
        name="학급 평균",
        line=dict(width=2, color="#bbbbbb", dash="dash"),
        marker=dict(size=8),
    )
)
fig.add_trace(
    go.Scatter(
        x=["1회차", "2회차", "3회차"],
        y=values,
        mode="lines+markers+text",
        name=student,
        text=[f"{int(v)}타" for v in values],
        textposition="top center",
        line=dict(width=3, color="#1f77b4"),
        marker=dict(size=14),
    )
)
fig.update_layout(
    title=f"{student} 학생의 타자 속도 변화",
    yaxis_title="타수",
    height=420,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

c1, c2, c3 = st.columns(3)
c1.metric("1회차", f"{int(row['1회차'])}타")
c2.metric("3회차", f"{int(row['3회차'])}타", delta=f"{int(row['3회차'] - row['1회차'])}타")
c3.metric("성장 퍼센티지", f"+{row['성장 퍼센티지']:.2f}%")


# ──────────────────────────────────────────────────────────────
# 기능 3. "타자수 상승률" 버튼 → 학급 전체 요약 표
# ──────────────────────────────────────────────────────────────
st.subheader("③ 학급 전체 상승률 요약")

if st.button("📊 타자수 상승률 보기", type="primary"):
    summary = df[["이름", "종류", "1회차", "3회차", "성장 퍼센티지"]].copy()
    summary = summary.sort_values("성장 퍼센티지", ascending=False).reset_index(drop=True)
    summary.insert(0, "순위", summary.index + 1)

    def color_growth(v):
        if v >= 50:
            return "background-color: #d4edda; color: #155724"
        if v >= 0:
            return "background-color: #fff3cd; color: #856404"
        return "background-color: #f8d7da; color: #721c24"

    styled = summary.style.map(color_growth, subset=["성장 퍼센티지"]).map(color_category, subset=["종류"]).format(
        {"성장 퍼센티지": "+{:.2f}%"}
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.caption("🟢 +50% 이상 · 🟡 0~50% · 🔴 0% 미만 (퇴보)")


# ──────────────────────────────────────────────────────────────
# 기능 4. 종류별 학생 분류 명단
# ──────────────────────────────────────────────────────────────
st.subheader("④ 종류별 학생 명단")

categories = ["단어", "문장", "긴글연습"]
tab_columns = st.tabs([f"📋 {cat} ({len(df[df['종류'] == cat])}명)" for cat in categories])

for idx, (tab, category) in enumerate(zip(tab_columns, categories)):
    with tab:
        category_df = df[df["종류"] == category].sort_values("성장 퍼센티지", ascending=False).reset_index(drop=True)
        
        if len(category_df) == 0:
            st.info(f"해당 카테고리에 학생이 없습니다.")
        else:
            display_df = category_df[["이름", "1회차", "2회차", "3회차", "성장 퍼센티지"]].copy()
            display_df.insert(0, "순번", range(1, len(display_df) + 1))
            
            def color_category_growth(v):
                if isinstance(v, (int, float)):
                    if v >= 50:
                        return "background-color: #d4edda; color: #155724"
                    if v >= 0:
                        return "background-color: #fff3cd; color: #856404"
                    return "background-color: #f8d7da; color: #721c24"
                return ""
            
            styled_display = display_df.style.map(color_category_growth, subset=["성장 퍼센티지"]).format(
                {"성장 퍼센티지": "+{:.2f}%"}
            )
            st.dataframe(styled_display, use_container_width=True, hide_index=True)
            
            # 통계 정보
            col_a, col_b, col_c = st.columns(3)
            col_a.metric(f"{category} 평균 1회차", f"{category_df['1회차'].mean():.0f}타")
            col_b.metric(f"{category} 평균 3회차", f"{category_df['3회차'].mean():.0f}타")
            col_c.metric(f"{category} 평균 성장률", f"+{category_df['성장 퍼센티지'].mean():.2f}%")


# ──────────────────────────────────────────────────────────────
# 기능 5. 4회차 예상 타자 횟수 & 격려 메시지
# ──────────────────────────────────────────────────────────────
st.subheader("⑤ 🎯 4회차 예상 타자 속도 & 격려 메시지")

st.markdown("**선택한 학생의 현재 성장 추세를 바탕으로 4회차 예상 타자 속도를 예측합니다.**")

student_name = st.selectbox("격려 메시지를 받을 학생을 선택하세요", df["이름"].tolist(), key="encouragement_student")
student_row = df[df["이름"] == student_name].iloc[0]

emoji, message, detail = get_encouragement_message(
    student_row["성장 퍼센티지"],
    student_row["4회차 예상"],
    student_row["3회차"]
)

# 격려 메시지 표시
col_msg1, col_msg2 = st.columns([1, 3])
with col_msg1:
    st.markdown(f"<h1 style='text-align: center; font-size: 50px;'>{emoji}</h1>", unsafe_allow_html=True)
with col_msg2:
    st.markdown(f"""
    <div style='background-color: #FFE4E1; padding: 20px; border-radius: 10px; border-left: 5px solid #FF69B4;'>
        <h3 style='color: #C2185B; margin: 0;'>{student_name} 학생에게 드리는 말씀</h3>
        <h2 style='color: #2C3E50; margin: 10px 0;'>{message}</h2>
        <p style='color: #555; font-size: 16px; margin: 10px 0;'>{detail}</p>
    </div>
    """, unsafe_allow_html=True)

# 예측 데이터 표시
st.markdown("---")

col_pred1, col_pred2, col_pred3, col_pred4 = st.columns(4)
col_pred1.metric("📊 1회차", f"{int(student_row['1회차'])}타")
col_pred2.metric("📈 2회차", f"{int(student_row['2회차'])}타")
col_pred3.metric("🚀 3회차", f"{int(student_row['3회차'])}타")
col_pred4.metric("⭐ 4회차 예상", f"{int(student_row['4회차 예상'])}타")

# 예측 그래프
fig_pred = go.Figure()
fig_pred.add_trace(
    go.Scatter(
        x=["1회차", "2회차", "3회차", "4회차(예상)"],
        y=[student_row["1회차"], student_row["2회차"], student_row["3회차"], student_row["4회차 예상"]],
        mode="lines+markers+text",
        name=student_name,
        text=[
            f"{int(student_row['1회차'])}타",
            f"{int(student_row['2회차'])}타",
            f"{int(student_row['3회차'])}타",
            f"{int(student_row['4회차 예상'])}타"
        ],
        textposition="top center",
        line=dict(width=3, color="#FF1493"),
        marker=dict(size=12, color=["#1f77b4", "#1f77b4", "#1f77b4", "#FFD700"]),
        fill="tozeroy",
        fillcolor="rgba(255, 20, 147, 0.1)"
    )
)

fig_pred.update_layout(
    title=f"{student_name} 학생의 예상 성장 곡선",
    yaxis_title="타수",
    xaxis_title="회차",
    height=400,
    hovermode="x unified",
    plot_bgcolor="rgba(240, 240, 240, 0.5)",
    paper_bgcolor="#FFE4E1",
)

st.plotly_chart(fig_pred, use_container_width=True)

# 전체 학생 4회차 예상 비교표
st.markdown("---")
st.markdown("**📋 전체 학생 4회차 예상 타자 속도 비교**")

all_prediction_df = df[["이름", "종류", "1회차", "2회차", "3회차", "4회차 예상", "성장 퍼센티지"]].copy()
all_prediction_df = all_prediction_df.sort_values("4회차 예상", ascending=False).reset_index(drop=True)
all_prediction_df.insert(0, "순위", range(1, len(all_prediction_df) + 1))

def color_category_pred(v):
    if v == "단어":
        return "background-color: #E8F5E9; color: #2E7D32; font-weight: bold;"
    elif v == "문장":
        return "background-color: #FFFDE7; color: #F57C00; font-weight: bold;"
    elif v == "긴글연습":
        return "background-color: #E1F5FE; color: #0277BD; font-weight: bold;"
    return ""

styled_all_pred = all_prediction_df.style.map(color_category_pred, subset=["종류"]).format(
    {"성장 퍼센티지": "+{:.2f}%"}
)
st.dataframe(styled_all_pred, use_container_width=True, hide_index=True)

st.caption("💡 **예측 방식**: 1·2·3회차 데이터의 선형 추세를 바탕으로 4회차를 예측했습니다. ⭐ 표시는 예상 성장으로, 이를 목표로 노력해봅시다!")
