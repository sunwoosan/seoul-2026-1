import io
import os
import json
import base64

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# QR / PDF 생성용
import qrcode
import qrcode.constants
from PIL import Image, ImageDraw, ImageFont

# ──────────────────────────────────────────────────────────────
# 배포 / 실행 안내 (요약)
#   requirements.txt: streamlit, pandas, plotly, qrcode, pillow, numpy
#   packages.txt:     fonts-nanum   (Streamlit Cloud에서 한글 PDF 출력용)
#   QR 기능은 앱이 외부에서 접속 가능한 URL로 배포되어 있어야 동작한다.
#   로컬(localhost) 실행 시 생성된 QR은 같은 PC에서만 열린다.
# ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="타자 성장 트래커",
    page_icon="⌨️",
    layout="wide",
)

# 배경색을 연한 핑크로 설정
st.markdown(
    """
    <style>
        .stApp { background-color: #FFE4E1; }
    </style>
    """,
    unsafe_allow_html=True,
)


REQUIRED_COLS = ["이름", "종류", "1회차", "2회차", "3회차"]
VALID_TYPES = ["단어", "문장", "긴글연습"]


# ==============================================================
# 공통 계산 함수
# ==============================================================
def predict_4th(v1, v2, v3):
    """1·2·3회차의 평균 증가량으로 4회차를 선형 외삽한다."""
    avg_increase = ((v2 - v1) + (v3 - v2)) / 2
    return max(0, v3 + avg_increase)


def growth_percent(v1, v3):
    if v1 <= 0:
        return 0.0
    return round((v3 - v1) / v1 * 100, 2)


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


def build_growth_figure(name, v1, v2, v3, v4):
    """4회차 예상 성장 곡선 (학생/교사 화면 공용)"""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=["1회차", "2회차", "3회차", "4회차(예상)"],
            y=[v1, v2, v3, v4],
            mode="lines+markers+text",
            name=name,
            text=[f"{int(v1)}타", f"{int(v2)}타", f"{int(v3)}타", f"{int(v4)}타"],
            textposition="top center",
            line=dict(width=3, color="#FF1493"),
            marker=dict(size=12, color=["#1f77b4", "#1f77b4", "#1f77b4", "#FFD700"]),
            fill="tozeroy",
            fillcolor="rgba(255, 20, 147, 0.1)",
        )
    )
    fig.update_layout(
        title=f"{name} 학생의 예상 성장 곡선",
        yaxis_title="타수",
        xaxis_title="회차",
        height=400,
        hovermode="x unified",
        plot_bgcolor="rgba(240, 240, 240, 0.5)",
        paper_bgcolor="#FFE4E1",
    )
    return fig


# ==============================================================
# 학생 데이터 인코딩 / 디코딩 (URL 토큰)
#   토큰은 base64 인코딩일 뿐 암호화가 아니다.
#   타자 기록(이름·타수) 수준이라 민감도는 낮으나, URL을 아는 사람은
#   내용을 복원할 수 있다는 점에 유의한다.
# ==============================================================
def encode_student(name, ctype, scores):
    payload = {"n": str(name), "t": str(ctype), "s": [int(x) for x in scores]}
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_student(token):
    raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
    d = json.loads(raw)
    return d["n"], d["t"], list(d["s"])


# ==============================================================
# 한글 폰트 로더 (PDF 출력용, Pillow 기반)
#   reportlab은 Noto Sans CJK 같은 CFF 폰트를 임베드하지 못하므로
#   freetype 기반 Pillow로 페이지를 그려 PDF로 저장한다.
# ==============================================================
FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", 0),
    ("/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 0),
    ("/Library/Fonts/NanumGothic.ttf", 0),
    ("/System/Library/Fonts/AppleSDGothicNeo.ttc", 0),
    ("/System/Library/Fonts/Supplemental/AppleGothic.ttf", 0),
    ("C:/Windows/Fonts/malgun.ttf", 0),
    ("C:/Windows/Fonts/gulim.ttc", 0),
]


