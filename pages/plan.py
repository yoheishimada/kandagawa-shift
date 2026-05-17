import os, pickle, json
import numpy as np
import pandas as pd
import streamlit as st
from datetime import date, timedelta

st.set_page_config(page_title="生産計画表 | 神田川ベーカリー", layout="wide")

# 認証チェック
if not st.session_state.get("authenticated", False):
    st.switch_page("app.py")

# session_state から予測結果を取得
results        = st.session_state.get("plan_results")
latest_prices  = st.session_state.get("plan_latest_prices")
start_date     = st.session_state.get("plan_start_date")
mode_label     = st.session_state.get("plan_mode_label", "普通予測")

if results is None or latest_prices is None:
    st.warning("メインページで予測を確認してから、「生産計画表を開く」ボタンでこのページを開いてください。")
    if st.button("← メインページへ"):
        st.switch_page("app.py")
    st.stop()

# ── 定数（app.py からコピー、循環インポート回避） ──────────────────────

FILLING_PRODUCTS = {
    "あんこ塩ぱん",
    "あんこ塩パン",
    "いちご練乳スティック",
    "プレーンプチ（クリーム入り）",
    "プレーンプチ（マロンミルククリーム入り）",
    "プレーンプチ（レモンクリーム入り）",
    "チョコチッププチ（クリーム入）",
    "レーズンプチ（クリーム入り）",
}

SECONDARY_PRODUCTS = FILLING_PRODUCTS | {
    "クロックムッシュ", "タルティーヌ", "フレンチトースト",
    "ニース風ホット", "カリカリハニー", "明太フランス",
    "ピザトースト", "本日のトースト", "本日のフレンチトースト",
    "ナンテールトースト", "バゲットのフレンチトースト",
    "きのこクリームのバゲットトースト",
}

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


def categorize_product(name):
    for category, keywords in CATEGORY_GROUPS:
        for kw in keywords:
            if kw in name:
                return category
    return "その他"


def sheet_order_key(pos_name, sheet_order):
    """スプレッドシートの行順インデックスを返す（マッチしない場合は末尾）"""
    if pos_name in sheet_order:
        return sheet_order[pos_name]
    primary = [sn for sn in sheet_order if sn in pos_name and sn != pos_name]
    if primary:
        best = max(primary, key=len)
        return sheet_order[best]
    secondary = [sn for sn in sheet_order if pos_name in sn]
    if secondary:
        best = min(secondary, key=len)
        return sheet_order[best]
    return 9999


def sort_by_sheet(products):
    def sort_key(p):
        excel_idx = sheet_order_key(p, EXCEL_ORDER)
        if excel_idx < 9999:
            return (0, excel_idx)
        return (1, excel_idx)
    return sorted(products, key=sort_key)


# ── 列幅定数 ──
_IDX_W = 200   # 商品名列
_COL_W = 100   # 日付列 × 7

# ── results から各製品リストを再構築 ──
bread_products_all    = sort_by_sheet(set(p for r in results for p in r["bread_products"]))
sandwich_products_all = sort_by_sheet(set(p for r in results for p in r["sandwich_products"]))
rebake_products_all   = sort_by_sheet(set(p for r in results for p in r["rebake_products"]))

# ── 日付ラベル再計算 ──
plan_date_labels = [
    f"{r['weekday']} {int(r['date'][5:7])}/{int(r['date'][8:10])}"
    for r in results
]

# ── 表示名クリーニング ──
def _clean_name(name):
    return name.replace("1斤", "").replace("食パン", "").strip()

# ── ページ上部ナビゲーション ──
if st.button("← メインページに戻る"):
    st.switch_page("app.py")

st.markdown(f"### 生産計画表　{start_date} 〜　{mode_label}")

# ── 生産計画表（編集・CSV出力） ─────────────────────────────────────
st.caption("数字はその場で修正できます。確定したら「CSVダウンロード」で吉田さんのスプレッドシートに貼り付けてください。")

# 製造計画テーブルと同じ順番：パン → サンドイッチ → リベイク
plan_products = (
    [p for p in bread_products_all    if p not in SECONDARY_PRODUCTS] +
    [p for p in sandwich_products_all if p not in SECONDARY_PRODUCTS] +
    [p for p in rebake_products_all   if p not in SECONDARY_PRODUCTS]
)

