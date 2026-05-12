"""
データ前処理スクリプト
売上CSV（4年分）と天候データを結合し、学習用データセットを生成する
"""
import csv
import json
import os
from collections import defaultdict
from datetime import date, timedelta

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

SALES_FILES = [
    "商品-2022-05-11-2023-05-11.csv",
    "商品-2023-05-11-2024-05-11.csv",
    "商品-2024-05-11-2025-05-11.csv",
    "商品-2025-05-11-2026-05-11.csv",
]

WEATHER_FILE = "weather_toshima_2021_2026.csv"
WEATHER_HOURLY_FILE = "weather_hourly_toshima.csv"

# 予測対象外のカテゴリ（袋・ドリンク・割引など）
EXCLUDE_CATEGORIES = {
    "レジ袋", "袋／箱", "ドリンク", "割引", "焼菓子割引",
    "粉／粉割引", "モバイル", "なし", "アソート", "ミックス粉", "前日焼",
}

# 豊島区立小中学校の休業期間（年度ごと）
SCHOOL_HOLIDAYS = [
    # 2022年度
    ("2022-07-21", "2022-08-31"),
    ("2022-12-26", "2023-01-09"),
    ("2023-03-25", "2023-04-06"),
    # 2023年度
    ("2023-07-21", "2023-08-31"),
    ("2023-12-26", "2024-01-08"),
    ("2024-03-26", "2024-04-07"),
    # 2024年度
    ("2024-07-22", "2024-08-31"),
    ("2024-12-26", "2025-01-07"),
    ("2025-03-25", "2025-04-06"),
    # 2025年度
    ("2025-07-21", "2025-08-31"),
    ("2025-12-26", "2026-01-07"),
    ("2026-03-26", "2026-04-05"),
]

# 早稲田大学の休業期間
WASEDA_HOLIDAYS = [
    # 2022年度
    ("2022-07-25", "2022-09-21"),
    ("2023-02-04", "2023-03-31"),
    # 2023年度
    ("2023-07-25", "2023-09-20"),
    ("2024-02-04", "2024-03-31"),
    # 2024年度
    ("2024-07-29", "2024-09-20"),
    ("2025-02-04", "2025-03-31"),
    # 2025年度
    ("2025-07-30", "2025-09-20"),
    ("2026-02-04", "2026-03-31"),
]

import math
import jpholiday as _jpholiday

# ── 東京（新宿区・豊島区）桜開花・満開日 ─────────────────────────
# 気象庁標準木（靖国神社）+ 新宿御苑・神田川近辺の実績
SAKURA_DATES = {
    2022: {"kaika": date(2022, 3, 20), "mankai": date(2022, 3, 27)},
    2023: {"kaika": date(2023, 3, 14), "mankai": date(2023, 3, 22)},
    2024: {"kaika": date(2024, 3, 29), "mankai": date(2024, 4,  5)},
    2025: {"kaika": date(2025, 3, 25), "mankai": date(2025, 4,  2)},
    2026: {"kaika": date(2026, 3, 26), "mankai": date(2026, 4,  3)},  # 気象庁長期予報ベース推定
}

def sakura_features(dt: date) -> dict:
    """桜関連の特徴量を計算する"""
    year = dt.year
    # 年が見つからない場合は前後の年で補間
    if year not in SAKURA_DATES:
        year = max(k for k in SAKURA_DATES if k <= year) if any(k <= year for k in SAKURA_DATES) else min(SAKURA_DATES)

    mankai = SAKURA_DATES[year]["mankai"]
    kaika  = SAKURA_DATES[year]["kaika"]
    days_from_mankai = (dt - mankai).days  # 負=満開前、正=満開後

    # sakura_score: 満開日を頂点とするベル曲線（開花〜散り終わりまで）
    # 開花〜満開: 線形に0→1、満開〜+7日: 1.0、+7〜+21日: 線形に1→0
    kaika_to_mankai = max((mankai - kaika).days, 1)
    days_from_kaika = (dt - kaika).days

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
        "sakura_score":      round(max(0.0, score), 4),
        "days_from_mankai":  max(-30, min(30, days_from_mankai)),
        "is_sakura_peak":    int(-7 <= days_from_mankai <= 7),
    }


