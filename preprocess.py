"""
データ前処理スクリプト
売上CSV（4年分）と天候データを結合し、学習用データセットを生成する
"""
import csv
import json
import os
import pickle
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


def post_holiday_features(dt: date) -> dict:
    """3日以上連続した祝日の翌1〜7日間に立つフラグ。
    GW・年末年始・シルバーウィーク明けの売上跳ね上がりを明示的にモデルに伝える。
    ※当日が祝日の場合・土日は0（店は通常営業）。
    """
    _ZERO = {"is_post_long_holiday": 0, "days_after_long_holiday": 0}
    # 当日が祝日なら連休中なのでフラグなし
    if _jpholiday.is_holiday(dt):
        return _ZERO
    # 過去30日を遡り、直近の「3日以上連続した国民の祝日」の終了日を探す
    streak = 0
    streak_end = None
    for look_back in range(1, 31):
        check = dt - timedelta(days=look_back)
        if _jpholiday.is_holiday(check):
            if streak == 0:
                streak_end = check  # 連休の最終日（一番直近の祝日）
            streak += 1
        else:
            if streak >= 3:
                # 3日以上の連休が見つかった → 今日は何日後か
                days_after = (dt - streak_end).days
                if 1 <= days_after <= 7:
                    return {
                        "is_post_long_holiday":    1,
                        "days_after_long_holiday": days_after,
                    }
                break  # 7日より古い連休は無視
            streak = 0  # 短い連休はリセット
    return _ZERO


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
    daily_last_time = defaultdict(float)  # 日付 -> 最終レジ時刻（0時からの分数）
    latest_prices = {}  # product -> (date, unit_price)

    # 自動取得CSVがあれば追加（Square APIからの日次データ）
    auto_csv = "商品-square-auto.csv"
    all_files = list(SALES_FILES)
    if auto_csv not in all_files and os.path.exists(os.path.join(DATA_DIR, auto_csv)):
        all_files.append(auto_csv)

    for filename in all_files:
        path = os.path.join(DATA_DIR, filename)
        # 自動取得CSVはUTF-8・カンマ区切り、既存CSVはUTF-16・タブ区切り
        is_auto = filename == auto_csv
        encoding = "utf-8" if is_auto else "utf-16"
        delimiter = "," if is_auto else "\t"
        with open(path, encoding=encoding) as f:
            reader = csv.DictReader(f, delimiter=delimiter)
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

                # 最終レジ時刻を記録（最大値を保持）
                time_str = row.get("時間", "").strip()
                if time_str:
                    try:
                        h, m, s = time_str.split(":")
                        t_min = int(h) * 60 + int(m) + int(s) / 60
                        if t_min > daily_last_time[dt]:
                            daily_last_time[dt] = t_min
                    except ValueError:
                        pass

                # 最新単価を記録（日付が新しいものを優先）
                if qty > 0 and amount > 0:
                    unit_price = amount / qty
                    if product not in latest_prices or dt > latest_prices[product][0]:
                        latest_prices[product] = (dt, unit_price)

    # 日付情報を除いて単価だけのdictに変換
    latest_unit_prices = {p: price for p, (_, price) in latest_prices.items()}
    return daily_sales, daily_products, daily_last_time, latest_unit_prices


