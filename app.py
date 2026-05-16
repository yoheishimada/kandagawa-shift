"""
神田川ベーカリー 製造数予測アプリ
"""
import os, pickle, json, urllib.request
from datetime import date, timedelta
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import jpholiday as _jpholiday

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

st.set_page_config(
    page_title="神田川ベーカリー 製造数予測",
    page_icon="🍞",
    layout="wide",
    initial_sidebar_state="expanded",
)

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.markdown("""
        <div style='padding: 2.5rem 0 1.5rem 0; border-bottom: 1px solid #e8e4de; margin-bottom: 1.8rem;'>
          <div style='font-size:0.62rem;letter-spacing:0.28em;color:#bbb;text-transform:uppercase;margin-bottom:0.5rem;'>Kandagawa Bakery</div>
          <div style='font-size:1.7rem;font-weight:700;letter-spacing:-0.02em;color:#1a1a1a;line-height:1.1;'>売上予測 & 製造数プランナー</div>
        </div>
        """, unsafe_allow_html=True)
        password = st.text_input("パスワードを入力してください", type="password")
        if st.button("ログイン", use_container_width=True):
            if password in ("Kandagawa0222", "Fang_Admiration_2010"):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("パスワードが違います")
        st.stop()

check_password()

# ── カスタムCSS ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+JP:wght@300;400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans JP', sans-serif;
    font-size: 15px;
}