def get_font_loader(uploaded_font):
    """(loader_fn, label, korean_ok) 를 반환한다."""
    if uploaded_font is not None:
        data = uploaded_font.getvalue()
        try:
            test = ImageFont.truetype(io.BytesIO(data), 20)
            test.getlength("가")

            def loader(size, _d=data):
                return ImageFont.truetype(io.BytesIO(_d), size)

            return loader, uploaded_font.name, True
        except Exception:
            pass

    for path, idx in FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                ImageFont.truetype(path, 20, index=idx)

                def loader(size, _p=path, _i=idx):
                    return ImageFont.truetype(_p, size, index=_i)

                return loader, os.path.basename(path), True
            except Exception:
                continue

    def loader(size):
        return ImageFont.load_default()

    return loader, "기본 폰트(한글 미지원)", False


def make_qr_img(data, px):
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((px, px), Image.NEAREST)


def build_qr_pdf(records, base_url, font_loader, cols=3, rows=4, dpi=200):
    """records: [{'n','t','s'}] -> 멀티페이지 PDF bytes"""
    a4_w = round(210 / 25.4 * dpi)
    a4_h = round(297 / 25.4 * dpi)
    margin = round(14 / 25.4 * dpi)
    cell_w = (a4_w - 2 * margin) // cols
    cell_h = (a4_h - 2 * margin) // rows
    qr_px = int(min(cell_w, cell_h) * 0.60)

    name_font = font_loader(int(dpi * 0.16))
    type_font = font_loader(int(dpi * 0.11))
    url_font = font_loader(int(dpi * 0.05))

    per_page = cols * rows
    pages = []
    page = None
    draw = None

    for i, s in enumerate(records):
        pos = i % per_page
        if pos == 0:
            page = Image.new("RGB", (a4_w, a4_h), "white")
            draw = ImageDraw.Draw(page)
            pages.append(page)

        r, col = divmod(pos, cols)
        cx = margin + col * cell_w + cell_w // 2
        cell_top = margin + r * cell_h

        token = encode_student(s["n"], s["t"], s["s"])
        url = f"{base_url}?student={token}"

        qr_top = cell_top + int(dpi * 0.06)
        qr = make_qr_img(url, qr_px)
        page.paste(qr, (cx - qr_px // 2, qr_top))

        ny = qr_top + qr_px + int(dpi * 0.05)
        labels = [
            (str(s["n"]), name_font, 0),
            (str(s["t"]), type_font, int(dpi * 0.20)),
        ]
        for text, fnt, gap in labels:
            bbox = draw.textbbox((0, 0), text, font=fnt)
            tw = bbox[2] - bbox[0]
            draw.text((cx - tw // 2, ny + gap), text, fill="black", font=fnt)

    if not pages:
        page = Image.new("RGB", (a4_w, a4_h), "white")
        pages.append(page)

    buf = io.BytesIO()
    pages[0].save(
        buf,
        format="PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=dpi,
    )
    return buf.getvalue(), len(pages)


# ==============================================================
# 학생 뷰 (QR 접속 시)
# ==============================================================
def render_student_view(token):
    # 학생 화면에서는 사이드바를 숨긴다.
    st.markdown(
        "<style>[data-testid='stSidebar']{display:none;}</style>",
        unsafe_allow_html=True,
    )

    try:
        name, ctype, scores = decode_student(token)
        v1, v2, v3 = scores[0], scores[1], scores[2]
    except Exception:
        st.error("리포트 정보를 읽을 수 없습니다. QR 코드를 다시 확인해주세요.")
        st.stop()

    v4 = round(predict_4th(v1, v2, v3))
    gr = growth_percent(v1, v3)
    emoji, message, detail = get_encouragement_message(gr, v4, v3)

    st.title(f"⌨️ {name} 학생의 타자 성장 리포트")
    st.caption(f"연습 종류: {ctype}")

    col_msg1, col_msg2 = st.columns([1, 3])
    with col_msg1:
        st.markdown(
            f"<h1 style='text-align:center; font-size:60px;'>{emoji}</h1>",
            unsafe_allow_html=True,
        )
    with col_msg2:
        st.markdown(
            f"""
            <div style='background-color:#FFFFFF; padding:20px; border-radius:10px; border-left:6px solid #FF69B4;'>
                <h3 style='color:#C2185B; margin:0;'>{name} 학생에게</h3>
                <h2 style='color:#2C3E50; margin:10px 0;'>{message}</h2>
                <p style='color:#555; font-size:16px; margin:10px 0;'>{detail}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📊 1회차", f"{int(v1)}타")
    c2.metric("📈 2회차", f"{int(v2)}타")
    c3.metric("🚀 3회차", f"{int(v3)}타", delta=f"{int(v3 - v1)}타")
    c4.metric("⭐ 4회차 예상", f"{int(v4)}타")
    c5.metric("✨ 성장률", f"+{gr:.2f}%")

    st.plotly_chart(
        build_growth_figure(name, v1, v2, v3, v4), use_container_width=True
    )
    st.caption(
        "💡 4회차 예상은 1·2·3회차의 평균 증가량으로 계산한 참고값입니다. ⭐ 표시를 목표로 연습해봅시다."
    )
    st.stop()


# ==============================================================
# 라우팅: 토큰이 있으면 학생 뷰
# ==============================================================
_token = st.query_params.get("student")
if _token:
    render_student_view(_token)


# ==============================================================
# 교사 뷰
# ==============================================================
st.title("⌨️ 타자 성장 트래커")
st.caption("결과보다 성장 과정을 본다 — 학생들의 1·2·3회차 타자 속도 변화 시각화 도구")


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

    if not df["종류"].isin(VALID_TYPES).all():
        errors.append(f"종류 컬럼에 유효하지 않은 값이 있습니다. 허용 값: {VALID_TYPES}")

    for col in ["1회차", "2회차", "3회차"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[["1회차", "2회차", "3회차"]].isna().any().any():
        errors.append("1~3회차 컬럼에 숫자가 아닌 값이 있습니다. CSV를 확인하세요.")
    if (df["1회차"] <= 0).any():
        errors.append("1회차에 0 또는 음수가 있어 성장률 계산이 불가능한 학생이 있습니다.")
    return errors


def color_category(v):
    if v == "단어":
        return "background-color: #E8F5E9; color: #2E7D32; font-weight: bold;"
    elif v == "문장":
        return "background-color: #FFFDE7; color: #F57C00; font-weight: bold;"
    elif v == "긴글연습":
        return "background-color: #E1F5FE; color: #0277BD; font-weight: bold;"
    return ""


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
        """
    )

    st.divider()
    st.header("🔗 QR 설정")
    auto_host = ""
    try:
        host = st.context.headers.get("Host", "")
        if host and "localhost" not in host and "127.0.0.1" not in host:
            auto_host = f"https://{host}/"
    except Exception:
        auto_host = ""

    base_url = st.text_input(
        "앱 배포 URL (Base URL)",
        value=auto_host,
        placeholder="https://내앱주소.streamlit.app/",
        help="배포된 앱 주소를 넣으세요. 이 주소를 기준으로 학생별 QR 링크가 만들어집니다.",
    )
    st.caption("QR은 외부 접속이 가능한 배포 URL에서만 열립니다. 로컬 주소는 같은 PC에서만 동작합니다.")

    st.divider()
    st.header("🔤 PDF 한글 폰트")
    uploaded_font = st.file_uploader(
        "한글 폰트(.ttf/.otf) 업로드 (선택)", type=["ttf", "otf"]
    )
    st.caption(
        "시스템에 한글 폰트가 없으면 PDF의 학생 이름이 깨질 수 있습니다. "
        "Streamlit Cloud는 packages.txt에 fonts-nanum 추가를 권장합니다."
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
df["4회차 예상"] = df.apply(
    lambda r: predict_4th(r["1회차"], r["2회차"], r["3회차"]), axis=1
).round(0).astype(int)

df = df[["이름", "종류", "1회차", "2회차", "3회차", "성장 퍼센티지", "4회차 예상"]]


# ──────────────────────────────────────────────────────────────
# ① 전체 기록
# ──────────────────────────────────────────────────────────────
st.subheader("① 전체 기록")

c1, c2, c3, c4 = st.columns(4)
c1.metric("👥 응답자 수", f"{len(df)}명")
c2.metric("📈 평균 1회차", f"{df['1회차'].mean():.0f}타")
c3.metric("🚀 평균 3회차", f"{df['3회차'].mean():.0f}타")
c4.metric("✨ 평균 성장률", f"+{df['성장 퍼센티지'].mean():.2f}%")

styled_df = df.style.map(color_category, subset=["종류"]).format(
    {"성장 퍼센티지": "+{:.2f}%"}
)
st.dataframe(styled_df, use_container_width=True, hide_index=True)


# ──────────────────────────────────────────────────────────────
# ② 학생별 성장 추이
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

cc1, cc2, cc3 = st.columns(3)
cc1.metric("1회차", f"{int(row['1회차'])}타")
cc2.metric("3회차", f"{int(row['3회차'])}타", delta=f"{int(row['3회차'] - row['1회차'])}타")
cc3.metric("성장 퍼센티지", f"+{row['성장 퍼센티지']:.2f}%")


# ──────────────────────────────────────────────────────────────
# ③ 학급 전체 상승률 요약
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

    styled = (
        summary.style.map(color_growth, subset=["성장 퍼센티지"])
        .map(color_category, subset=["종류"])
        .format({"성장 퍼센티지": "+{:.2f}%"})
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.caption("🟢 +50% 이상 · 🟡 0~50% · 🔴 0% 미만 (퇴보)")


# ──────────────────────────────────────────────────────────────
# ④ 종류별 학생 명단
# ──────────────────────────────────────────────────────────────
st.subheader("④ 종류별 학생 명단")

tab_columns = st.tabs(
    [f"📋 {cat} ({len(df[df['종류'] == cat])}명)" for cat in VALID_TYPES]
)

for tab, category in zip(tab_columns, VALID_TYPES):
    with tab:
        category_df = (
            df[df["종류"] == category]
            .sort_values("성장 퍼센티지", ascending=False)
            .reset_index(drop=True)
        )
        if len(category_df) == 0:
            st.info("해당 카테고리에 학생이 없습니다.")
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

            styled_display = display_df.style.map(
                color_category_growth, subset=["성장 퍼센티지"]
            ).format({"성장 퍼센티지": "+{:.2f}%"})
            st.dataframe(styled_display, use_container_width=True, hide_index=True)

            a, b, c = st.columns(3)
            a.metric(f"{category} 평균 1회차", f"{category_df['1회차'].mean():.0f}타")
            b.metric(f"{category} 평균 3회차", f"{category_df['3회차'].mean():.0f}타")
            c.metric(f"{category} 평균 성장률", f"+{category_df['성장 퍼센티지'].mean():.2f}%")


# ──────────────────────────────────────────────────────────────
# ⑤ 4회차 예상 & 격려 메시지 (교사 미리보기)
# ──────────────────────────────────────────────────────────────
st.subheader("⑤ 🎯 4회차 예상 타자 속도 & 격려 메시지")
st.markdown("선택한 학생의 현재 성장 추세를 바탕으로 4회차 예상 타자 속도를 예측합니다.")

student_name = st.selectbox(
    "격려 메시지를 미리 볼 학생을 선택하세요",
    df["이름"].tolist(),
    key="encouragement_student",
)
sr = df[df["이름"] == student_name].iloc[0]

emoji, message, detail = get_encouragement_message(
    sr["성장 퍼센티지"], sr["4회차 예상"], sr["3회차"]
)

m1, m2 = st.columns([1, 3])
with m1:
    st.markdown(
        f"<h1 style='text-align:center; font-size:50px;'>{emoji}</h1>",
        unsafe_allow_html=True,
    )
with m2:
    st.markdown(
        f"""
        <div style='background-color:#FFFFFF; padding:20px; border-radius:10px; border-left:5px solid #FF69B4;'>
            <h3 style='color:#C2185B; margin:0;'>{student_name} 학생에게 드리는 말씀</h3>
            <h2 style='color:#2C3E50; margin:10px 0;'>{message}</h2>
            <p style='color:#555; font-size:16px; margin:10px 0;'>{detail}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")
p1, p2, p3, p4 = st.columns(4)
p1.metric("📊 1회차", f"{int(sr['1회차'])}타")
p2.metric("📈 2회차", f"{int(sr['2회차'])}타")
p3.metric("🚀 3회차", f"{int(sr['3회차'])}타")
p4.metric("⭐ 4회차 예상", f"{int(sr['4회차 예상'])}타")

st.plotly_chart(
    build_growth_figure(
        student_name, sr["1회차"], sr["2회차"], sr["3회차"], sr["4회차 예상"]
    ),
    use_container_width=True,
)

st.markdown("---")
st.markdown("**📋 전체 학생 4회차 예상 타자 속도 비교**")
all_pred = df[["이름", "종류", "1회차", "2회차", "3회차", "4회차 예상", "성장 퍼센티지"]].copy()
all_pred = all_pred.sort_values("4회차 예상", ascending=False).reset_index(drop=True)
all_pred.insert(0, "순위", range(1, len(all_pred) + 1))
styled_all_pred = all_pred.style.map(color_category, subset=["종류"]).format(
    {"성장 퍼센티지": "+{:.2f}%"}
)
st.dataframe(styled_all_pred, use_container_width=True, hide_index=True)
st.caption("💡 예측 방식: 1·2·3회차의 평균 증가량으로 4회차를 외삽한 참고값입니다.")


# ──────────────────────────────────────────────────────────────
# ⑥ 학생 개인 QR 코드 & 전체 QR PDF 출력
# ──────────────────────────────────────────────────────────────
st.subheader("⑥ 📱 학생별 QR 코드 & 전체 출력")
st.markdown(
    "학생이 본인 QR을 스캔하면 ⑤번의 예상 성장 곡선과 격려 메시지를 본인 화면에서 볼 수 있습니다."
)

records = [
    {"n": r["이름"], "t": r["종류"], "s": [int(r["1회차"]), int(r["2회차"]), int(r["3회차"])]}
    for _, r in df.iterrows()
]

if not base_url.strip():
    st.warning(
        "왼쪽 사이드바의 'QR 설정'에 앱 배포 URL을 입력하면 QR과 PDF가 생성됩니다. "
        "URL이 없으면 학생이 QR을 스캔해도 리포트가 열리지 않습니다."
    )
else:
    base_clean = base_url.strip().rstrip("?&")
    if not base_clean.endswith("/"):
        base_clean += "/"

    layout = st.radio(
        "PDF 배치 (한 페이지당 학생 수)",
        ["3열 × 4행 (12명/쪽)", "2열 × 4행 (8명/쪽)", "4열 × 5행 (20명/쪽)"],
        horizontal=True,
    )
    layout_map = {
        "3열 × 4행 (12명/쪽)": (3, 4),
        "2열 × 4행 (8명/쪽)": (2, 4),
        "4열 × 5행 (20명/쪽)": (4, 5),
    }
    cols_n, rows_n = layout_map[layout]

    font_loader, font_label, korean_ok = get_font_loader(uploaded_font)
    if korean_ok:
        st.caption(f"PDF 한글 폰트: {font_label}")
    else:
        st.error(
            "한글 폰트를 찾지 못했습니다. PDF의 학생 이름이 깨질 수 있습니다. "
            "사이드바에서 한글 폰트(.ttf)를 업로드하거나, Streamlit Cloud는 packages.txt에 "
            "fonts-nanum 을 추가하세요."
        )

    if st.button("🖨️ 전체 QR 코드 PDF 만들기", type="primary"):
        with st.spinner("QR 코드를 생성하고 PDF로 정리하는 중..."):
            pdf_bytes, npages = build_qr_pdf(
                records, base_clean, font_loader, cols=cols_n, rows=rows_n
            )
        st.success(f"학생 {len(records)}명 · {npages}쪽 PDF가 준비되었습니다.")
        st.download_button(
            label="📥 QR 코드 PDF 다운로드",
            data=pdf_bytes,
            file_name="typing_growth_qr.pdf",
            mime="application/pdf",
        )

    with st.expander("🔍 학생별 QR 코드 / 링크 미리보기"):
        link_rows = []
        for s in records:
            token = encode_student(s["n"], s["t"], s["s"])
            link_rows.append({"이름": s["n"], "종류": s["t"], "QR 링크": f"{base_clean}?student={token}"})
        st.dataframe(
            pd.DataFrame(link_rows), use_container_width=True, hide_index=True
        )

        st.markdown("**개별 QR 이미지**")
        preview_cols = st.columns(4)
        for idx, s in enumerate(records):
            token = encode_student(s["n"], s["t"], s["s"])
            url = f"{base_clean}?student={token}"
            img = make_qr_img(url, 240)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            with preview_cols[idx % 4]:
                st.image(buf.getvalue(), caption=f"{s['n']} ({s['t']})", use_container_width=True)