# ── 東京 梅雨入り・明け日（気象庁発表実績） ─────────────────────────
TSUYU_DATES = {
    2022: {"iri": date(2022, 6,  6), "ake": date(2022, 7, 23)},
    2023: {"iri": date(2023, 6,  8), "ake": date(2023, 7, 22)},
    2024: {"iri": date(2024, 6, 21), "ake": date(2024, 7, 18)},
    2025: {"iri": date(2025, 6, 10), "ake": date(2025, 7, 20)},  # 暫定（確定後更新）
    2026: {"iri": date(2026, 6, 10), "ake": date(2026, 7, 20)},  # 平年値ベース推定
}

def tsuyu_features(dt: date) -> dict:
    """梅雨関連の特徴量"""
    year = dt.year
    if year not in TSUYU_DATES:
        year = max(k for k in TSUYU_DATES if k <= year) if any(k <= year for k in TSUYU_DATES) else min(TSUYU_DATES)
    iri = TSUYU_DATES[year]["iri"]
    ake = TSUYU_DATES[year]["ake"]
    is_tsuyu = int(iri <= dt <= ake)
    # 梅雨入り・梅雨明けからの距離（気分が変わるタイミングを捉える）
    days_from_iri = (dt - iri).days
    return {
        "is_tsuyu":        is_tsuyu,
        "days_into_tsuyu": max(0, min(days_from_iri, 45)) if is_tsuyu else 0,
    }


def heat_features(temp_max: float) -> dict:
    """猛暑関連の特徴量（30度超えで売上が落ちる傾向）"""
    return {
        "heat_excess":  round(max(0.0, temp_max - 30.0), 1),  # 30度超過分
        "is_hot_day":   int(temp_max >= 30),
        "is_very_hot":  int(temp_max >= 35),
    }


def _build_national_holidays(from_year=2021, to_year=2027):
    holidays = set()
    d = date(from_year, 1, 1)
    end = date(to_year, 12, 31)
    while d <= end:
        if _jpholiday.is_holiday(d):
            holidays.add(d.isoformat())
        d += timedelta(days=1)
    return holidays

NATIONAL_HOLIDAYS = _build_national_holidays()


def build_holiday_sets():
    school_set = set()
    for start_s, end_s in SCHOOL_HOLIDAYS:
        d = date.fromisoformat(start_s)
        end = date.fromisoformat(end_s)
        while d <= end:
            school_set.add(d.isoformat())
            d += timedelta(days=1)

    waseda_set = set()
    for start_s, end_s in WASEDA_HOLIDAYS:
        d = date.fromisoformat(start_s)
        end = date.fromisoformat(end_s)
        while d <= end:
            waseda_set.add(d.isoformat())
            d += timedelta(days=1)

    return school_set, waseda_set


