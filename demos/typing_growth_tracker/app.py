import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import numpy as np
from urllib.parse import quote, parse_qs, urlparse
import qrcode
from datetime import datetime

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

# 한컴타자연습 긴글 목록 (난이도별로 정렬)
TYPING_MATERIALS = [
    {"제목": "애국가", "난이도": "초급", "설명": "우리나라 국가"},
    {"제목": "겨울밤", "난이도": "초급", "설명": "겨울 풍경을 묘사한 글"},
    {"제목": "봄날의 산책", "난이도": "초급", "설명": "봄 계절 산책 이야기"},
    {"제목": "추억의 학창시절", "난이도": "초급", "설명": "학교 시절 추억"},
    {"제목": "명시 - 산유화", "난이도": "중급", "설명": "고전 명시"},
    {"제목": "동시 - 별", "난이도": "중급", "설명": "아동 동시"},
    {"제목": "수필 - 부모님과의 시간", "난이도": "중급", "설명": "일상 수필"},
    {"제목": "현대시 - 사막의 꽃", "난이도": "중급", "설명": "현대 시조"},
    {"제목": "소설 발췌 - 제주 여행", "난이도": "중급", "설명": "여행기 소설"},
    {"제목": "에세이 - 하루의 의미", "난이도": "중급", "설명": "인생 에세이"},
    {"제목": "고전 문장 - 논어", "난이도": "상급", "설명": "논어의 명언"},
    {"제목": "단편소설 - 시간 여행자", "난이도": "상급", "설명": "단편 소설"},
    {"제목": "장편 발췌 - 삼국지", "난이도": "상급", "설명": "고전 문학"},
    {"제목": "수필 - 인생 그 자체", "난이도": "상급", "설명": "철학적 수필"},
    {"제목": "현대문학 - 바람과 함께", "난이도": "상급", "설명": "현대 문학작품"},
]

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
    
    # 생년월일 컬럼 확인
    if "생년월일" not in df.columns:
        errors.append(f"필수 컬럼 누락: 생년월일. 필요한 컬럼: {REQUIRED_COLS + ['생년월일']}")
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
    """3회차까지의 성장 추세를 바탕으로 4회차 예상 타자 횟수를 예측"""
    val1 = row["1회차"]
    val2 = row["2회차"]
    val3 = row["3회차"]
    
    # 1→2 증가량, 2→3 증가량
    increase_1_2 = val2 - val1
    increase_2_3 = val3 - val2
    
    # 평균 증가량으로 4회차 예측
    avg_increase = (increase_1_2 + increase_2_3) / 2
    prediction = val3 + avg_increase
    
    return max(0, prediction)


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


def get_recommended_materials(current_speed):
    """현재 타수를 기반으로 추천 긴글을 선별"""
    if current_speed < 80:
        difficulty = "초급"
        color = "🟢"
    elif current_speed < 130:
        difficulty = "중급"
        color = "🟡"
    else:
        difficulty = "상급"
        color = "🔴"
    
    # 같은 난이도의 글들 필터링
    recommended = [m for m in TYPING_MATERIALS if m["난이도"] == difficulty]
    
    return difficulty, color, recommended


def generate_qr(url):
    """QR 코드 생성"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")


with st.sidebar:
    st.header("📂 데이터 업로드")
    uploaded = st.file_uploader("학생 타자 기록 CSV", type=["csv"])
    st.markdown(
        """
        **필수 컬럼**
        - `이름` (문자열)
        - `생년월일` (6자리, 예: 240315)
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
            "이름,생년월일,종류,1회차,2회차,3회차\n김민준,240315,단어,120,145,180\n이서연,240528,문장,95,110,135\n...",
            language="csv",
        )
    st.stop()

df = read_csv_any(uploaded)

# 생년월일 컬럼 확인
if "생년월일" not in df.columns:
    st.error("❌ CSV 파일에 '생년월일' 컬럼이 없습니다. 다시 확인해주세요.")
    st.stop()

errs = validate(df)
if errs:
    for e in errs:
        st.error(e)
    st.stop()

df["성장 퍼센티지"] = ((df["3회차"] - df["1회차"]) / df["1회차"] * 100).round(2)
df["4회차 예상"] = df.apply(predict_4th_attempt, axis=1).round(0).astype(int)

# 컬럼 순서 재정렬: 이름, 종류, 1회차, 2회차, 3회차, 성장 퍼센티지
df = df[["이름", "생년월일", "종류", "1회차", "2회차", "3회차", "성장 퍼센티지", "4회차 예상"]]

# URL 파라미터에서 학생 정보 가져오기 (익명 모드)
query_params = st.query_params
student_name_param = query_params.get("name", None)
birthdate_param = query_params.get("birth", None)

# 익명 모드 여부 확인
is_anonymous_mode = student_name_param is not None and birthdate_param is not None

