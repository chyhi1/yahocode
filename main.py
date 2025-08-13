import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from io import StringIO
from pathlib import Path

st.set_page_config(page_title="MBTI Top10 by Country", page_icon="🧭", layout="centered")
st.title("국가 선택 → MBTI 순위 Top10")
st.caption("CSV: countriesMBTI_16types.csv · 값이 0~1 비율이든 0~100 퍼센트든 자동 인식")

KNOWN_TYPES = [
    "INTJ","INTP","ENTJ","ENTP","INFJ","INFP","ENFJ","ENFP",
    "ISTJ","ISFJ","ESTJ","ESFJ","ISTP","ISFP","ESTP","ESFP"
]

@st.cache_data(show_spinner=False)
def load_df(uploaded_bytes: bytes | None) -> pd.DataFrame:
    # 1) 파일 업로드를 우선 사용
    if uploaded_bytes is not None:
        return pd.read_csv(StringIO(uploaded_bytes.decode("utf-8")))
    # 2) 동일 폴더에 있는 기본 파일 시도
    default_path = Path("countriesMBTI_16types.csv")
    if default_path.exists():
        return pd.read_csv(default_path)
    # 3) 예외 처리
    raise FileNotFoundError("CSV를 업로드하거나 리포지토리에 countriesMBTI_16types.csv를 넣어주세요.")


def detect_columns(df: pd.DataFrame) -> tuple[str, list[str]]:
    # 국가열 후보
    lower_cols = {c: c.lower().strip() for c in df.columns}
    country_candidates = [
        c for c, lc in lower_cols.items()
        if lc in {"country","nation","location","지역","국가"}
    ]
    country_col = country_candidates[0] if country_candidates else df.columns[0]

    # MBTI 열 탐지 (정확 매칭 → 부분 포함 순)
    up_cols = {c: c.upper().strip() for c in df.columns}
    mbti_cols = [c for c in df.columns if up_cols[c] in KNOWN_TYPES]
    if not mbti_cols:
        for c in df.columns:
            cu = up_cols[c]
            if any(t in cu for t in KNOWN_TYPES):
                mbti_cols.append(c)
    # 순서 및 중복 제거
    seen = set(); ordered = []
    for c in mbti_cols:
        if c not in seen:
            seen.add(c); ordered.append(c)
    return country_col, ordered


def coerce_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out


def to_percent(series: pd.Series) -> pd.Series:
    """0~1 또는 0~100 스케일 자동 처리 → % 스케일로 반환."""
    s = series.astype(float)
    s_clean = s.dropna()
    if s_clean.empty:
        return s
    ssum = float(s_clean.sum())
    # 합계가 0.95~1.05 사이라면 비율(0~1)로 간주 → 100배
    if 0.95 <= ssum <= 1.05:
        return s * 100.0
    # 합계가 95~105 사이라면 이미 %로 간주
    return s


# ===== UI =====
left, right = st.columns([1,1])
with left:
    uploaded = st.file_uploader("CSV 업로드 (선택)", type=["csv"], accept_multiple_files=False)
with right:
    st.markdown("""
    **파일 규격**  
    - 국가열: `Country` (또는 유사명 자동 인식)  
    - MBTI 열: INTJ…ESFP 16종 (대소문자 무관)  
    """)

# Load
try:
    df = load_df(uploaded.read() if uploaded is not None else None)
except Exception as e:
    st.error(str(e))
    st.stop()

country_col, mbti_cols = detect_columns(df)
if not mbti_cols:
    st.error("MBTI 유형 열을 찾지 못했습니다. 컬럼명을 확인해주세요.")
    st.stop()

# 숫자 변환
_df = coerce_numeric(df, mbti_cols)

# 국가 선택
countries = _df[country_col].astype(str).fillna("(Unknown)").tolist()
country = st.selectbox("국가 선택", sorted(countries))

# 선택한 국가의 MBTI 시리즈 구성 → Top10
row = _df[_df[country_col].astype(str) == country]
if row.empty:
    st.warning("해당 국가 행을 찾지 못했습니다.")
    st.stop()

series = row[mbti_cols].iloc[0]
series_percent = to_percent(series)

# Top10 계산
s_sorted = series_percent.sort_values(ascending=False).head(10)
rank_df = (
    s_sorted.reset_index().rename(columns={"index":"MBTI","0": "Percent", s_sorted.name if s_sorted.name is not None else 0: "Percent"})
)
rank_df["Rank"] = np.arange(1, len(rank_df)+1)
rank_df = rank_df[["Rank","MBTI","Percent"]]

# 테이블 표시
st.subheader(f"{country} · MBTI Top10")
st.dataframe(rank_df, use_container_width=True)

# Altair Bar Chart
chart_df = rank_df.copy()
chart = (
    alt.Chart(chart_df)
    .mark_bar()
    .encode(
        x=alt.X("Percent:Q", title="비중(%)"),
        y=alt.Y("MBTI:N", sort='-x', title="MBTI 유형"),
        tooltip=["Rank:N","MBTI:N", alt.Tooltip("Percent:Q", format=".2f")]
    )
)
text = (
    alt.Chart(chart_df)
    .mark_text(align='left', baseline='middle', dx=3)
    .encode(y=alt.Y("MBTI:N", sort='-x'), x="Percent:Q", text=alt.Text("Percent:Q", format=".2f"))
)

st.altair_chart(chart + text, use_container_width=True)

# 추가 진단(선택)
with st.expander("데이터 진단 보기"):
    sums = _df[mbti_cols].sum(axis=1)
    st.write("국가별 16유형 합계 통계(원본 스케일):", sums.describe())
    st.write("감지된 국가열:", country_col)
    st.write("감지된 MBTI 열(개수={}):".format(len(mbti_cols)), mbti_cols)

st.caption("© Streamlit + Altair · 파일이 0~1 비율일 경우 자동으로 100% 변환하여 출력합니다.")