def load_weather():
    weather = {}
    path = os.path.join(DATA_DIR, WEATHER_FILE)
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            weather[row["日付"]] = {
                "temp_max": float(row["最高気温(°C)"] or 0),
                "temp_min": float(row["最低気温(°C)"] or 0),
                "temp_mean": float(row["平均気温(°C)"] or 0),
                "sunshine_sec": float(row["日照時間(秒)"] or 0),
                "wind_max": float(row["最大風速(km/h)"] or 0),
                "weather_code": int(float(row["天気コード"] or 0)),
            }

    # 時間別降水量データを結合
    hourly_path = os.path.join(DATA_DIR, WEATHER_HOURLY_FILE)
    with open(hourly_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dt = row["日付"]
            if dt not in weather:
                weather[dt] = {}
            weather[dt].update({
                "rain_lunch_total":   float(row["昼雨量合計(mm)"] or 0),
                "rain_lunch_max":     float(row["昼最大時間雨量(mm)"] or 0),
                "rain_evening_total": float(row["夕方雨量合計(mm)"] or 0),
                "rain_evening_max":   float(row["夕方最大時間雨量(mm)"] or 0),
                "rain_morning":       float(row["朝雨量(mm)"] or 0),
                "rain_lunch_heavy":   float(row["昼大雨時間数"] or 0),
                "rain_evening_heavy": float(row["夕方大雨時間数"] or 0),
            })
    return weather


def load_sales():
    daily_sales = defaultdict(float)
    daily_products = defaultdict(lambda: defaultdict(float))
    latest_prices = {}  # product -> (date, unit_price)

    for filename in SALES_FILES:
        path = os.path.join(DATA_DIR, filename)
        with open(path, encoding="utf-16") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                dt = row.get("日付", "").strip()
                if not dt:
                    continue
                category = row.get("カテゴリ", "").strip()
                if category in EXCLUDE_CATEGORIES:
                    continue
                product = row.get("商品", "").strip().replace("＊", "")
                if not product:
                    continue
                try:
                    qty = float(row.get("数量", 0) or 0)
                    amount = float(
                        row.get("純売上高", "0")
                        .replace("¥", "")
                        .replace(",", "")
                        or 0
                    )
                except ValueError:
                    continue

                daily_sales[dt] += amount
                daily_products[dt][product] += qty

                # 最新単価を記録（日付が新しいものを優先）
                if qty > 0 and amount > 0:
                    unit_price = amount / qty
                    if product not in latest_prices or dt > latest_prices[product][0]:
                        latest_prices[product] = (dt, unit_price)

    # 日付情報を除いて単価だけのdictに変換
    latest_unit_prices = {p: price for p, (_, price) in latest_prices.items()}
    return daily_sales, daily_products, latest_unit_prices


def build_dataset():
    print("休業日セットを構築中...")
    school_set, waseda_set = build_holiday_sets()

    print("天候データを読み込み中...")
    weather = load_weather()

    print("売上データを読み込み中...")
    daily_sales, daily_products, latest_unit_prices = load_sales()

    print("データセットを結合中...")
    records = []
    for dt_str in sorted(daily_sales.keys()):
        d = date.fromisoformat(dt_str)
        w = weather.get(dt_str, {})

        record = {
            "date": dt_str,
            "year": d.year,
            "month": d.month,
            "day": d.day,
            "weekday": d.weekday(),          # 0=月, 6=日
            "is_weekend": int(d.weekday() >= 5),
            "is_holiday": int(dt_str in NATIONAL_HOLIDAYS),
            "is_school_holiday": int(dt_str in school_set),
            "is_waseda_holiday": int(dt_str in waseda_set),
            "temp_max": w.get("temp_max", 0),
            "temp_min": w.get("temp_min", 0),
            "temp_mean": w.get("temp_mean", 0),
            "sunshine_sec": w.get("sunshine_sec", 0),
            "wind_max": w.get("wind_max", 0),
            "weather_code": w.get("weather_code", 0),
            # 営業時間帯別降水量（時間別データより）
            "rain_lunch_total":   w.get("rain_lunch_total", 0),    # 11-14時 合計
            "rain_lunch_max":     w.get("rain_lunch_max", 0),      # 11-14時 最大時間雨量
            "rain_lunch_heavy":   w.get("rain_lunch_heavy", 0),    # 11-14時 大雨時間数
            "rain_evening_total": w.get("rain_evening_total", 0),  # 16-18時 合計
            "rain_evening_max":   w.get("rain_evening_max", 0),    # 16-18時 最大時間雨量
            "rain_evening_heavy": w.get("rain_evening_heavy", 0),  # 16-18時 大雨時間数
            "rain_morning":       w.get("rain_morning", 0),        # 10時
            "is_rainy_lunch":   int(w.get("rain_lunch_total", 0) > 1.0),
            "is_rainy_evening": int(w.get("rain_evening_total", 0) > 1.0),
            "total_sales": daily_sales[dt_str],
            **sakura_features(d),
            **tsuyu_features(d),
            **heat_features(w.get("temp_max", 20)),
        }

        for product, qty in daily_products[dt_str].items():
            record[f"qty_{product}"] = qty

        records.append(record)

    return records, latest_unit_prices


def get_all_products(records):
    products = set()
    for r in records:
        for k in r:
            if k.startswith("qty_"):
                products.add(k[4:])
    return sorted(products)


if __name__ == "__main__":
    records, latest_unit_prices = build_dataset()
    products = get_all_products(records)

    print(f"\n完了: {len(records)}日分のデータを構築")
    print(f"商品種類: {len(products)}種")
    print(f"期間: {records[0]['date']} 〜 {records[-1]['date']}")

    # 出力（pickle形式で保存）
    import pickle
    out_path = os.path.join(DATA_DIR, "dataset.pkl")
    with open(out_path, "wb") as f:
        pickle.dump({
            "records": records,
            "products": products,
            "latest_unit_prices": latest_unit_prices,
        }, f)
    print(f"保存: {out_path}")
    print(f"最新単価取得済み商品数: {len(latest_unit_prices)}")
