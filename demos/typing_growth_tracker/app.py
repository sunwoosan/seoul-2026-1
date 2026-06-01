import io

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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


def generate_pdf(df: pd.DataFrame) -> bytes:
    """전체 결과를 PDF로 생성 (한 페이지)"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=10*mm, bottomMargin=10*mm, 
                           leftMargin=10*mm, rightMargin=10*mm)
    
    story = []
    styles = getSampleStyleSheet()
    
    # 제목
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=6,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    story.append(Paragraph("⌨️ 타자 성장 트래커 - 종합 보고서", title_style))
    
    # 생성 날짜
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#7F8C8D'),
        alignment=TA_CENTER,
        spaceAfter=10
    )
    story.append(Paragraph(f"생성일: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}", date_style))
    
    # 전체 요약 메트릭
    summary_data = [
        ["응답자 수", "평균 1회차", "평균 2회차", "평균 3회차", "평균 성장률"],
        [
            f"{len(df)}명",
            f"{df['1회차'].mean():.0f}타",
            f"{df['2회차'].mean():.0f}타",
            f"{df['3회차'].mean():.0f}타",
            f"+{df['성장 퍼센티지'].mean():.2f}%"
        ]
    ]
    
    summary_table = Table(summary_data, colWidths=[25*mm, 25*mm, 25*mm, 25*mm, 25*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FFB6D9')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFEF0'), colors.white]),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6*mm))
    
    # 종류별 데이터
    categories = ["단어", "문장", "긴글연습"]
    
    for category in categories:
        category_df = df[df["종류"] == category].sort_values("성장 퍼센티지", ascending=False).reset_index(drop=True)
        
        if len(category_df) > 0:
            # 카테고리 제목
            cat_style = ParagraphStyle(
                'CatTitle',
                parent=styles['Heading2'],
                fontSize=11,
                textColor=colors.white,
                spaceAfter=4,
                alignment=TA_CENTER,
                fontName='Helvetica-Bold'
            )
            
            if category == "단어":
                bg_color = colors.HexColor('#2E7D32')
            elif category == "문장":
                bg_color = colors.HexColor('#F57C00')
            else:
                bg_color = colors.HexColor('#0277BD')
            
            # 카테고리 헤더
            cat_header = Table([[Paragraph(f"{category} ({len(category_df)}명)", cat_style)]], 
                              colWidths=[125*mm])
            cat_header.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), bg_color),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(cat_header)
            
            # 학생 데이터 테이블
            table_data = [["순번", "이름", "1회차", "2회차", "3회차", "성장률"]]
            for idx, (_, row) in enumerate(category_df.iterrows()):
                table_data.append([
                    str(idx + 1),
                    str(row["이름"]),
                    f"{int(row['1회차'])}",
                    f"{int(row['2회차'])}",
                    f"{int(row['3회차'])}",
                    f"+{row['성장 퍼센티지']:.1f}%"
                ])
            
            table = Table(table_data, colWidths=[12*mm, 25*mm, 18*mm, 18*mm, 18*mm, 20*mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E8E8E8')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
                ('TOPPADDING', (0, 0), (-1, 0), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FAFAFA'), colors.white]),
            ]))
            story.append(table)
            story.append(Spacer(1, 4*mm))
    
    # PDF 생성
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


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

# 컬럼 순서 재정렬: 이름, 종류, 1회차, 2회차, 3회차, 성장 퍼센티지
df = df[["이름", "종류", "1회차", "2회차", "3회차", "성장 퍼센티지"]]


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
# 기능 5. PDF 다운로드 버튼
# ──────────────────────────────────────────────────────────────
st.subheader("⑤ PDF 보고서 다운로드")

col_pdf_1, col_pdf_2 = st.columns([1, 3])
with col_pdf_1:
    if st.button("📄 PDF 생성", type="secondary"):
        pdf_bytes = generate_pdf(df)
        st.session_state.pdf_ready = True
        st.session_state.pdf_data = pdf_bytes

if hasattr(st.session_state, 'pdf_ready') and st.session_state.pdf_ready:
    with col_pdf_2:
        st.download_button(
            label="⬇️ PDF 다운로드",
            data=st.session_state.pdf_data,
            file_name=f"타자성장트래커_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mime="application/pdf",
            type="primary"
        )
    st.success("✅ PDF가 준비되었습니다. 한 페이지(가로 방향)로 모든 결과가 포함되어 있습니다.")
    st.info("💡 **프린트 팁**: 브라우저의 인쇄 설정에서 '배경색 및 이미지' 옵션을 켜면 더 예쁘게 출력됩니다.")