if is_anonymous_mode:
    # 학생 검증
    matching_students = df[(df["이름"] == student_name_param) & (df["생년월일"].astype(str) == birthdate_param)]
    
    if len(matching_students) == 0:
        st.error("❌ 입력된 이름과 생년월일이 일치하지 않습니다. 다시 시도해주세요.")
        st.stop()
    
    student_row = matching_students.iloc[0]
    
    st.markdown("""
    <style>
        body { background-color: #FFE4E1 !important; }
    </style>
    """, unsafe_allow_html=True)
    
    # 익명 모드 헤더
    st.markdown("---")
    st.subheader("👤 나의 성장 현황 (익명)")
    
    # 개인 격려 메시지
    emoji, message, detail = get_encouragement_message(
        student_row["성장 퍼센티지"],
        student_row["4회차 예상"],
        student_row["3회차"]
    )
    
    col_msg1, col_msg2 = st.columns([1, 3])
    with col_msg1:
        st.markdown(f"<h1 style='text-align: center; font-size: 50px;'>{emoji}</h1>", unsafe_allow_html=True)
    with col_msg2:
        st.markdown(f"""
        <div style='background-color: #FFE4E1; padding: 20px; border-radius: 10px; border-left: 5px solid #FF69B4;'>
            <h2 style='color: #2C3E50; margin: 10px 0;'>{message}</h2>
            <p style='color: #555; font-size: 16px; margin: 10px 0;'>{detail}</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 개인 성적
    st.subheader("📊 개인 성적")
    col_pred1, col_pred2, col_pred3, col_pred4 = st.columns(4)
    col_pred1.metric("1회차", f"{int(student_row['1회차'])}타")
    col_pred2.metric("2회차", f"{int(student_row['2회차'])}타")
    col_pred3.metric("3회차", f"{int(student_row['3회차'])}타")
    col_pred4.metric("4회차 예상", f"{int(student_row['4회차 예상'])}타")
    
    # 개인 그래프
    fig_personal = go.Figure()
    fig_personal.add_trace(
        go.Scatter(
            x=["1회차", "2회차", "3회차", "4회차(예상)"],
            y=[student_row["1회차"], student_row["2회차"], student_row["3회차"], student_row["4회차 예상"]],
            mode="lines+markers+text",
            name="나의 성장",
            text=[
                f"{int(student_row['1회차'])}",
                f"{int(student_row['2회차'])}",
                f"{int(student_row['3회차'])}",
                f"{int(student_row['4회차 예상'])}"
            ],
            textposition="top center",
            line=dict(width=3, color="#FF1493"),
            marker=dict(size=12, color=["#1f77b4", "#1f77b4", "#1f77b4", "#FFD700"]),
            fill="tozeroy",
            fillcolor="rgba(255, 20, 147, 0.1)"
        )
    )
    fig_personal.update_layout(
        title="개인 성장 곡선",
        yaxis_title="타수",
        xaxis_title="회차",
        height=400,
        plot_bgcolor="rgba(240, 240, 240, 0.5)",
        paper_bgcolor="#FFE4E1",
    )
    st.plotly_chart(fig_personal, use_container_width=True)
    
    st.markdown("---")
    
    # 반 평균 그래프
    st.subheader("📈 반 평균")
    class_avg = [df["1회차"].mean(), df["2회차"].mean(), df["3회차"].mean()]
    
    fig_class = go.Figure()
    fig_class.add_trace(
        go.Scatter(
            x=["1회차", "2회차", "3회차"],
            y=class_avg,
            mode="lines+markers+text",
            name="반 평균",
            text=[f"{avg:.0f}" for avg in class_avg],
            textposition="top center",
            line=dict(width=3, color="#2E7D32"),
            marker=dict(size=12, color="#2E7D32"),
            fill="tozeroy",
            fillcolor="rgba(46, 125, 50, 0.1)"
        )
    )
    fig_class.update_layout(
        title="반 평균 성장 곡선",
        yaxis_title="타수",
        xaxis_title="회차",
        height=400,
        plot_bgcolor="rgba(240, 240, 240, 0.5)",
        paper_bgcolor="#FFE4E1",
    )
    st.plotly_chart(fig_class, use_container_width=True)
    
    st.markdown("---")
    
    # 반 구성 (익명)
    st.subheader("👥 반 구성 현황")
    categories = ["단어", "문장", "긴글연습"]
    cat_counts = [len(df[df["종류"] == cat]) for cat in categories]
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📋 단어", f"{cat_counts[0]}명")
    col2.metric("📝 문장", f"{cat_counts[1]}명")
    col3.metric("📚 긴글연습", f"{cat_counts[2]}명")
    
    # 원형 차트
    fig_pie = go.Figure(data=[go.Pie(
        labels=categories,
        values=cat_counts,
        marker=dict(colors=["#2E7D32", "#F57C00", "#0277BD"]),
        textinfo="label+value",
        hovertemplate="<b>%{label}</b><br>%{value}명<extra></extra>"
    )])
    fig_pie.update_layout(
        title="반 학생 분포",
        height=400,
        paper_bgcolor="#FFE4E1",
    )
    st.plotly_chart(fig_pie, use_container_width=True)
    
    st.markdown("---")
    
    # 📚 다음 도전할 긴글 추천
    st.subheader("📚 다음 도전할 긴글 추천")
    
    current_speed = student_row["3회차"]
    difficulty, color_emoji, recommended_materials = get_recommended_materials(current_speed)
    
    st.markdown(f"""
    <div style='background-color: #FFF9C4; padding: 15px; border-radius: 10px; border-left: 5px solid #FBC02D;'>
        <p style='color: #F57F17; font-size: 16px; margin: 0;'>
            <b>💡 현재 타수: {int(current_speed)}타</b><br>
            <b>추천 난이도: {color_emoji} {difficulty}</b><br>
            아래의 긴글을 연습하면 좋습니다!
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("")
    
    # 추천 긴글 목록
    cols = st.columns(2)
    for idx, material in enumerate(recommended_materials):
        with cols[idx % 2]:
            st.markdown(f"""
            <div style='background-color: white; padding: 15px; border-radius: 10px; border: 2px solid #E91E63; margin: 10px 0;'>
                <h4 style='color: #E91E63; margin: 0 0 10px 0;'>✨ {material['제목']}</h4>
                <p style='color: #666; margin: 0; font-size: 14px;'>{material['설명']}</p>
                <p style='color: #999; margin: 5px 0 0 0; font-size: 12px;'>난이도: {material['난이도']}</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.success("✅ 성장 현황 조회 완료! 화이팅! 💪")
    st.stop()

# ──────────────────────────────────────────────────────────────
# 교사 모드
# ──────────────────────────────────────────────────────────────

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

st.caption("💡 **예측 방식**: 1·2·3회차의 평균 증가량을 바탕으로 4회차를 예측했습니다. ⭐ 표시는 예상 성장으로, 이를 목표로 노력해봅시다!")


# ──────────────────────────────────────────────────────────────
# 기능 6. 익명 모드 QR & 링크 배포
# ──────────────────────────────────────────────────────────────
st.subheader("⑥ 📱 익명 모드 - QR 코드 & 링크 배포")

st.markdown("**모든 학생이 동일한 QR을 스캔하여 자신의 이름과 생년월일로 접속합니다.**")

# 배포 URL 설정
base_url = st.secrets.get("BASE_URL", "http://localhost:8501")
student_mode_url = f"{base_url}?name={{이름}}&birth={{생년월일}}"

st.markdown("---")

# QR 코드 생성 (기본 URL - 학생들이 직접 입력)
qr_url = base_url
qr_img = generate_qr(qr_url)

col_qr1, col_qr2 = st.columns([1, 2])
with col_qr1:
    st.markdown("**📱 공용 QR 코드**")
    st.image(qr_img, caption="모든 학생이 스캔할 QR")
    
    # QR 이미지 다운로드
    buf = io.BytesIO()
    qr_img.save(buf, format="PNG")
    buf.seek(0)
    
    st.download_button(
        label="📥 QR 이미지 다운로드",
        data=buf,
        file_name="class_qr.png",
        mime="image/png"
    )

with col_qr2:
    st.markdown("**🔗 공용 링크**")
    st.code(base_url, language="text")
    st.info("""
    📌 **접속 방법:**
    1. QR을 스캔하거나 위 링크 클릭
    2. 자신의 **이름** 입력
    3. **생년월일 6자리** 입력 (예: 240315)
    4. ✅ 본인 성적 확인!
    
    💡 **익명 처리:**
    - 이름과 생년월일로만 본인 데이터 조회 가능
    - 다른 학생 정보는 보이지 않음
    - 반 평균와 반 구성만 공개
    """)

st.markdown("---")

# 학생별 개별 URL 리스트 (참고용)
st.markdown("**📋 학생별 개별 URL (참고용)**")

with st.expander("학생별 링크 보기"):
    for idx, (_, row) in enumerate(df.iterrows(), 1):
        student_url = f"{base_url}?name={row['이름']}&birth={row['생년월일']}"
        st.write(f"{idx}. **{row['이름']}**: {student_url}")

# 설정 안내
st.warning("""
⚠️ **중요 설정:**
- `BASE_URL`을 `.streamlit/secrets.toml` 파일에 설정하세요
- 예: `BASE_URL = "https://your-streamlit-app-url.com"`
- Streamlit Cloud 배포 시 환경 변수에서 설정하세요
""")
