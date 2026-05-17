"""
Square APIから当日の売上データを取得し、CSVに追記するスクリプト
毎晩23:30に実行することを想定
"""
import os
import csv
import requests
from datetime import date, timedelta

# .env ファイルがあれば読み込む（ローカル開発用）
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

ACCESS_TOKEN = os.environ.get("SQUARE_ACCESS_TOKEN", "")
LOCATION_ID  = os.environ.get("SQUARE_LOCATION_ID", "EMF8KF9VJ6RRN")
DATA_DIR     = os.path.dirname(os.path.abspath(__file__))
CSV_PATH     = os.path.join(DATA_DIR, "商品-square-auto.csv")

HEADERS = {
    "Square-Version": "2024-01-17",
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json"
}

# 既存CSVと同じ列構成（モデルが使う最低限の列）
CSV_COLUMNS = ["日付", "時間", "商品", "数量", "純売上高"]


def fetch_payments(target_date: date) -> list[dict]:
    """指定日の全決済を取得"""
    begin = f"{target_date}T00:00:00+09:00"
    end   = f"{target_date}T23:59:59+09:00"
    all_payments, cursor = [], None

    while True:
        params = {
            "location_id": LOCATION_ID,
            "begin_time": begin,
            "end_time": end,
            "limit": 100,
        }
        if cursor:
            params["cursor"] = cursor
        resp = requests.get(
            "https://connect.squareup.com/v2/payments",
            headers=HEADERS, params=params, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        all_payments.extend(data.get("payments", []))
        cursor = data.get("cursor")
        if not cursor:
            break

    print(f"  決済件数: {len(all_payments)}件")
    return all_payments


def fetch_order(order_id: str) -> dict:
    """注文詳細（商品明細）を取得"""
    resp = requests.get(
        f"https://connect.squareup.com/v2/orders/{order_id}",
        headers=HEADERS, timeout=30
    )
    resp.raise_for_status()
    return resp.json().get("order", {})


def payments_to_rows(payments: list[dict], target_date: date) -> list[dict]:
    """決済データを CSV行形式に変換"""
    rows = []
    for p in payments:
        if not p.get("order_id"):
            continue
        time_str = p["created_at"][11:19]  # HH:MM:SS（JST）
        order = fetch_order(p["order_id"])
        for item in order.get("line_items", []):
            qty    = float(item.get("quantity", 1))
            amount = item.get("total_money", {}).get("amount", 0)
            name   = item.get("name", "不明")
            rows.append({
                "日付": str(target_date),
                "時間": time_str,
                "商品": name,
                "数量": qty,
                "純売上高": f"¥{amount:,}",
            })
    return rows


def load_existing_dates() -> set[str]:
    """既存CSVに記録済みの日付を返す"""
    if not os.path.exists(CSV_PATH):
        return set()
    dates = set()
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            dates.add(row.get("日付", ""))
    return dates


def append_rows(rows: list[dict]):
    """CSVに行を追記（ファイルがなければヘッダーも書く）"""
    file_exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in CSV_COLUMNS})


def run(target_date: date = None):
    if not ACCESS_TOKEN:
        raise ValueError("環境変数 SQUARE_ACCESS_TOKEN が設定されていません")

    if target_date is None:
        target_date = date.today() - timedelta(days=1)  # 昨日分

    print(f"[fetch_square] {target_date} のデータを取得中...")

    # すでに取得済みならスキップ
    existing = load_existing_dates()
    if str(target_date) in existing:
        print(f"  → {target_date} はすでに記録済みです。スキップします。")
        return 0

    payments = fetch_payments(target_date)
    if not payments:
        print(f"  → 決済データなし（定休日？）")
        return 0

    rows = payments_to_rows(payments, target_date)
    if not rows:
        print(f"  → 商品明細なし")
        return 0

    append_rows(rows)
    total = sum(
        int(r["純売上高"].replace("¥", "").replace(",", ""))
        for r in rows
    )
    print(f"  → {len(rows)}行追記完了  売上合計: ¥{total:,}")
    return len(rows)


if __name__ == "__main__":
    import sys
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None
    run(target)