# 元名→表示名のマッピング（売上計算で元名を使うため）
plan_name_map = {p: _clean_name(p) for p in plan_products}

# DataFrame構築（表示名をインデックスに使用）
plan_rows = {}
for p in plan_products:
    row = []
    for r in results:
        qty = (
            r["bread_products"].get(p, 0)
            or r["sandwich_products"].get(p, 0)
            or r["rebake_products"].get(p, 0)
        )
        row.append(int(qty) if qty else 0)
    plan_rows[plan_name_map[p]] = row

plan_df = pd.DataFrame(plan_rows, index=plan_date_labels).T
plan_df.index.name = "商品名"

_N     = len(plan_date_labels)
_TOTAL = _IDX_W + _COL_W * _N   # 900px

# 売上カードのコンテナを先に確保
sales_container = st.container()

# 編集可能テーブル（列幅を固定値で指定）
edited_df = st.data_editor(
    plan_df,
    use_container_width=False,
    width=_TOTAL + 4,   # +4 は内部ボーダー分
    num_rows="fixed",
    key="plan_editor",
    column_config={
        "商品名": st.column_config.Column(width=_IDX_W),
        **{col: st.column_config.NumberColumn(
                col, min_value=0, step=1, format="%d", width=_COL_W)
           for col in plan_date_labels},
    },
)

# 表示名→元名の逆引きマップ（単価取得に使用）
plan_name_reverse = {v: k for k, v in plan_name_map.items()}

# 編集後の数量 × 単価で売上を再計算（NaN・None は 0 扱い）
TAX_RATE = 1.08
sales_by_day = {}
for col in plan_date_labels:
    total = 0
    for display_name in edited_df.index:
        raw = edited_df.loc[display_name, col]
        qty = int(raw) if (raw is not None and pd.notna(raw)) else 0
        orig_name = plan_name_reverse.get(display_name, display_name)
        price = latest_prices.get(orig_name, latest_prices.get(display_name, 0))
        total += qty * price * TAX_RATE
    sales_by_day[col] = int(total)
weekly_sales_total = sum(sales_by_day.values())

# 売上カードを data_editor の列幅にぴったり合わせて描画
with sales_container:
    total_card = (
        f'<div style="width:{_IDX_W}px;flex-shrink:0;background:#eaf2fb;'
        f'border:1px solid #b0cfe8;border-radius:8px;'
        f'padding:0.5rem 0.7rem;display:flex;flex-direction:column;justify-content:center;">'
        f'<div style="font-size:0.58rem;color:#4a7fa8;font-weight:600;letter-spacing:0.08em;margin-bottom:0.1rem">週合計 売上予測</div>'
        f'<div style="font-size:1.1rem;font-weight:700;color:#1a1a1a">¥{weekly_sales_total:,}</div>'
        f'</div>'
    )
    day_cards = "".join(
        f'<div style="width:{_COL_W}px;flex-shrink:0;background:#f5f9fd;'
        f'border:1px solid #d0e4f4;border-radius:8px;'
        f'padding:0.45rem 0.2rem;text-align:center;">'
        f'<div style="font-size:0.58rem;color:#7aafd4;font-weight:600;letter-spacing:0.04em">{col_label}</div>'
        f'<div style="font-size:0.88rem;font-weight:700;color:#1a1a1a">¥{sales_val:,}</div>'
        f'</div>'
        for col_label, sales_val in sales_by_day.items()
    )
    st.markdown(
        f'<div style="display:flex;gap:2px;width:{_TOTAL}px;margin-bottom:0.4rem;">'
        f'{total_card}{day_cards}</div>',
        unsafe_allow_html=True,
    )

# 週合計列を追加してCSV出力
export_df = edited_df.copy()
export_df["週合計"] = export_df.sum(axis=1)
csv_bytes = export_df.reset_index().to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button(
    label="CSVダウンロード",
    data=csv_bytes,
    file_name=f"生産計画_{start_date}.csv",
    mime="text/csv",
    use_container_width=True,
)
