"""
parse_sheets.py  ―  Googleスプレッドシートから実績データを取得・保存

月1回の更新作業：python3 parse_sheets.py

スプレッドシートの「手動生産表」シートからパンの
  製造数／売切時間／ロス数量／ロス金額
を読み込み、sheet_actuals.pkl に保存します。
"""

import csv
import io
import os
import pickle
import urllib.request
from datetime import date

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# ── スプレッドシート設定 ──────────────────────────────────────────
# app.py の fetch_spreadsheet_data() と同じURLを使用
SHEET_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "1hLmRFfAm_kfjr_hk-G4GhGBwvJ5g_sNU/export?format=csv&gid=753872113"
)
SECTION_TYPES = {"定番", "季節", "サンド", "二次"}


def download_csv() -> str:
    """スプレッドシートをCSV文字列として取得する"""
    req = urllib.request.Request(SHEET_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.read().decode("utf-8")


def parse_csv(content: str) -> dict:
    """CSVを解析し sheet_actuals 形式の辞書を返す

    Returns:
        {
            "商品名": {
                "YYYY-MM-DD": {
                    "製造数": float,
                    "売切時間": str,
                    "ロス数量": float,
                    "ロス金額": int,
                    "実売数":   float,   # 製造数 - ロス数量
                },
                ...
            },
            ...
        }
    """
    today = date.today()
    rows = list(csv.reader(io.StringIO(content)))

    if len(rows) < 8:
        raise ValueError(f"スプレッドシートの行数が不正です（{len(rows)}行）。形式を確認してください。")

    row0 = rows[0]

    # ── 日付列インデックスを特定 ──────────────────────────────────
    # 行0の各セルが "M/D" 形式なら日付列と判定
    date_cols: list[tuple[int, str]] = []
    for i, v in enumerate(row0):
        v = v.strip()
        if v and "/" in v and len(v) <= 5 and v.count("/") == 1:
            try:
                m, d_num = map(int, v.split("/"))
                # 現在日付から±400日以内で最も近い年を付与
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

    if not date_cols:
        raise ValueError("スプレッドシートに日付列が見つかりません。")

    print(f"  日付列: {len(date_cols)} 日分 "
          f"({date_cols[0][1]} 〜 {date_cols[-1][1]})")

    # ── 商品行を解析 ──────────────────────────────────────────────
    result: dict = {}
    n_parsed = 0

    for row in rows[7:]:
        type_col  = row[0].strip() if len(row) > 0 else ""
        prod_name = row[1].strip() if len(row) > 1 else ""
        if type_col not in SECTION_TYPES or not prod_name:
            continue

        prod_data: dict = {}
        for col, dt in date_cols:
            # 各日付のデータブロック: [製造数, 単位, 計画売上, 売切時間, ロス数量, ロス金額]
            if col + 5 >= len(row):
                continue
            try:
                seizo    = float(row[col].strip())       if row[col].strip()   else 0.0
                saikiri  = row[col + 3].strip()
                loss_qty = float(row[col + 4].strip())   if row[col + 4].strip() else 0.0
                loss_yen = int(float(row[col + 5].strip())) if row[col + 5].strip() else 0
            except (ValueError, IndexError):
                continue

            if seizo > 0:
                jitsu = max(0.0, seizo - loss_qty)
                prod_data[dt] = {
                    "製造数":   seizo,
                    "売切時間": saikiri,
                    "ロス数量": loss_qty,
                    "ロス金額": loss_yen,
                    "実売数":   jitsu,
                }
                n_parsed += 1

        if prod_data:
            result[prod_name] = prod_data

    return result


def main():
    print("=== parse_sheets.py ===")
    print(f"スプレッドシートを取得中...")

    try:
        content = download_csv()
    except Exception as e:
        print(f"❌ ダウンロード失敗: {e}")
        print("  インターネット接続とスプレッドシートの共有設定を確認してください。")
        raise SystemExit(1)

    print("解析中...")
    try:
        sheet_actuals = parse_csv(content)
    except ValueError as e:
        print(f"❌ 解析失敗: {e}")
        raise SystemExit(1)

    total_records = sum(len(v) for v in sheet_actuals.values())
    print(f"  商品数: {len(sheet_actuals)} 品目")
    print(f"  レコード数: {total_records} 件")

    out_path = os.path.join(DATA_DIR, "sheet_actuals.pkl")
    with open(out_path, "wb") as f:
        pickle.dump(sheet_actuals, f)
    print(f"✅ 保存完了: {out_path}")


if __name__ == "__main__":
    main()