def build_dataset():
    print("休業日セットを構築中...")
    school_set, waseda_set = build_holiday_sets()

    print("天候データを読み込み中...")
    weather = load_weather()

    print("売上データを読み込み中...")
    daily_sales, daily_products, daily_last_time, latest_unit_prices = load_sales()

    # 前日の最終レジ時刻を引けるよう日付リストを準備
    DEFAULT_CLOSE = 17 * 60  # デフォルト：17時（1020分）
    dates_sorted = sorted(daily_sales.keys())
    prev_close_map = {}
    for i, dt_str in enumerate(dates_sorted):
        if i == 0:
            prev_close_map[dt_str] = DEFAULT_CLOSE
        else:
            prev_dt = dates_sorted[i - 1]
            d_curr = date.fromisoformat(dt_str)
            d_prev = date.fromisoformat(prev_dt)
            # 前営業日が3日以内なら使用（週末・祝日を挟む場合も対応）
            if (d_curr - d_prev).days <= 3:
                prev_close_map[dt_str] = daily_last_time.get(prev_dt, DEFAULT_CLOSE)
            else:
                prev_close_map[dt_str] = DEFAULT_CLOSE

    # ── ラグ特徴量の事前計算 ────────────────────────────────────
    # 7日・28日・365日前の売上と移動平均・前年比・勢いを算出
    # 成長・衰退どちらのトレンドも自然に反映される
    sales_map = dict(zip(dates_sorted, [daily_sales[d] for d in dates_sorted]))

    def lookup_sales_near(dt_str, offset_days, window=3):
        """offset_days前後window日以内で最も近い営業日の売上を返す。
        7/28日ラグは同曜日フォールバックあり。"""
        target = date.fromisoformat(dt_str) - timedelta(days=offset_days)
        for delta in range(window + 1):
            for sign in [0, 1, -1]:
                cand = (target + timedelta(days=delta * sign)).isoformat()
                if cand in sales_map:
                    return sales_map[cand]
        if offset_days % 7 == 0:
            for extra_weeks in range(1, 5):
                cand = (target - timedelta(weeks=extra_weeks)).isoformat()
                if cand in sales_map:
                    return sales_map[cand]
        return None

    def moving_avg(dt_str, days):
        """直近days日の移動平均"""
        d0 = date.fromisoformat(dt_str)
        vals = [sales_map[d] for i in range(1, days + 1)
                if (d := (d0 - timedelta(days=i)).isoformat()) in sales_map]
        return sum(vals) / len(vals) if vals else None

    lag_features_map = {}
    BASELINE_SALES = 70000  # 特徴量がない場合のデフォルト（全期間平均）

    for dt_str in dates_sorted:
        s7   = lookup_sales_near(dt_str, 7)    # 先週同曜日
        s28  = lookup_sales_near(dt_str, 28)   # 4週前
        s365 = lookup_sales_near(dt_str, 365)  # 昨年同日
        ma7  = moving_avg(dt_str, 7)           # 直近7日移動平均
        ma28 = moving_avg(dt_str, 28)          # 直近28日移動平均

        # 前年比（成長 > 1.0、衰退 < 1.0）
        yoy = (ma28 / s365) if (s365 and s365 > 0 and ma28) else 1.0
        yoy = max(0.5, min(2.0, yoy))  # 極端な値をクリップ

        # 直近の勢い（加速 > 1.0、減速 < 1.0）
        momentum = (ma7 / ma28) if (ma7 and ma28 and ma28 > 0) else 1.0
        momentum = max(0.5, min(2.0, momentum))

        lag_features_map[dt_str] = {
            "sales_lag_7":   s7   if s7   is not None else BASELINE_SALES,
            "sales_lag_28":  s28  if s28  is not None else BASELINE_SALES,
            "sales_lag_365": s365 if s365 is not None else BASELINE_SALES,
            "sales_ma7":     ma7  if ma7  is not None else BASELINE_SALES,
            "sales_ma28":    ma28 if ma28 is not None else BASELINE_SALES,
            "yoy_ratio":     yoy,      # 前年比トレンド
            "momentum":      momentum, # 直近の勢い（加速/減速）
        }

    # 需要補正データを読み込む（早期売切による打ち切りデータの補正）
    corrections_path = os.path.join(DATA_DIR, "demand_corrections.pkl")
    if os.path.exists(corrections_path):
        with open(corrections_path, "rb") as f:
            demand_corrections = pickle.load(f)
        print(f"需要補正データ読み込み: {len(demand_corrections)}件")
    else:
        demand_corrections = {}

    print("データセットを結合中...")
    records = []
    for dt_str in dates_sorted:
        d = date.fromisoformat(dt_str)
        w = weather.get(dt_str, {})

        record = {
            "date": dt_str,
            "year": d.year,
            "month": d.month,
            "day": d.day,
            "weekday": d.weekday(),          # 0=月, 6=日
            "week_of_year": d.isocalendar()[1],  # 年間何週目か（1〜52）
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
            # 前日の最終レジ時刻（分）：売れ行きの勢いを表す指標
            "prev_close_min": prev_close_map.get(dt_str, DEFAULT_CLOSE),
            "total_sales": daily_sales[dt_str],
            # ラグ特徴量（トレンド・前年比・勢い）
            **lag_features_map[dt_str],
            **sakura_features(d),
            **tsuyu_features(d),
            **heat_features(w.get("temp_max", 20)),
            **post_holiday_features(d),
        }

        for product, qty in daily_products[dt_str].items():
            # 早期売切日は補正済み需要量を使用（実売数は打ち切られているため）
            corrected = demand_corrections.get((dt_str, product))
            record[f"qty_{product}"] = corrected if corrected and corrected > qty else qty

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