/* ── 背景 ── */
.stApp { background: #f5f5f3; color: #1a1a1a; }

/* ── サイドバー ── */
[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e8e4de !important;
}
[data-testid="stSidebar"] * { color: #1a1a1a !important; }
[data-testid="stSidebarNav"] { display: none !important; }

/* ── タイトル ── */
.main-title {
    font-size: 1.9rem; font-weight: 700; letter-spacing: -0.02em;
    color: #1a1a1a; margin-bottom: 0.1rem;
}
.main-subtitle {
    font-size: 0.63rem; font-weight: 600; letter-spacing: 0.22em;
    text-transform: uppercase; color: #bbb; margin-bottom: 2rem;
}

/* ── 日付カード ── */
.day-card {
    background: #ffffff; border: 1px solid #e8e4de; border-radius: 12px;
    padding: 1.1rem 0.7rem; text-align: center; transition: all 0.18s;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
.day-card:hover { border-color: #1a1a1a; box-shadow: 0 4px 16px rgba(0,0,0,0.09); transform: translateY(-2px); }
.day-card .date-label { font-size: 0.68rem; color: #bbb; letter-spacing: 0.08em; margin-bottom: 0.2rem; }
.day-card .weekday { font-size: 1.1rem; font-weight: 700; margin-bottom: 0.35rem; color: #1a1a1a; }
.day-card .sales-amount { font-size: 1.35rem; font-weight: 700; color: #1a1a1a; letter-spacing: -0.02em; }
.day-card .weather-info { font-size: 0.7rem; color: #ccc; margin-top: 0.35rem; }

/* バッジ（日付カード） */
.day-card .badge {
    display: inline-block; font-size: 0.6rem; padding: 0.1rem 0.35rem;
    border-radius: 4px; margin: 0.12rem 0.04rem; font-weight: 600; letter-spacing: 0.02em;
}
.badge-holiday { background: #fff3e0; color: #c86000; border: 1px solid #ffd08a; }
.badge-school  { background: #e8f0fe; color: #1a56db; border: 1px solid #b3c9fa; }
.badge-waseda  { background: #f0e8fe; color: #6c27c5; border: 1px solid #cdb3fa; }
.badge-rain    { background: #e8f4fd; color: #1565c0; border: 1px solid #90caf9; }

/* レンジバー */
.range-row { display: flex; align-items: center; gap: 0.35rem; font-size: 0.66rem; color: #ccc; margin-top: 0.5rem; }
.range-track { flex: 1; height: 3px; background: #ebebeb; border-radius: 99px; position: relative; }
.range-fill  { position: absolute; top: 0; height: 3px; border-radius: 99px; background: #1a1a1a; }

/* ── テーブル ── */
.styled-table { width: 100%; border-collapse: collapse; }
.styled-table th {
    background: #fafaf8; color: #aaa; font-size: 0.7rem; font-weight: 600;
    padding: 0.65rem 1rem; text-align: right;
    border-bottom: 1px solid #e8e4de; letter-spacing: 0.08em; text-transform: uppercase;
}
.styled-table th:first-child { text-align: left; }
.styled-table td {
    padding: 0.6rem 1rem; font-size: 0.87rem; border-bottom: 1px solid #f2ede8;
    text-align: right; color: #444;
}
.styled-table td:first-child { text-align: left; color: #1a1a1a; font-weight: 500; }
.styled-table tr:hover td { background: #fafaf8; }
.styled-table tr.cat-header td {
    background: #f5f5f3; color: #aaa; font-size: 0.66rem; font-weight: 700;
    letter-spacing: 0.14em; padding: 0.38rem 1rem; text-transform: uppercase;
    border-top: 1px solid #e8e4de; border-bottom: 1px solid #e8e4de; text-align: left;
}

/* テーブル内バッジ */
.tbl-badge {
    display: inline-block; font-size: 0.57rem; font-weight: 700;
    padding: 0.04rem 0.25rem; border-radius: 3px; margin-left: 0.28rem;
    vertical-align: middle; letter-spacing: 0.02em; line-height: 1.4;
}
.tbl-sellout   { background: #fde8e8; color: #c0392b; border: 1px solid #e57373; }
.tbl-loss      { background: #fff8e1; color: #966000; border: 1px solid #f0c040; }
.tbl-secondary { background: #f0f0f0; color: #888; border: 1px solid #ddd; }

/* ── セクションヘッダー ── */
.section-header {
    font-size: 0.66rem; font-weight: 700; letter-spacing: 0.2em;
    text-transform: uppercase; color: #aaa; margin: 2.2rem 0 1rem;
    display: flex; align-items: center; gap: 0.8rem;
}
.section-header::after { content: ''; flex: 1; height: 1px; background: #e8e4de; }

/* ── 入力フィールド ── */
.stTextInput input, .stDateInput input {
    background: #ffffff !important; border: 1px solid #e8e4de !important;
    color: #1a1a1a !important; border-radius: 0px !important; font-size: 0.9rem !important;
}

/* ── メトリクスカード ── */
.metric-chip {
    background: #ffffff; border: 1px solid #e8e4de; border-radius: 10px;
    padding: 1rem 1.2rem; margin-bottom: 0.8rem;
}
.metric-chip .label { font-size: 0.66rem; color: #aaa; letter-spacing: 0.1em; text-transform: uppercase; }
.metric-chip .value { font-size: 1.5rem; font-weight: 700; color: #1a1a1a; letter-spacing: -0.02em; }

/* ── ボタン ── */
.stButton button, .stDownloadButton button {
    background: #1a1a1a !important; border: none !important;
    color: #ffffff !important; border-radius: 6px !important;
    font-size: 0.82rem !important; font-weight: 500 !important;
    letter-spacing: 0.04em !important; transition: opacity 0.2s !important;
}
.stButton button:hover, .stDownloadButton button:hover {
    opacity: 0.72 !important; background: #1a1a1a !important;
}

/* ── その他 ── */
hr { border-color: #e8e4de !important; }
.stCaption p { color: #bbb !important; font-size: 0.7rem !important; letter-spacing: 0.04em; }
</style>
""", unsafe_allow_html=True)

# ── 定数 ────────────────────────────────────────────────────
SCHOOL_HOLIDAYS = [
    ("2022-07-21","2022-08-31"),("2022-12-26","2023-01-09"),("2023-03-25","2023-04-06"),
    ("2023-07-21","2023-08-31"),("2023-12-26","2024-01-08"),("2024-03-26","2024-04-07"),
    ("2024-07-22","2024-08-31"),("2024-12-26","2025-01-07"),("2025-03-25","2025-04-06"),
    ("2025-07-21","2025-08-31"),("2025-12-26","2026-01-07"),("2026-03-26","2026-04-05"),
]
WASEDA_HOLIDAYS = [
    ("2022-07-25","2022-09-21"),("2023-02-04","2023-03-31"),
    ("2023-07-25","2023-09-20"),("2024-02-04","2024-03-31"),
    ("2024-07-29","2024-09-20"),("2025-02-04","2025-03-31"),
    ("2025-07-30","2025-09-20"),("2026-02-04","2026-03-31"),
]
WEEKDAY_JP = ["月", "火", "水", "木", "金", "土", "日"]
MODE_LABELS = {"bear": "弱気", "normal": "普通", "bull": "強気"}
MODE_COLORS = {"bear": "#4a90d9", "normal": "#50c878", "bull": "#e8603d"}

# 東京（新宿区・豊島区）桜開花・満開日
SAKURA_DATES = {
    2022: {"kaika": date(2022, 3, 20), "mankai": date(2022, 3, 27)},
    2023: {"kaika": date(2023, 3, 14), "mankai": date(2023, 3, 22)},
    2024: {"kaika": date(2024, 3, 29), "mankai": date(2024, 4,  5)},
    2025: {"kaika": date(2025, 3, 25), "mankai": date(2025, 4,  2)},
    2026: {"kaika": date(2026, 3, 26), "mankai": date(2026, 4,  3)},
}

def sakura_features(dt: date) -> dict:
    year = dt.year
    if year not in SAKURA_DATES:
        year = max(k for k in SAKURA_DATES if k <= year) if any(k <= year for k in SAKURA_DATES) else min(SAKURA_DATES)
    mankai = SAKURA_DATES[year]["mankai"]
    kaika  = SAKURA_DATES[year]["kaika"]
    days_from_mankai = (dt - mankai).days
    kaika_to_mankai  = max((mankai - kaika).days, 1)
    days_from_kaika  = (dt - kaika).days
    if days_from_kaika < 0:
        score = 0.0
    elif days_from_kaika <= kaika_to_mankai:
        score = days_from_kaika / kaika_to_mankai
    elif days_from_mankai <= 7:
        score = 1.0
    elif days_from_mankai <= 21:
        score = 1.0 - (days_from_mankai - 7) / 14
    else:
        score = 0.0
    return {
        "sakura_score":     round(max(0.0, score), 4),
        "days_from_mankai": max(-30, min(30, days_from_mankai)),
        "is_sakura_peak":   int(-7 <= days_from_mankai <= 7),
    }


TSUYU_DATES = {
    2022: {"iri": date(2022, 6,  6), "ake": date(2022, 7, 23)},
    2023: {"iri": date(2023, 6,  8), "ake": date(2023, 7, 22)},
    2024: {"iri": date(2024, 6, 21), "ake": date(2024, 7, 18)},
    2025: {"iri": date(2025, 6, 10), "ake": date(2025, 7, 20)},
    2026: {"iri": date(2026, 6, 10), "ake": date(2026, 7, 20)},
}

def tsuyu_features(dt: date) -> dict:
    year = dt.year
    if year not in TSUYU_DATES:
        year = max(k for k in TSUYU_DATES if k <= year) if any(k <= year for k in TSUYU_DATES) else min(TSUYU_DATES)
    iri = TSUYU_DATES[year]["iri"]
    ake = TSUYU_DATES[year]["ake"]
    is_tsuyu = int(iri <= dt <= ake)
    days_from_iri = (dt - iri).days
    return {
        "is_tsuyu":        is_tsuyu,
        "days_into_tsuyu": max(0, min(days_from_iri, 45)) if is_tsuyu else 0,
    }

def heat_features(temp_max: float) -> dict:
    return {
        "heat_excess":  round(max(0.0, temp_max - 30.0), 1),
        "is_hot_day":   int(temp_max >= 30),
        "is_very_hot":  int(temp_max >= 35),
    }

# スプレッドシート構成に合わせたカテゴリグループ（EXCEL_PRODUCT_ORDERの並び順に対応）
CATEGORY_GROUPS = [
    ("山食生地", [
        "山食", "プチ", "塩ぱん", "塩パン",
        "あんことクリームチーズ", "クリームパン", "クリームぱん",
        "カルダモンロール", "明太ハムロール", "カリカリソーセージカリー",
        "お豆のふんわり蒸しパン",
        "ミルクチョコと伊予柑のぱん", "ミルクチョコと伊予柑のパン", "ミルクチョコと伊予柑",
        "お芋のぱん", "お芋のパン", "お芋の塩ぱん",
        "キャラメルアップル", "紅玉",
        "焙煎大麦のくるみぱん", "焙煎大麦黒豆ぱん",
        "うぐいす豆", "抹茶うぐいすロール",
    ]),
    ("レーズン山食生地", [
        "レーズン食パン", "レーズンプチ", "シナモンロール", "レーズンかぼちゃあんぱん",
    ]),
    ("クランベリースティック生地", [
        "クランベリーのスティック", "クランベリースティック",
    ]),
    ("チョコ生地", [
        "チョコチッププチ",
    ]),
    ("ごま食生地", [
        "ハムロール", "ベーコンロール", "あんぱん",
        "黒豆ぱん", "黒豆パン", "ごまぱん", "ごま食パン",
    ]),
    ("カンパーニュ生地", [
        "カンパーニュ", "小さなカンパーニュ",
        "ハニークリームチーズ", "ショコラカンパーニュ", "柑橘ピール",
        "あめ色玉ねぎとゴーダチーズ", "3種ナッツとホワイトチョコ",
    ]),
    ("レーズン＆くるみ生地", [
        "レーズンとくるみのカンパーニュ", "小さなレーズンとくるみのカンパーニュ",
    ]),
    ("フォカッチャ生地", [
        "プレーンフォカッチャ", "フォカッチャ プレーン",
        "アンチョビオリーブ", "ソーセージエピ",
        "カレーパン", "カレーぱん",
        "スパイシーボロネーゼドッグ",
        "ソーセージとポテトのジェノベーゼフォカッチャ",
        "3種のチーズぱん", "3種のチーズパン",
        "セミドライトマトとチーズのフォカッチャ",
        "そら豆とゴーダチーズのフォカッチャ",
        "よもぎとクリームチーズ",
        "チョリソーミイラ", "厚切りフォカッチャ",
        "フォカッチャ", "ソイフォカッチャ", "ソイフーガス",
    ]),
    ("バゲット生地", [
        "バゲット", "バタール",
        "ジャーマンポテト", "バターソテーオニオン",
    ]),
    ("チーズブール生地", ["チーズブール"]),
    ("豆乳フランス生地", ["豆乳フランス", "あおさの豆乳フランス"]),
    ("ブリオッシュ生地", [
        "ブリオッシュ", "メロンパン", "シュクレ", "きのこのクリームブリオッシュ",
    ]),
    ("サンドイッチ・パニーノ", [
        "バゲットサンド", "バケットサンド", "パニーノ",
        "照り焼きチキンサンド", "照り焼きチキンのサンドイッチ",
        "スモークチキンとたまご", "プチサンドセット",
    ]),
    ("リベイク二次製品", [
        "クロックムッシュ", "タルティーヌ", "フレンチトースト",
        "ニース風ホット", "カリカリハニー", "明太フランス",
        "ピザトースト", "本日のトースト", "本日のフレンチトースト",
        "ナンテールのトースト", "ナンテールトースト",
        "バゲットのフレンチトースト", "きのこクリームのバゲットトースト",
        "カリカリハニーバタートースト",
    ]),
    ("フィリング二次製品", [
        "あんこ塩ぱん", "あんこ塩パン",
        "ミルククリーム", "マロンクリーム",
        "いちご練乳スティック",
        "プレーンプチ（クリーム", "チョコチッププチ（クリーム", "レーズンプチ（クリーム",
    ]),
]


SECONDARY_CATEGORIES = {"リベイク二次製品", "フィリング二次製品"}
REBAKE_CATEGORIES    = {"リベイク二次製品"}
FILLING_CATEGORIES   = {"フィリング二次製品"}
SANDWICH_CATEGORIES  = {"サンドイッチ・パニーノ"}

# フィリング二次製品：当日焼いたパンにあんこ・クリーム等を詰める商品
# 生産数はベースパン（塩パン・プチ等）に含まれる
FILLING_PRODUCTS = {
    "あんこ塩ぱん",
    "あんこ塩パン",
    "いちご練乳スティック",
    # プチ系クリーム入り（プレーンプチ・チョコプチ・レーズンプチをベースに使用）
    "プレーンプチ（クリーム入り）",
    "プレーンプチ（マロンミルククリーム入り）",
    "プレーンプチ（レモンクリーム入り）",
    "チョコチッププチ（クリーム入）",
    "レーズンプチ（クリーム入り）",
}

# リベイク二次製品・フィリング二次製品の統合セット（学習除外用）
SECONDARY_PRODUCTS = FILLING_PRODUCTS | {
    # リベイク系（前日ロスから製造するため個別予測不要）
    "クロックムッシュ", "タルティーヌ", "フレンチトースト",
    "ニース風ホット", "カリカリハニー", "明太フランス",
    "ピザトースト", "本日のトースト", "本日のフレンチトースト",
    "ナンテールトースト", "バゲットのフレンチトースト",
    "きのこクリームのバゲットトースト",
}

# 食パン1斤→2斤 統合マッピング
# 1斤は2斤を半分に切ったもの。製造は2斤単位で行うため、1斤の需要を2斤換算で加算する
# キー: 1斤商品名（の部分文字列）, 値: 対応する2斤商品名（の部分文字列）
SHOKUPAN_PAIRS = [
    ("山食　プレーン1斤",  "山食　プレーン2斤"),
    ("山食プレーン1斤",   "山食プレーン2斤"),   # 旧表記
    ("山食　レーズン1斤", "山食　レーズン2斤"),
    ("山食レーズン1斤",   "山食レーズン2斤"),   # 旧表記
]
# 1斤商品（表示上は「2斤に統合」バッジを付ける）
SHOKUPAN_1KIN = {pair[0] for pair in SHOKUPAN_PAIRS}

# 二次加工品のためにベースパンへ追加する数量（曜日別平均、4年間の実績から算出）
# キー: ベースパン名, 値: {weekday(0=月〜6=日): 追加個数}
SECONDARY_UPLIFT = {
    "塩ぱん":               {0: 10.3, 1:  9.0, 2: 12.1, 3: 11.7, 4: 11.4, 5: 18.3, 6: 18.0},
    "クランベリーのスティックぱん": {0:  3.9, 1:  3.3, 2:  3.0, 3:  3.5, 4:  3.8, 5:  5.4, 6:  6.5},
    "プレーンプチ":          {0:  3.7, 1:  3.5, 2:  3.5, 3:  3.6, 4:  3.6, 5:  4.9, 6:  4.6},
    "チョコチッププチ":       {0:  1.8, 1:  1.6, 2:  1.5, 3:  1.8, 4:  1.4, 5:  2.0, 6:  2.4},
    "レーズンプチ":          {0:  1.4, 1:  1.6, 2:  1.5, 3:  1.5, 4:  1.6, 5:  1.8, 6:  1.8},
}


def categorize_product(name):
    for category, keywords in CATEGORY_GROUPS:
        for kw in keywords:
            if kw in name:
                return category
    return "その他"


def is_filling(name):
    """フィリング二次製品（ベースパンに含む）"""
    return name in FILLING_PRODUCTS or categorize_product(name) in FILLING_CATEGORIES

def is_rebake(name):
    """リベイク二次製品（前日ロスから製造・AI予測表示）"""
    return categorize_product(name) in REBAKE_CATEGORIES

def is_secondary(name):
    return is_filling(name) or is_rebake(name)

def is_sandwich(name):
    return categorize_product(name) in SANDWICH_CATEGORIES


def in_period(dt_str, periods):
    return any(s <= dt_str <= e for s, e in periods)


@st.cache_resource
def load_models():
    import gzip
    gz_path = os.path.join(DATA_DIR, "models.pkl.gz")
    pkl_path = os.path.join(DATA_DIR, "models.pkl")
    try:
        if os.path.exists(gz_path):
            with gzip.open(gz_path, "rb") as f:
                return pickle.load(f)
        with open(pkl_path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        st.error(f"models.pkl の読み込みに失敗しました: {e}")
        st.stop()


@st.cache_resource
def load_dataset():
    path = os.path.join(DATA_DIR, "dataset.pkl")
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        st.error(f"dataset.pkl の読み込みに失敗しました: {e}")
        st.stop()


@st.cache_resource
def load_calibration():
    path = os.path.join(DATA_DIR, "calibration.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return {}


@st.cache_data(ttl=3600)
def fetch_spreadsheet_data():
    """スプレッドシートから製造数・売切・ロス実績を取得"""
    import csv, io
    SHEET_URL = (
        "https://docs.google.com/spreadsheets/d/"
        "1hLmRFfAm_kfjr_hk-G4GhGBwvJ5g_sNU/export?format=csv&gid=753872113"
    )
    SECTION_TYPES = {"定番", "季節", "サンド", "二次"}
    today = date.today()

    try:
        req = urllib.request.Request(SHEET_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            content = res.read().decode("utf-8")
    except Exception:
        return {}

    rows = list(csv.reader(io.StringIO(content)))
    if len(rows) < 8:
        return {}

    row0 = rows[0]

    # 日付列を探して年を付与
    date_cols = []
    for i, v in enumerate(row0):
        v = v.strip()
        if v and "/" in v and len(v) <= 5 and v.count("/") == 1:
            try:
                m, d_num = map(int, v.split("/"))
                # 年判定：現在の月±6ヶ月以内で最も近い年を使用
                for yr in [today.year, today.year - 1, today.year + 1]:
                    try:
                        candidate = date(yr, m, d_num)
                        if abs((candidate - today).days) < 400:
                            date_cols.append((i, candidate.isoformat()))
                            break
                    except ValueError:
                        continue
            except ValueError:
                continue

    # 各商品行を解析
    result = {}
    for row in rows[7:]:
        type_col = row[0].strip() if row else ""
        prod_name = row[1].strip() if len(row) > 1 else ""
        if type_col not in SECTION_TYPES or not prod_name:
            continue

        prod_data = {}
        for col, dt in date_cols:
            if col + 5 >= len(row):
                continue
            try:
                seizo    = float(row[col].strip())   if row[col].strip()   else 0
                unit     = row[col+1].strip()
                uriage   = int(float(row[col+2].strip())) if row[col+2].strip() else 0
                saikiri  = row[col+3].strip()
                loss_qty = float(row[col+4].strip()) if row[col+4].strip() else 0
                loss_yen = int(float(row[col+5].strip())) if row[col+5].strip() else 0
            except (ValueError, IndexError):
                continue
            if seizo > 0:
                prod_data[dt] = {
                    "製造数": seizo, "単位": unit, "計画売上": uriage,
                    "売切時間": saikiri, "ロス数量": loss_qty, "ロス金額": loss_yen,
                }
        if prod_data:
            result[prod_name] = prod_data

    return result


def compute_sheet_stats(sheet_data):
    """商品別の売切率・ロス率・推奨バッファーを計算（過去データのみ）"""
    today_str = date.today().isoformat()
    stats = {}
    for prod, daily in sheet_data.items():
        past = {dt: v for dt, v in daily.items() if dt < today_str}
        if not past:
            continue
        n = len(past)
        n_so = sum(1 for v in past.values() if v["売切時間"])
        n_loss = sum(1 for v in past.values() if v["ロス数量"] > 0)
        total_seizo   = sum(v["製造数"]   for v in past.values())
        total_loss_qty = sum(v["ロス数量"] for v in past.values())
        total_loss_yen = sum(v["ロス金額"] for v in past.values())
        avg_loss_pct = (total_loss_qty / total_seizo * 100) if total_seizo > 0 else 0
        so_rate   = n_so   / n if n > 0 else 0
        loss_rate = n_loss / n if n > 0 else 0
        stats[prod] = {
            "n_days": n, "n_sellout": n_so, "n_loss": n_loss,
            "total_seizo": total_seizo, "total_loss_qty": total_loss_qty,
            "total_loss_yen": total_loss_yen,
            "avg_loss_pct": avg_loss_pct,
            "sellout_rate": so_rate, "loss_rate": loss_rate,
        }
    return stats


# ── Excelの生産表に基づく商品並び順（コピペ用） ──────────────────────
EXCEL_PRODUCT_ORDER = [
    "山食", "プチ", "塩ぱん", "あんこクリームチーズ", "クリームパン",
    "カルダモンロール", "明太ハムロール（大葉入）", "カリカリソーセージカリー", "お豆のふんわり蒸しパン",
    "レーズン食パン", "レーズンプチ", "シナモンロール", "クランベリースティック", "チョコチッププチ",
    "ハム  or  ベーコンロール", "あんぱん", "黒豆ぱん",
    "カンパーニュ（小)", "ハニークリームチーズ", "ショコラカンパーニュ", "柑橘ピール",
    "あめ色玉ねぎとゴーダチーズ", "3種ナッツとホワイトチョコ",
    "レーズン&くるみ（小）", "プレーンフォカッチャ", "アンチョビオリーブ", "ソーセージエピ",
    "カレーパン", "スパイシーボロネーゼドッグ", "ソーセージとポテトのジェノベーゼフォカッチャ",
    "3種のチーズぱん", "セミドライトマトとチーズのフォカッチャ",
    "そら（枝）豆とゴーダチーズのフォカッチャ", "よもぎとクリームチーズ",
    "バゲット", "大葉とベーコンのバゲット", "マカダミアナッツと黒胡椒のバゲット",
    "チーズブール", "豆乳フランス", "あおさの豆乳フランス",
    "きのこのクリームブリオッシュ", "メロンパン", "ブリオッシュシュクレ", "ブリオッシュナンテール",
]
EXCEL_ORDER = {name: idx for idx, name in enumerate(EXCEL_PRODUCT_ORDER)}


def sheet_order_key(pos_name, sheet_order):
    """スプレッドシートの行順インデックスを返す（マッチしない場合は末尾）"""
    # 優先1: 完全一致
    if pos_name in sheet_order:
        return sheet_order[pos_name]
    # 優先2: sheet_name が pos_name の部分文字列
    primary = [sn for sn in sheet_order if sn in pos_name and sn != pos_name]
    if primary:
        best = max(primary, key=len)
        return sheet_order[best]
    # 優先3: pos_name が sheet_name の部分文字列（最短）
    secondary = [sn for sn in sheet_order if pos_name in sn]
    if secondary:
        best = min(secondary, key=len)
        return sheet_order[best]
    return 9999  # スプレッドシートにない商品は末尾


def match_pos_to_sheet(pos_name, sheet_stats):
    """Square商品名をスプレッドシート商品名にマッチ（優先度付き最長一致）
    優先1: 完全一致
    優先2: スプレッドシート名がPOS名の部分文字列（山食→山食1斤）
    優先3: POS名がスプレッドシート名の部分文字列（フォールバック）
    """
    # 優先1: 完全一致
    if pos_name in sheet_stats:
        return sheet_stats[pos_name]
    # 優先2: sheet_name が pos_name の部分文字列
    primary = [sn for sn in sheet_stats if sn in pos_name and sn != pos_name]
    if primary:
        best = max(primary, key=len)
        return sheet_stats[best]
    # 優先3: pos_name が sheet_name の部分文字列（フォールバック）
    secondary = [sn for sn in sheet_stats if pos_name in sn]
    if secondary:
        best = min(secondary, key=len)  # 最短（最も近い）を選ぶ
        return sheet_stats[best]
    return None


@st.cache_data(ttl=3600)
def fetch_forecast(start: str, end: str):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude=35.715&longitude=139.717"
        f"&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
        f"precipitation_sum,sunshine_duration,windspeed_10m_max,weathercode"
        f"&hourly=precipitation"
        f"&timezone=Asia%2FTokyo&start_date={start}&end_date={end}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read())

        # 時間別降水量を営業時間帯に集計
        htimes = data["hourly"]["time"]
        hprecip = data["hourly"]["precipitation"]
        hourly_by_date = {}
        for t, p in zip(htimes, hprecip):
            ds, hs = t[:10], int(t[11:13])
            p = p or 0.0
            if ds not in hourly_by_date:
                hourly_by_date[ds] = {"lunch": [], "evening": [], "morning": []}
            if hs == 10:
                hourly_by_date[ds]["morning"].append(p)
            elif 11 <= hs <= 14:
                hourly_by_date[ds]["lunch"].append(p)
            elif 16 <= hs <= 18:
                hourly_by_date[ds]["evening"].append(p)

        daily = data["daily"]
        result = {}
        for i, dt in enumerate(daily["time"]):
            h = hourly_by_date.get(dt, {"lunch": [], "evening": [], "morning": []})
            lunch = h["lunch"]
            eve = h["evening"]
            morn = h["morning"]
            result[dt] = {
                "temp_max":   daily["temperature_2m_max"][i],
                "temp_min":   daily["temperature_2m_min"][i],
                "temp_mean":  daily["temperature_2m_mean"][i],
                "sunshine_sec": daily["sunshine_duration"][i] or 0,
                "wind_max":   daily["windspeed_10m_max"][i],
                "weather_code": daily["weathercode"][i],
                "rain_lunch_total":   sum(lunch),
                "rain_lunch_max":     max(lunch) if lunch else 0,
                "rain_lunch_heavy":   sum(1 for x in lunch if x >= 2),
                "rain_evening_total": sum(eve),
                "rain_evening_max":   max(eve) if eve else 0,
                "rain_evening_heavy": sum(1 for x in eve if x >= 2),
                "rain_morning":       sum(morn),
                "is_rainy_lunch":     int(sum(lunch) > 1),
                "is_rainy_evening":   int(sum(eve) > 1),
            }
        return result
    except Exception:
        return None  # 呼び出し元で判定


def get_lineup(models):
    """スプレッドシートの商品構成（EXCEL_PRODUCT_ORDER）をPOS商品名にマッピングして返す。
    廃番品の混入・新商品の漏れを防ぐため、スプレッドシートを唯一の正として固定する。"""
    model_products = list(models.get("product_models", {}).keys())
    lineup = []
    seen = set()

    for sheet_name in EXCEL_PRODUCT_ORDER:
        # 優先1: 完全一致
        if sheet_name in models.get("product_models", {}):
            if sheet_name not in seen:
                lineup.append(sheet_name)
                seen.add(sheet_name)
            continue
        # 優先2: sheet_name が pos_name の部分文字列（最短）
        matches = [p for p in model_products if sheet_name in p]
        if matches:
            best = min(matches, key=len)
            if best not in seen:
                lineup.append(best)
                seen.add(best)
            continue
        # 優先3: pos_name が sheet_name の部分文字列（最長）
        matches = [p for p in model_products if p in sheet_name]
        if matches:
            best = max(matches, key=len)
            if best not in seen:
                lineup.append(best)
                seen.add(best)

    return lineup


_LAG_BASELINE = 70000  # ラグ特徴量のデフォルト値（特徴量が取れない場合）
_LAG_DEFAULTS = {
    "sales_lag_7":   _LAG_BASELINE,
    "sales_lag_28":  _LAG_BASELINE,
    "sales_lag_365": _LAG_BASELINE,
    "sales_ma7":     _LAG_BASELINE,
    "sales_ma28":    _LAG_BASELINE,
    "yoy_ratio":     1.0,
    "momentum":      1.0,
}


def build_sales_map(records):
    """dataset["records"] から {日付文字列: 売上合計} の辞書を作成"""
    return {r["date"]: r["total_sales"] for r in records if "total_sales" in r}


def compute_lag_features(dt_str, sales_map):
    """予測対象日のラグ特徴量を過去実績から計算する。
    7/28日ラグは同曜日優先ルックアップ：データ境界外でも正しい曜日の値を取得。
    成長・衰退どちらのトレンドも yoy_ratio / momentum に自然に反映される。"""
    base_wd = date.fromisoformat(dt_str).weekday()

    def lookup_near(offset_days, window=3):
        target = date.fromisoformat(dt_str) - timedelta(days=offset_days)
        # 7/28日ラグは同曜日を最優先（異曜日の値はトレンドを歪める）
        if offset_days % 7 == 0:
            # ① ちょうど同曜日の日を最大6週遡る
            for extra_weeks in range(7):
                cand = (target - timedelta(weeks=extra_weeks))
                if cand.isoformat() in sales_map and cand.weekday() == base_wd:
                    return sales_map[cand.isoformat()]
        # ② 同曜日が見つからない場合はwindow日以内の近傍で妥協
        for delta in range(window + 1):
            for sign in [0, 1, -1]:
                cand = (target + timedelta(days=delta * sign)).isoformat()
                if cand in sales_map:
                    return sales_map[cand]
        return None

    def moving_avg(days):
        d0 = date.fromisoformat(dt_str)
        vals = [sales_map[d] for i in range(1, days + 1)
                if (d := (d0 - timedelta(days=i)).isoformat()) in sales_map]
        return sum(vals) / len(vals) if vals else None

    s7   = lookup_near(7)
    s28  = lookup_near(28)
    s365 = lookup_near(365)
    ma7  = moving_avg(7)
    ma28 = moving_avg(28)

    yoy = (ma28 / s365) if (s365 and s365 > 0 and ma28) else 1.0
    yoy = max(0.5, min(2.0, yoy))
    momentum = (ma7 / ma28) if (ma7 and ma28 and ma28 > 0) else 1.0
    momentum = max(0.5, min(2.0, momentum))

    return {
        "sales_lag_7":   s7   if s7   is not None else _LAG_BASELINE,
        "sales_lag_28":  s28  if s28  is not None else _LAG_BASELINE,
        "sales_lag_365": s365 if s365 is not None else _LAG_BASELINE,
        "sales_ma7":     ma7  if ma7  is not None else _LAG_BASELINE,
        "sales_ma28":    ma28 if ma28 is not None else _LAG_BASELINE,
        "yoy_ratio":     yoy,
        "momentum":      momentum,
    }


def make_features(dt_str, weather, prev_close_min=1020, lag_feats=None):
    d = date.fromisoformat(dt_str)
    w = weather.get(dt_str, {})
    m, wd = d.month, d.weekday()
    woy = d.isocalendar()[1]  # 年間何週目か（1〜52）
    sk = sakura_features(d)
    ts = tsuyu_features(d)
    ht = heat_features(w.get("temp_max", 20))
    lf = lag_feats if lag_feats is not None else _LAG_DEFAULTS
    return [
        d.year, m, d.day, wd, woy,
        int(wd >= 5), int(_jpholiday.is_holiday(d)),
        int(in_period(dt_str, SCHOOL_HOLIDAYS)),
        int(in_period(dt_str, WASEDA_HOLIDAYS)),
        w.get("temp_max", 18), w.get("temp_min", 10), w.get("temp_mean", 14),
        w.get("sunshine_sec", 30000), w.get("wind_max", 8), w.get("weather_code", 1),
        w.get("rain_lunch_total", 0), w.get("rain_lunch_max", 0), w.get("rain_lunch_heavy", 0),
        w.get("rain_evening_total", 0), w.get("rain_evening_max", 0), w.get("rain_evening_heavy", 0),
        w.get("rain_morning", 0), w.get("is_rainy_lunch", 0), w.get("is_rainy_evening", 0),
        sk["sakura_score"], sk["days_from_mankai"], sk["is_sakura_peak"],
        ts["is_tsuyu"], ts["days_into_tsuyu"],
        ht["heat_excess"], ht["is_hot_day"], ht["is_very_hot"],
        prev_close_min,  # 前日の最終レジ時刻（分）
        # ラグ特徴量：トレンド・前年比・勢い（成長・衰退どちらも反映）
        lf["sales_lag_7"], lf["sales_lag_28"], lf["sales_lag_365"],
        lf["sales_ma7"], lf["sales_ma28"],
        lf["yoy_ratio"], lf["momentum"],
        np.sin(2*np.pi*m/12), np.cos(2*np.pi*m/12),
        np.sin(2*np.pi*wd/7), np.cos(2*np.pi*wd/7),
        np.sin(2*np.pi*woy/52), np.cos(2*np.pi*woy/52),
    ]


def find_calib_for_pos(pos_name, calib_dict):
    """POS商品名に対応するキャリブレーションエントリを返す（優先度付きマッチング）
    優先1: 完全一致
    優先2: スプレッドシート名がPOS名の部分文字列（山食→山食1斤）
    優先3: POS名がスプレッドシート名の部分文字列（最短一致）
    """
    # 優先1: 完全一致
    if pos_name in calib_dict:
        return calib_dict[pos_name]
    # 優先2: calib_name が pos_name の部分文字列
    primary = [sn for sn in calib_dict if sn in pos_name and sn != pos_name]
    if primary:
        best = max(primary, key=len)
        return calib_dict[best]
    # 優先3: pos_name が calib_name の部分文字列（最短=最も近い商品）
    secondary = [sn for sn in calib_dict if pos_name in sn]
    if secondary:
        best = min(secondary, key=len)
        return calib_dict[best]
    return None


def predict_week(start_date, weather, models, lineup, latest_prices, mode, buffer_pct, calib=None, prev_close_min=1020, sales_map=None):
    lineup_set = set(lineup)
    calib = calib or {}
    sales_models = models.get("sales_models", {})
    results = []
    for i in range(7):
        d = start_date + timedelta(days=i)
        dt_str = d.isoformat()
        # 初日のみ前日の最終時刻を使用、2日目以降はデフォルト（17時）
        pcm = prev_close_min if i == 0 else 1020
        lag_feats = compute_lag_features(dt_str, sales_map) if sales_map else None
        X = np.array([make_features(dt_str, weather, pcm, lag_feats)])

        # モード別スケール係数（sales_modelsの分位点予測比率）
        if sales_models and mode != "normal":
            normal_pred = max(1.0, sales_models["normal"].predict(X)[0])
            mode_pred   = max(0.0, sales_models[mode].predict(X)[0])
            mode_scale  = mode_pred / normal_pred
            # 最低±10%の差を保証（逆転防止）
            if mode == "bull":
                mode_scale = max(mode_scale, 1.10)
            elif mode == "bear":
                mode_scale = min(mode_scale, 0.90)
        else:
            mode_scale = 1.0

        bread_products     = {}
        sandwich_products  = {}
        rebake_products    = {}
        filling_products_d = {}
        bread_excl    = 0.0
        sandwich_excl = 0.0
        rebake_excl   = 0.0

        for product, model in models["product_models"].items():
            if product not in lineup_set:
                continue
            qty = max(0, model.predict(X)[0])

            # キャリブレーション補正
            if calib:
                c = find_calib_for_pos(product, calib)
                if c and c.get("ml_vs_actual_ratio") is not None:
                    ratio = c["ml_vs_actual_ratio"]
                    if 0.4 <= ratio <= 2.5:
                        qty = qty / ratio  # 系統的バイアスを補正

            # モード別スケール適用（弱気↓ / 強気↑）
            qty = qty * mode_scale

            # 「その他」カテゴリ（焼き菓子・ドリンク等）は製造表・売上予測ともに除外
            if categorize_product(product) == "その他":
                continue

            qty_buf = int(np.ceil(qty * (1 + buffer_pct / 100)))
            price = latest_prices.get(product, 0)
            if is_filling(product):
                # フィリング二次製品：売上はパン類に含める、製造数はベースパン側で管理
                if qty_buf > 0:
                    filling_products_d[product] = qty_buf
                bread_excl += qty * price
            elif is_rebake(product):
                # リベイク二次製品：AI予測で個数表示
                if qty_buf > 0:
                    rebake_products[product] = qty_buf
                rebake_excl += qty * price
            elif is_sandwich(product):
                if qty_buf > 0:
                    sandwich_products[product] = qty_buf
                sandwich_excl += qty * price
            else:
                if qty_buf > 0:
                    bread_products[product] = qty_buf
                bread_excl += qty * price

        # ── 食パン1斤→2斤 統合（製造は2斤単位のため）──────────────
        for kin1, kin2 in SHOKUPAN_PAIRS:
            # 1斤商品が lineup に含まれている場合のみ処理
            prod1 = next((p for p in bread_products if kin1 in p or p in kin1), None)
            prod2 = next((p for p in bread_products if kin2 in p or p in kin2), None)
            if prod1 is None:
                continue
            qty1 = bread_products.pop(prod1)  # 1斤を製造数テーブルから除外
            extra_2kin = int(np.ceil(qty1 / 2))  # 1斤2本 = 2斤1本
            if prod2 is not None:
                bread_products[prod2] = bread_products[prod2] + extra_2kin
            elif extra_2kin > 0:
                # 2斤がラインナップになければ新規追加
                bread_products[kin2] = extra_2kin

        # ── 二次加工品用ベースパン追加数（曜日別平均）──────────────
        wd = d.weekday()
        for base_prod, uplift_by_wd in SECONDARY_UPLIFT.items():
            if base_prod not in bread_products:
                continue  # ラインナップにないベースパンはスキップ
            extra_raw = uplift_by_wd.get(wd, 0)
            if extra_raw <= 0:
                continue
            # バッファーも適用してから加算（安全マージンを確保）
            extra_buf = int(np.ceil(extra_raw * (1 + buffer_pct / 100)))
            bread_products[base_prod] = bread_products[base_prod] + extra_buf
            # 売上計算用の原価にも加算（バッファーなしで加算）
            bread_excl += extra_raw * latest_prices.get(base_prod, 0)

        w = weather.get(dt_str, {})
        results.append({
            "date": dt_str,
            "weekday": WEEKDAY_JP[d.weekday()],
            "is_weekend": d.weekday() >= 5,
            "is_holiday": _jpholiday.is_holiday(d),
            "is_school_holiday": in_period(dt_str, SCHOOL_HOLIDAYS),
            "is_waseda_holiday": in_period(dt_str, WASEDA_HOLIDAYS),
            "bread_sales":     int(bread_excl * 1.08),
            "sandwich_sales":  int(sandwich_excl * 1.08),
            "rebake_sales":    int(rebake_excl * 1.08),
            "predicted_sales": int((bread_excl + sandwich_excl + rebake_excl) * 1.08),
            "bread_products":     bread_products,
            "sandwich_products":  sandwich_products,
            "rebake_products":    rebake_products,
            "secondary_products": {**filling_products_d, **rebake_products},
            "products": {**bread_products, **sandwich_products, **rebake_products, **filling_products_d},
            "temp_max": w.get("temp_max"),
            "rain_lunch": w.get("rain_lunch_total", 0),
            "rain_evening": w.get("rain_evening_total", 0),
            "is_rainy_lunch": w.get("is_rainy_lunch", 0),
            "is_rainy_evening": w.get("is_rainy_evening", 0),
        })
    return results


def predict_all_modes(start_date, weather, models, lineup, latest_prices, buffer_pct, calib=None, prev_close_min=1020, sales_map=None):
    return {
        mode: predict_week(start_date, weather, models, lineup, latest_prices, mode, buffer_pct, calib, prev_close_min, sales_map)
        for mode in ["bear", "normal", "bull"]
    }


# ── UI ──────────────────────────────────────────────────────

# タイトル
st.markdown("""
<div style='padding: 1.8rem 0 1.4rem 0; border-bottom: 1px solid #e8e4de; margin-bottom: 1.6rem;'>
  <div style='font-size:0.62rem;letter-spacing:0.28em;color:#bbb;text-transform:uppercase;margin-bottom:0.4rem;'>Kandagawa Bakery</div>
  <div class="main-title">売上予測 & 製造数プランナー</div>
</div>
""", unsafe_allow_html=True)

models = load_models()
dataset = load_dataset()
latest_prices = dataset.get("latest_unit_prices", {})

# キャリブレーションデータ（プリコンピュート済み）
calib = load_calibration()

if calib:
    sheet_stats = calib
    sheet_data  = {}
else:
    sheet_data  = fetch_spreadsheet_data()
    sheet_stats = compute_sheet_stats(sheet_data)

# スプレッドシートの行順（並び替え用）— ネットワーク失敗時は空dict
if not sheet_data:
    sheet_data = fetch_spreadsheet_data()   # calib使用時もorder取得を試みる
sheet_order = {name: idx for idx, name in enumerate(sheet_data.keys())}

# ── サイドバー ──
with st.sidebar:
    st.markdown("### ⚙️ 設定")
    start_date = st.date_input(
        "予測開始日",
        value=date.today() + timedelta(days=1),
        min_value=date.today(),
    )
    buffer_pct = st.slider(
        "安全在庫バッファー",
        min_value=0, max_value=30, value=10, step=5,
        format="%d%%",
        help="製造数に上乗せする割合。売上予測には影響しません。"
    )
    st.divider()

    # 前日の最終レジ時刻（モデルへの入力特徴量）
    st.markdown("### 🕐 前日の最終レジ時刻")
    last_register = st.selectbox(
        "前日の最終レジ時刻",
        options=["〜15時台", "16時台", "17時台", "18時台以降"],
        index=2,  # デフォルト：17時台
        label_visibility="collapsed",
        help="前日の最終レジ打刻時刻。予測モデルの入力として使われます。"
    )
    # 選択値を分数に変換してモデルへ渡す
    prev_close_min = {"〜15時台": 900, "16時台": 990, "17時台": 1050, "18時台以降": 1110}[last_register]

    st.divider()

    # モード選択
    st.markdown("### 📊 予測モード")
    mode = st.radio(
        "予測モード選択",
        options=["bull", "normal", "bear"],
        format_func=lambda x: {"bull": "🔴 強気予測", "normal": "🟢 普通予測", "bear": "🔵 弱気予測"}[x],
        index=1,
        label_visibility="collapsed",
    )
    mode_color = MODE_COLORS[mode]
    mode_label = MODE_LABELS[mode]

    st.divider()
    st.markdown("### 🍞 ラインナップ")
    lineup = get_lineup(models)
    st.caption(f"基準日: {(date.today() - timedelta(days=1)).isoformat()}")
    st.caption(f"{len(lineup)} 商品")

    st.divider()
    show_manual = st.button("📖 使い方マニュアル", use_container_width=True)
    st.caption("天気予報: Open-Meteo")

# 予報取得（open-meteoは最大16日先まで対応）
end_date = start_date + timedelta(days=6)
FORECAST_LIMIT_DAYS = 16
days_ahead = (start_date - date.today()).days

if days_ahead > FORECAST_LIMIT_DAYS:
    # 予報範囲外：APIを呼ばずに即フォールバック
    weather = None
    st.info(
        f"📅 予測開始日（{start_date}）は今日から{days_ahead}日先のため、"
        f"天気予報データが利用できません（対応範囲：{FORECAST_LIMIT_DAYS}日先まで）。\n\n"
        "**天候データなしで過去の実績パターンのみから売上予測を行っています。**"
        "気温・降雨の影響は考慮されていないため、精度が低下する場合があります。",
    )
else:
    with st.spinner("天気予報を取得中..."):
        weather = fetch_forecast(start_date.isoformat(), end_date.isoformat())
    if weather is None:
        st.info(
            "⚠️ 天気予報の取得に失敗しました。"
            "インターネット接続を確認してください。\n\n"
            "**天候データなしで過去の実績パターンのみから売上予測を行っています。**"
            "気温・降雨の影響は考慮されていないため、精度が低下する場合があります。",
        )

weather_available = weather is not None
if not weather_available:
    weather = {}  # 空dictで make_features のデフォルト値を使用

# 全モード予測（ラグ特徴量: 過去実績から直近トレンドを自動反映）
sales_map = build_sales_map(dataset["records"])
all_results = predict_all_modes(start_date, weather, models, lineup, latest_prices, buffer_pct, calib, prev_close_min, sales_map)
results = all_results[mode]

# ── 週間売上カード ──
st.markdown('<div class="section-header">週間売上予測</div>', unsafe_allow_html=True)

cols = st.columns(7)
for col, r, bear_r, bull_r in zip(cols, results, all_results["bear"], all_results["bull"]):
    bear_val = bear_r["predicted_sales"]
    bull_val = bull_r["predicted_sales"]
    cur_val  = r["predicted_sales"]

    # バッジ
    badges = []
    if r["is_holiday"]:      badges.append('<span class="badge badge-holiday">祝</span>')
    if r["is_school_holiday"]:badges.append('<span class="badge badge-school">学休</span>')
    if r["is_waseda_holiday"]:badges.append('<span class="badge badge-waseda">早大休</span>')
    if r["is_rainy_lunch"]:   badges.append('<span class="badge badge-rain">昼雨</span>')
    if r["is_rainy_evening"]: badges.append('<span class="badge badge-rain">夕雨</span>')

    wd_color = "#c0392b" if r["is_weekend"] or r["is_holiday"] else "#2c2520"
    if not weather_available:
        temp_txt = ""
        rain_txt = "🌥️ 天気データなし"
    else:
        rain_txt = ""
        if r["rain_lunch"] > 0 or r["rain_evening"] > 0:
            rain_txt = f"昼{r['rain_lunch']:.1f}mm 夕{r['rain_evening']:.1f}mm"
        temp_txt = f"🌡{r['temp_max']:.0f}°C" if r["temp_max"] else ""

    # 弱気〜強気の範囲バー
    total_range = max(bull_val - bear_val, 1)
    fill_pct = min(100, (cur_val - bear_val) / total_range * 100)

    bread_val  = r["bread_sales"]
    sand_val   = r["sandwich_sales"]
    rebake_val = r["rebake_sales"]

    card_html = f"""
    <div class="day-card">
        <div class="date-label">{r['date'][5:]}</div>
        <div class="weekday" style="color:{wd_color}">{r['weekday']}</div>
        <div class="sales-amount">¥{cur_val:,}</div>
        <div style="font-size:0.68rem;color:#bbb;margin:0.08rem 0 0.18rem;letter-spacing:0.01em">
            パン ¥{bread_val:,} ／ サンド ¥{sand_val:,} ／ リベイク ¥{rebake_val:,}
        </div>
        <div style="margin:0.2rem 0">{''.join(badges)}</div>
        <div class="weather-info">{temp_txt} {rain_txt}</div>
        <div class="range-row">
            <span>¥{bear_val//1000}k</span>
            <div class="range-track">
                <div class="range-fill" style="left:0;width:{fill_pct:.0f}%"></div>
            </div>
            <span>¥{bull_val//1000}k</span>
        </div>
    </div>
    """
    col.markdown(card_html, unsafe_allow_html=True)

# ── 売上グラフ ──
st.markdown('<div class="section-header">売上予測グラフ</div>', unsafe_allow_html=True)

dates_label = [f"{r['date'][5:]}({r['weekday']})" for r in results]
bear_vals  = [r["predicted_sales"] for r in all_results["bear"]]
normal_vals= [r["predicted_sales"] for r in all_results["normal"]]
bull_vals  = [r["predicted_sales"] for r in all_results["bull"]]

fig = go.Figure()
fig.add_trace(go.Bar(
    x=dates_label, y=normal_vals,
    name="🟢 普通予測",
    marker_color="#1a1a1a",
    opacity=0.82,
))
fig.update_layout(
    paper_bgcolor="#ffffff", plot_bgcolor="#fafaf8",
    font=dict(color="#888", family="Inter, Noto Sans JP", size=12),
    height=360, margin=dict(t=20, b=20, l=10, r=10),
    yaxis=dict(gridcolor="#ebebeb", tickformat="¥,.0f", tickfont=dict(size=11)),
    xaxis=dict(gridcolor="#ebebeb", tickfont=dict(size=11)),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, bgcolor="rgba(0,0,0,0)", font=dict(size=13)),
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# ── テーブル共通ヘルパー ──────────────────────────────────────
def build_product_table(products_list, results, date_cols, key_field="products", sheet_stats_map=None):
    """products_list の商品をカテゴリ別にグループ化してHTML返す"""
    if sheet_stats_map is None:
        sheet_stats_map = {}
    categorized = {}
    for p in products_list:
        cat = categorize_product(p)
        categorized.setdefault(cat, []).append(p)

    category_order = [cat for cat, _ in CATEGORY_GROUPS] + ["その他"]
    n_cols = len(date_cols) + 2
    header_cells = "".join(f"<th>{c}</th>" for c in ["商品名"] + date_cols + ["週合計"])
    rows_html = ""
    for cat in category_order:
        prods = [p for p in categorized.get(cat, [])
                 if sum(r[key_field].get(p, 0) for r in results) > 0]
        if not prods:
            continue
        rows_html += f'<tr class="cat-header"><td colspan="{n_cols}">▸ {cat}</td></tr>'
        for p in prods:
            total = sum(r[key_field].get(p, 0) for r in results)
            # 実績バッジ（テーブル用コンパクトスタイル）
            stat = match_pos_to_sheet(p, sheet_stats_map) if sheet_stats_map else None
            indicator = ""
            if stat:
                if stat["sellout_rate"] > 0.33:
                    indicator = ' <span class="tbl-badge tbl-sellout">売切↑</span>'
                elif stat["avg_loss_pct"] > 15:
                    indicator = ' <span class="tbl-badge tbl-loss">廃棄↓</span>'
            # 二次加工品バッジ
            if p in SECONDARY_PRODUCTS:
                indicator += ' <span class="tbl-badge tbl-secondary">二次</span>'
            # 食パン1斤バッジ（2斤に統合済み）
            if any(kin1 in p or p in kin1 for kin1, _ in SHOKUPAN_PAIRS):
                indicator += ' <span class="tbl-badge tbl-secondary">→2斤</span>'
            p_display = p.replace("1斤", "").strip()
            cells = f"<td>{p_display}{indicator}</td>"
            for r in results:
                qty = r[key_field].get(p, 0)
                if p in SECONDARY_PRODUCTS:
                    # 二次加工品はベースパンの生産数に含まれる
                    cells += '<td style="color:#9a8070;font-size:0.72rem;letter-spacing:-0.01em">ベースパンに含む</td>'
                else:
                    color = "#1a1a1a" if qty >= 20 else "#555" if qty >= 10 else "#999"
                    cells += f'<td style="color:{color};font-weight:{"600" if qty >= 20 else "400"}">{int(qty) if qty else "—"}</td>'
            if p in SECONDARY_PRODUCTS:
                cells += '<td style="color:#ccc;font-size:0.8rem">—</td>'
            else:
                cells += f'<td style="color:#1a1a1a;font-weight:700">{int(total)}</td>'
            rows_html += f"<tr>{cells}</tr>"
    if not rows_html:
        return ""
    return f"""
    <div style="overflow-x:auto;max-height:520px;overflow-y:auto;">
    <table class="styled-table">
        <thead><tr>{header_cells}</tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    </div>"""


date_cols = [f"{r['date'][5:]}({r['weekday']})" for r in results]

# 商品をパン・サンドイッチ・二次製品に分離（スプレッドシートの行順でソート）
def sort_by_sheet(products):
    # Excel生産表の順番を優先、なければGoogleスプレッドシート順
    def sort_key(p):
        excel_idx = sheet_order_key(p, EXCEL_ORDER)
        if excel_idx < 9999:
            return (0, excel_idx)
        return (1, sheet_order_key(p, sheet_order))
    return sorted(products, key=sort_key)

# 「その他」カテゴリ（焼き菓子・ドリンク等）は製造表に表示しない
# 売上予測には含まれているが、製造計画の管理対象外
bread_products_all    = sort_by_sheet(set(
    p for r in results for p in r["bread_products"]
))
sandwich_products_all = sort_by_sheet(set(p for r in results for p in r["sandwich_products"]))
rebake_products_all   = sort_by_sheet(set(p for r in results for p in r["rebake_products"]))
secondary_products_all= sort_by_sheet(set(p for r in results for p in r["secondary_products"]))

# ── CSV（全カテゴリ合計）──
rows_for_csv = []
for plist, key in [
    (bread_products_all,    "bread_products"),
    (sandwich_products_all, "sandwich_products"),
    (rebake_products_all,   "rebake_products"),
]:
    for p in plist:
        cat = categorize_product(p)
        row = {"カテゴリ": cat, "商品名": p}
        total = 0
        for r, dc in zip(results, date_cols):
            qty = r[key].get(p, 0)
            row[dc] = qty
            total += qty
        row["週合計"] = total
        if total > 0:
            rows_for_csv.append(row)

df_csv = pd.DataFrame(rows_for_csv) if rows_for_csv else pd.DataFrame()

# 検索・DLヘッダー行
search_col, dl_col = st.columns([3, 1])
with search_col:
    search = st.text_input("商品名で絞り込み", placeholder="🔍 商品名で絞り込み...", label_visibility="collapsed")
with dl_col:
    st.download_button(
        "📥 CSV",
        data=df_csv.to_csv(index=False, encoding="utf-8-sig") if not df_csv.empty else "",
        file_name=f"製造数_{start_date}_{mode_label}.csv",
        mime="text/csv",
        use_container_width=True,
    )

# ── パン製造計画 ──────────────────────────────────────────────
st.markdown('<div class="section-header">🍞 パン製造計画</div>', unsafe_allow_html=True)

bread_weekly = sum(r["bread_sales"] for r in results)
bread_daily_avg = bread_weekly // 7
st.markdown(
    f'<div style="font-size:0.8rem;color:#aaa;margin-bottom:0.8rem;letter-spacing:0.02em">'
    f'週合計: <strong style="color:#1a1a1a">¥{bread_weekly:,}</strong>'
    f'　日平均: <strong style="color:#1a1a1a">¥{bread_daily_avg:,}</strong></div>',
    unsafe_allow_html=True,
)

filtered_bread = [p for p in bread_products_all if not search or search in p]
bread_html = build_product_table(filtered_bread, results, date_cols, "bread_products", sheet_stats)
if bread_html:
    st.markdown(bread_html, unsafe_allow_html=True)

# ── サンドイッチ計画 ──────────────────────────────────────────
st.markdown('<div class="section-header">🥪 サンドイッチ・パニーノ計画</div>', unsafe_allow_html=True)

sand_weekly = sum(r["sandwich_sales"] for r in results)
sand_daily_avg = sand_weekly // 7
st.markdown(
    f'<div style="font-size:0.8rem;color:#aaa;margin-bottom:0.8rem;letter-spacing:0.02em">'
    f'週合計: <strong style="color:#1a1a1a">¥{sand_weekly:,}</strong>'
    f'　日平均: <strong style="color:#1a1a1a">¥{sand_daily_avg:,}</strong></div>',
    unsafe_allow_html=True,
)

filtered_sand = [p for p in sandwich_products_all if not search or search in p]
sand_html = build_product_table(filtered_sand, results, date_cols, "sandwich_products", sheet_stats)
if sand_html:
    st.markdown(sand_html, unsafe_allow_html=True)
elif not filtered_sand:
    st.caption("サンドイッチは前日ラインナップに含まれていません")

# ── リベイク二次製品計画 ──────────────────────────────────────
st.markdown('<div class="section-header">🔥 リベイク二次製品計画</div>', unsafe_allow_html=True)

rebake_weekly = sum(r["rebake_sales"] for r in results)
rebake_daily_avg = rebake_weekly // 7
st.markdown(
    f'<div style="font-size:0.8rem;color:#aaa;margin-bottom:0.8rem;letter-spacing:0.02em">'
    f'週合計: <strong style="color:#1a1a1a">¥{rebake_weekly:,}</strong>'
    f'　日平均: <strong style="color:#1a1a1a">¥{rebake_daily_avg:,}</strong></div>',
    unsafe_allow_html=True,
)

filtered_rebake = [p for p in rebake_products_all if not search or search in p]
rebake_html = build_product_table(filtered_rebake, results, date_cols, "rebake_products", sheet_stats)
if rebake_html:
    st.markdown(rebake_html, unsafe_allow_html=True)
elif not filtered_rebake:
    st.caption("リベイク二次製品は前日ラインナップに含まれていません")

# ── 週合計サマリー ＋ 積み上げ棒グラフ ──────────────────────────
total_weekly = bread_weekly + sand_weekly + rebake_weekly
st.markdown('<div class="section-header">📈 週間売上予測サマリー</div>', unsafe_allow_html=True)

# 数値カード
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f'<div style="padding:0.9rem 1rem;background:#fff;border:1px solid #e8e4de;border-radius:8px;">'
        f'<div style="font-size:0.6rem;color:#aaa;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.3rem">🍞 パン類</div>'
        f'<div style="font-size:1.25rem;font-weight:700;color:#1a1a1a">¥{bread_weekly:,}</div>'
        f'<div style="font-size:0.7rem;color:#bbb">日平均 ¥{bread_weekly//7:,}</div></div>',
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f'<div style="padding:0.9rem 1rem;background:#fff;border:1px solid #e8e4de;border-radius:8px;">'
        f'<div style="font-size:0.6rem;color:#aaa;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.3rem">🔥 リベイク</div>'
        f'<div style="font-size:1.25rem;font-weight:700;color:#1a1a1a">¥{rebake_weekly:,}</div>'
        f'<div style="font-size:0.7rem;color:#bbb">日平均 ¥{rebake_weekly//7:,}</div></div>',
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f'<div style="padding:0.9rem 1rem;background:#fff;border:1px solid #e8e4de;border-radius:8px;">'
        f'<div style="font-size:0.6rem;color:#aaa;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.3rem">🥪 サンドイッチ</div>'
        f'<div style="font-size:1.25rem;font-weight:700;color:#1a1a1a">¥{sand_weekly:,}</div>'
        f'<div style="font-size:0.7rem;color:#bbb">日平均 ¥{sand_weekly//7:,}</div></div>',
        unsafe_allow_html=True,
    )
with col4:
    st.markdown(
        f'<div style="padding:0.9rem 1rem;background:#1a1a1a;border-radius:8px;">'
        f'<div style="font-size:0.6rem;color:#888;letter-spacing:0.12em;text-transform:uppercase;margin-bottom:0.3rem">合計</div>'
        f'<div style="font-size:1.25rem;font-weight:700;color:#fff">¥{total_weekly:,}</div>'
        f'<div style="font-size:0.7rem;color:#666">日平均 ¥{total_weekly//7:,}</div></div>',
        unsafe_allow_html=True,
    )

# 積み上げ棒グラフ
import plotly.graph_objects as go
chart_dates = [f"{r['date'][5:]}({r['weekday']})" for r in results]
fig = go.Figure()
fig.add_trace(go.Bar(
    name="🍞 パン類", x=chart_dates,
    y=[r["bread_sales"] for r in results],
    marker_color="#1a1a1a",
))
fig.add_trace(go.Bar(
    name="🔥 リベイク", x=chart_dates,
    y=[r["rebake_sales"] for r in results],
    marker_color="#c0392b",
))
fig.add_trace(go.Bar(
    name="🥪 サンドイッチ", x=chart_dates,
    y=[r["sandwich_sales"] for r in results],
    marker_color="#7f8c8d",
))
fig.update_layout(
    barmode="stack",
    plot_bgcolor="#f5f5f3",
    paper_bgcolor="#f5f5f3",
    font=dict(family="Noto Sans JP, sans-serif", size=12, color="#1a1a1a"),
    margin=dict(l=10, r=10, t=20, b=10),
    height=300,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    yaxis=dict(tickformat="¥,.0f", gridcolor="#e8e4de"),
    xaxis=dict(gridcolor="#e8e4de"),
)
st.plotly_chart(fig, use_container_width=True)

# ── 実績分析レポート ──────────────────────────────────────────
st.markdown('<div class="section-header">📊 実績分析レポート</div>', unsafe_allow_html=True)

if sheet_stats:
    # 集計（calibration.pkl または compute_sheet_stats からの統一インターフェース）
    total_seizo_all   = sum(s.get("total_seizo", 0)    for s in sheet_stats.values())
    total_loss_yen_all = sum(s.get("total_loss_yen", 0) for s in sheet_stats.values())
    total_loss_qty_all = sum(s.get("total_loss_qty", 0) for s in sheet_stats.values())
    total_sellout_all  = sum(s.get("n_sellout", 0)      for s in sheet_stats.values())
    loss_pct_overall   = (total_loss_qty_all / total_seizo_all * 100) if total_seizo_all else 0
    n_products = len(sheet_stats)

    # KPIカード
    k1, k2, k3, k4 = st.columns(4)
    def kpi_card(col, label, value, sub=""):
        col.markdown(
            f'<div class="metric-chip"><div class="label">{label}</div>'
            f'<div class="value">{value}</div>'
            f'<div style="font-size:0.8rem;color:#9a8070">{sub}</div></div>',
            unsafe_allow_html=True,
        )
    kpi_card(k1, "集計商品数", f"{n_products}品目", "スプレッドシート実績")
    kpi_card(k2, "総ロス金額", f"¥{total_loss_yen_all:,}", f"廃棄数量 {total_loss_qty_all:.1f}個")
    kpi_card(k3, "平均ロス率",  f"{loss_pct_overall:.1f}%", "製造数に対するロス割合")
    kpi_card(k4, "売切発生回数", f"{total_sellout_all}回", "商品×日の売切件数")

    # 商品別テーブル（ML精度列付き）
    st.markdown("#### 商品別 売切・ロス 実績 & ML精度")
    stat_rows = []
    for prod, s in sorted(sheet_stats.items(), key=lambda x: -x[1].get("total_loss_yen", 0)):
        so_r = s.get("sellout_rate", 0)
        lo_r = s.get("loss_rate", 0)
        if so_r > 0.33 and lo_r < 0.2:
            rec = "↑ 製造数を増やす"
            rec_color = "#c0392b"
        elif lo_r > 0.33 and so_r < 0.2:
            rec = "↓ 製造数を減らす"
            rec_color = "#2980b9"
        elif so_r > 0.15 and lo_r < 0.1:
            rec = "△ やや増やす"
            rec_color = "#d35400"
        else:
            rec = "○ 適正"
            rec_color = "#27ae60"

        # ML精度の色付け
        ratio = s.get("ml_vs_actual_ratio")
        if ratio is None:
            ml_cell = "—"
            ml_color = "#9a8070"
            ml_note = ""
        elif 0.85 <= ratio <= 1.15:
            ml_cell = f"{ratio:.2f}"
            ml_color = "#27ae60"
            ml_note = ""
        elif 0.7 <= ratio < 0.85 or 1.15 < ratio <= 1.3:
            ml_cell = f"{ratio:.2f}"
            ml_color = "#e67e22"
            ml_note = " ▲"
        else:
            ml_cell = f"{ratio:.2f}"
            ml_color = "#c0392b"
            ml_note = " ★補正中" if 0.4 <= ratio <= 2.5 else " ✕対象外"

        stat_rows.append({
            "商品名": prod,
            "集計日数": s.get("n_days", 0),
            "売切回数": s.get("n_sellout", 0),
            "売切率": f"{so_r*100:.0f}%",
            "ロス回数": s.get("n_loss", 0),
            "平均ロス%": f"{s.get('avg_loss_pct', 0):.1f}%",
            "ロス金額": f"¥{s.get('total_loss_yen', 0):,}",
            "_推奨": rec,
            "_rec_color": rec_color,
            "_ml_cell": ml_cell + ml_note,
            "_ml_color": ml_color,
        })

    if stat_rows:
        header_s = "".join(
            f"<th>{h}</th>"
            for h in ["商品名","集計日数","売切回数","売切率","ロス回数","平均ロス%","ロス金額","ML比率","推奨"]
        )
        body_s = ""
        for row in stat_rows:
            body_s += (
                f'<tr>'
                f'<td style="text-align:left">{row["商品名"]}</td>'
                f'<td>{row["集計日数"]}</td>'
                f'<td>{row["売切回数"]}</td>'
                f'<td>{row["売切率"]}</td>'
                f'<td>{row["ロス回数"]}</td>'
                f'<td>{row["平均ロス%"]}</td>'
                f'<td>{row["ロス金額"]}</td>'
                f'<td style="color:{row["_ml_color"]};font-weight:600">{row["_ml_cell"]}</td>'
                f'<td style="color:{row["_rec_color"]};font-weight:600">{row["_推奨"]}</td>'
                f'</tr>'
            )
        st.markdown(
            f'<div style="overflow-x:auto;max-height:420px;overflow-y:auto;">'
            f'<table class="styled-table"><thead><tr>{header_s}</tr></thead>'
            f'<tbody>{body_s}</tbody></table></div>',
            unsafe_allow_html=True,
        )
        st.caption(
            "ML比率: MLモデル予測 ÷ 実売数。"
            " 🟢 0.85〜1.15=良好　🟠 0.7〜0.85 / 1.15〜1.3=中程度のバイアス　"
            "🔴 <0.7 / >1.3=大きなバイアス（補正適用中）"
        )
else:
    st.caption("実績データが見つかりません。calibration.pkl を生成してください。")

# ── 凡例 ──
with st.expander("ℹ️ 凡例・説明"):
    st.markdown(f"""
**予測モード**
- 🔵 **弱気**: 過去の同条件で下位25%の水準（廃棄リスク最小）
- 🟢 **普通**: 過去の中央値（標準的な製造数）
- 🔴 **強気**: 過去の同条件で上位25%の水準（売り切れリスク最小）

**バッジ**
- 🟡 **祝** 祝日 / 🔵 **学休** 小中学校休業 / 🟣 **早大休** 早稲田大学休業
- 💧 **昼雨** 11〜14時降雨 / 💧 **夕雨** 16〜18時降雨

**売上予測について**
- 税込み表示（消費税8%・軽減税率）
- 最新単価 × 予測数量で積み上げ計算
- カード下部のバーは弱気〜強気の予測レンジを示します
- 安全在庫バッファーは製造数のみに適用（売上計算には影響しません）

**実績インジケーター（製造数テーブル）**
- 🔴 **売切↑**: 過去33%以上の日で売り切れ → 製造数の増加を検討
- 🟡 **廃棄↓**: 平均ロス率15%超 → 製造数の削減またはバッファー引き下げを検討

**実績分析レポートの推奨コメント**
- ↑ 製造数を増やす: 売切率33%超かつロス率20%未満
- ↓ 製造数を減らす: ロス率33%超かつ売切率20%未満
- △ やや増やす: 売切率15〜33%程度
- ○ 適正: バランスが取れている
""")

# ── マニュアル ────────────────────────────────────────────────
if show_manual:
    st.markdown("---")
    st.markdown('<div class="section-header">📖 使い方マニュアル</div>', unsafe_allow_html=True)
    st.markdown("""
## アプリを開く

スマホ・タブレット・パソコンのブラウザで下のアドレスを開くだけ。インターネットにつながっていればどこからでも使えます。

```
kandagawa-bakery-production.up.railway.app
```

**パスワード：** `Kandagawa0222`

---

## 毎日の使い方

**3ステップで製造計画が完成します。**

**① 日付を選ぶ**　画面左のパネルから、計画を立てたい週の開始日を選びます。

**② モードを選ぶ**

| モード | こんな日に使う |
|---|---|
| 🔴 強気 | 天気がよい・イベントがある |
| 🟢 普通 | いつも通りの日 |
| 🔵 弱気 | 雨・連休明けなど |

**③ 製造数を確認する**　商品ごとの製造推奨数が表示されます。スプレッドシートと同じ並び順なので、そのまま転記できます。

---

## 画面の見方

**週間カード**　1週間分の売上予測が並びます。数字は税込の予測売上です。
バッジの意味：祝＝祝日 / 学休＝学校休み / 早大休＝早稲田休み / 昼雨・夕雨＝雨予報

**製造計画**　3つのセクションに分かれています。
- 🍞 パン — 食パン・惣菜パンなど
- 🥪 サンドイッチ — バゲットサンド・パニーノなど
- 🔥 二次製品 — フレンチトースト・クロックムッシュなど

🔴 **売切注意** — よく売り切れる商品。多めに検討
🔵 **廃棄注意** — ロスが出やすい商品。少なめに検討

---

## バッファーとは

製造数に上乗せする「余裕」のことです。

- **0%** → 予測通りに製造
- **10%** → 予測より1割多く製造（通常はここ）
- **20%** → 予測より2割多く製造

---

## 月に1回やること

前月のスプレッドシートが埋まったら、ターミナルで以下を実行します（約5分）。

```
python3 parse_sheets.py
python3 build_calibration.py
git add calibration.pkl sheet_actuals.pkl
git commit -m "月次更新"
git push
```

pushすると2〜3分でクラウドに自動反映されます。

---

## 困ったときは

| 症状 | 対処 |
|---|---|
| アプリが開かない | インターネット接続を確認してください |
| パスワードが通らない | 大文字・小文字に注意。コピー&貼り付けが確実です |
| 天気が取れないと表示される | 17日以上先は天気予報が使えません。予測は続きます |
| 数字が古い気がする | ブラウザを再読み込み（⌘R）してください |
| 月次更新後に反映されない | git pushから2〜3分待って再読み込みしてください |
""")
