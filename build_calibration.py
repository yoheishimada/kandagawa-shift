"""
build_calibration.py  ―  MLモデルと実績を照合してキャリブレーション係数を計算

月1回の更新作業（parse_sheets.py の直後に実行）：
    python3 build_calibration.py

sheet_actuals.pkl（スプレッドシート実績）と
models.pkl（MLモデル）、dataset.pkl（学習データ）を使って、
商品ごとの「MLモデルのバイアス比率（ml_vs_actual_ratio）」を計算し
calibration.pkl として保存します。

calibration.pkl の用途：
  - app.py がこのファイルを読み込み、ML予測値を実績に近づけるよう補正する
    qty_corrected = qty_predicted / ml_vs_actual_ratio
  - 実績分析レポート（売切率・ロス率・推奨）の元データとしても使用
"""

import os
import pickle
import numpy as np
from datetime import date

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# ── make_features と同じ特徴量生成ロジックを共有 ─────────────────────
# （app.py / train.py と一致させること）
import sys
sys.path.insert(0, DATA_DIR)

# app.py の関数群をインポート（特徴量生成は同一でなければならない）
# ただし Streamlit は不要なので、必要な部分だけ自前で定義する。
from datetime import timedelta
import jpholiday as _jpholiday
import math

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

SAKURA_DATES = {
    2022: {"kaika": date(2022, 3, 20), "mankai": date(2022, 3, 27)},
    2023: {"kaika": date(2023, 3, 14), "mankai": date(2023, 3, 22)},
    2024: {"kaika": date(2024, 3, 29), "mankai": date(2024, 4,  5)},
    2025: {"kaika": date(2025, 3, 25), "mankai": date(2025, 4,  2)},
    2026: {"kaika": date(2026, 3, 26), "mankai": date(2026, 4,  3)},
}

TSUYU_DATES = {
    2022: {"iri": date(2022, 6,  6), "ake": date(2022, 7, 23)},
    2023: {"iri": date(2023, 6,  8), "ake": date(2023, 7, 22)},
    2024: {"iri": date(2024, 6, 21), "ake": date(2024, 7, 18)},
    2025: {"iri": date(2025, 6, 10), "ake": date(2025, 7, 20)},
    2026: {"iri": date(2026, 6, 10), "ake": date(2026, 7, 20)},
}


def in_period(dt_str, periods):
    return any(s <= dt_str <= e for s, e in periods)


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


_LAG_BASELINE = 70000
_LAG_DEFAULTS = {
    "sales_lag_7": _LAG_BASELINE, "sales_lag_28": _LAG_BASELINE,
    "sales_lag_365": _LAG_BASELINE, "sales_ma7": _LAG_BASELINE,
    "sales_ma28": _LAG_BASELINE, "yoy_ratio": 1.0, "momentum": 1.0,
}


def post_holiday_features(dt: date) -> dict:
    _ZERO = {"is_post_long_holiday": 0, "days_after_long_holiday": 0}
    if _jpholiday.is_holiday(dt):
        return _ZERO
    streak = 0
    streak_end = None
    for look_back in range(1, 31):
        check = dt - timedelta(days=look_back)
        if _jpholiday.is_holiday(check):
            if streak == 0:
                streak_end = check
            streak += 1
        else:
            if streak >= 3:
                days_after = (dt - streak_end).days
                if 1 <= days_after <= 7:
                    return {"is_post_long_holiday": 1, "days_after_long_holiday": days_after}
                break
            streak = 0
    return _ZERO


def make_features(dt_str: str, weather: dict, sales_map: dict = None) -> list:
    """app.py の make_features() と完全に一致させること（特徴量の数・順序）"""
    d = date.fromisoformat(dt_str)
    w = weather.get(dt_str, {})
    m, wd = d.month, d.weekday()
    woy = d.isocalendar()[1]
    sk = sakura_features(d)
    ts = tsuyu_features(d)
    ht = heat_features(w.get("temp_max", 20))
    ph = post_holiday_features(d)
    # ラグ特徴量（sales_mapがあれば計算、なければデフォルト値）
    lf = _LAG_DEFAULTS.copy()
    if sales_map:
        base_wd = d.weekday()
        def lookup(offset):
            target = d - timedelta(days=offset)
            if offset % 7 == 0:
                for w_ in range(7):
                    cand = (target - timedelta(weeks=w_))
                    if cand.isoformat() in sales_map and cand.weekday() == base_wd:
                        return sales_map[cand.isoformat()]
            for delta in range(4):
                for sign in [0, 1, -1]:
                    cand = (target + timedelta(days=delta*sign)).isoformat()
                    if cand in sales_map:
                        return sales_map[cand]
            return None
        def ma(days):
            vals = [sales_map[k] for i in range(1, days+1)
                    if (k := (d - timedelta(days=i)).isoformat()) in sales_map]
            return sum(vals)/len(vals) if vals else None
        s7, s28, s365 = lookup(7), lookup(28), lookup(365)
        ma7, ma28 = ma(7), ma(28)
        yoy = max(0.5, min(2.0, ma28/s365)) if (s365 and s365 > 0 and ma28) else 1.0
        mom = max(0.5, min(2.0, ma7/ma28))  if (ma7  and ma28 and ma28 > 0) else 1.0
        lf = {
            "sales_lag_7":   s7   if s7   else _LAG_BASELINE,
            "sales_lag_28":  s28  if s28  else _LAG_BASELINE,
            "sales_lag_365": s365 if s365 else _LAG_BASELINE,
            "sales_ma7":     ma7  if ma7  else _LAG_BASELINE,
            "sales_ma28":    ma28 if ma28 else _LAG_BASELINE,
            "yoy_ratio": yoy, "momentum": mom,
        }
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
        1020,  # prev_close_min（キャリブレーション時はデフォルト値）
        lf["sales_lag_7"], lf["sales_lag_28"], lf["sales_lag_365"],
        lf["sales_ma7"], lf["sales_ma28"],
        lf["yoy_ratio"], lf["momentum"],
        ph["is_post_long_holiday"], ph["days_after_long_holiday"],
        np.sin(2*np.pi*m/12), np.cos(2*np.pi*m/12),
        np.sin(2*np.pi*wd/7), np.cos(2*np.pi*wd/7),
        np.sin(2*np.pi*woy/52), np.cos(2*np.pi*woy/52),
    ]


# ── 商品名マッチング（app.py の find_calib_for_pos と対称） ────────────
def find_pos_products_for_sheet(sheet_name: str, pos_products: list[str]) -> list[str]:
    """スプレッドシート商品名に対応するPOS商品名を返す

    優先1: 完全一致
    優先2: sheet_name が pos_name の部分文字列（山食 → 山食1斤）
    優先3: pos_name が sheet_name の部分文字列（フォールバック）
    """
    # 優先1: 完全一致
    if sheet_name in pos_products:
        return [sheet_name]

    # 優先2: sheet_name が pos_name の部分文字列（例: "山食" in "山食1斤"）
    primary = [p for p in pos_products if sheet_name in p and p != sheet_name]
    if primary:
        return primary

    # 優先3: pos_name が sheet_name の部分文字列（例: "バゲット" in "バゲットサンド"）
    # ※ この方向のマッチは曖昧になりがちなので最短一致のみ返す
    secondary = [p for p in pos_products if p in sheet_name]
    if secondary:
        return [min(secondary, key=len)]

    return []


# ── weather辞書をdataset.pklから再構築 ────────────────────────────────
def build_weather_from_dataset(records: list) -> dict:
    """dataset.pkl の records から weather 辞書を復元"""
    weather_keys = [
        "temp_max", "temp_min", "temp_mean", "sunshine_sec", "wind_max", "weather_code",
        "rain_lunch_total", "rain_lunch_max", "rain_lunch_heavy",
        "rain_evening_total", "rain_evening_max", "rain_evening_heavy",
        "rain_morning", "is_rainy_lunch", "is_rainy_evening",
    ]
    weather = {}
    for r in records:
        dt = r["date"]
        weather[dt] = {k: r.get(k, 0) for k in weather_keys}
    return weather


def main():
    print("=== build_calibration.py ===")

    # ── データ読み込み ────────────────────────────────────────────
    print("[1/4] sheet_actuals.pkl を読み込み中...")
    actuals_path = os.path.join(DATA_DIR, "sheet_actuals.pkl")
    if not os.path.exists(actuals_path):
        print("❌ sheet_actuals.pkl が見つかりません。先に parse_sheets.py を実行してください。")
        raise SystemExit(1)
    with open(actuals_path, "rb") as f:
        sheet_actuals = pickle.load(f)
    print(f"  {len(sheet_actuals)} 商品のスプレッドシート実績を読み込みました")

    print("[2/4] dataset.pkl を読み込み中...")
    dataset_path = os.path.join(DATA_DIR, "dataset.pkl")
    with open(dataset_path, "rb") as f:
        dataset = pickle.load(f)
    records = dataset["records"]
    pos_products_all = dataset["products"]  # 全POS商品名リスト
    weather = build_weather_from_dataset(records)
    sales_map = {r["date"]: r["total_sales"] for r in records if "total_sales" in r}
    print(f"  {len(records)} 日分のデータ、{len(pos_products_all)} 商品")

    print("[3/4] models.pkl を読み込み中...")
    models_path = os.path.join(DATA_DIR, "models.pkl")
    with open(models_path, "rb") as f:
        models = pickle.load(f)
    product_models = models.get("product_models", {})
    print(f"  {len(product_models)} 商品モデルを読み込みました")

    # ── 照合処理 ─────────────────────────────────────────────────
    print("[4/4] 実績とMLを照合中...")
    calibration = {}
    n_matched = 0
    n_no_match = 0

    for sheet_name, daily_actuals in sheet_actuals.items():
        # このsheet商品に対応するPOS商品名を特定
        matched_pos = find_pos_products_for_sheet(sheet_name, pos_products_all)

        # スプレッドシートの統計量を計算（全期間）
        today_str = date.today().isoformat()
        past = {dt: v for dt, v in daily_actuals.items() if dt < today_str}

        n_days      = len(past)
        n_sellout   = sum(1 for v in past.values() if v.get("売切時間"))
        n_loss      = sum(1 for v in past.values() if v.get("ロス数量", 0) > 0)
        total_seizo = sum(v.get("製造数", 0)    for v in past.values())
        total_loss_qty = sum(v.get("ロス数量", 0) for v in past.values())
        total_loss_yen = sum(v.get("ロス金額", 0) for v in past.values())
        avg_loss_pct = (total_loss_qty / total_seizo * 100) if total_seizo > 0 else 0
        sellout_rate = n_sellout / n_days if n_days > 0 else 0
        loss_rate    = n_loss    / n_days if n_days > 0 else 0

        # ML vs 実績比率の計算
        ml_vs_actual_ratio = None
        ml_mae             = None
        n_compared         = 0

        # 照合可能なPOS商品モデルがある場合
        pos_models_found = [p for p in matched_pos if p in product_models]

        if pos_models_found and past:
            sum_ml     = 0.0
            sum_actual = 0.0
            ae_list    = []

            for dt_str, actual_info in past.items():
                actual_jitsu = actual_info.get("実売数", 0)
                if actual_jitsu <= 0:
                    continue

                # 当日の全POSモデルの予測値を合算（複数SKUを1シート商品へ集約）
                X = np.array([make_features(dt_str, weather, sales_map)])
                ml_total = 0.0
                for pos_name in pos_models_found:
                    try:
                        pred = max(0.0, product_models[pos_name].predict(X)[0])
                        ml_total += pred
                    except Exception:
                        continue

                if ml_total >= 0:
                    sum_ml     += ml_total
                    sum_actual += actual_jitsu
                    ae_list.append(abs(ml_total - actual_jitsu))
                    n_compared += 1

            if sum_actual > 0 and n_compared >= 3:
                ml_vs_actual_ratio = sum_ml / sum_actual   # 1.0に近いほど良い
                ml_mae = float(np.mean(ae_list)) if ae_list else None
                n_matched += 1
            else:
                n_no_match += 1
        else:
            n_no_match += 1

        calibration[sheet_name] = {
            "n_days":           n_days,
            "n_sellout":        n_sellout,
            "n_loss":           n_loss,
            "avg_loss_pct":     avg_loss_pct,
            "sellout_rate":     sellout_rate,
            "loss_rate":        loss_rate,
            "total_seizo":      total_seizo,
            "total_loss_qty":   total_loss_qty,
            "total_loss_yen":   total_loss_yen,
            "n_compared":       n_compared,
            "ml_vs_actual_ratio": ml_vs_actual_ratio,
            "ml_mae":           ml_mae,
            "pos_products":     matched_pos,
        }

    # ── 保存 ──────────────────────────────────────────────────────
    out_path = os.path.join(DATA_DIR, "calibration.pkl")
    with open(out_path, "wb") as f:
        pickle.dump(calibration, f)

    # ── サマリー表示 ──────────────────────────────────────────────
    has_ratio = [v for v in calibration.values() if v["ml_vs_actual_ratio"] is not None]
    ratios = [v["ml_vs_actual_ratio"] for v in has_ratio]

    print(f"\n✅ calibration.pkl 保存完了: {out_path}")
    print(f"  総商品数:       {len(calibration)}")
    print(f"  ML比率算出済み: {len(has_ratio)} 商品")
    print(f"  ML比率なし:     {n_no_match} 商品 (POSデータ不一致 or データ不足)")
    if ratios:
        print(f"  ML比率 平均: {np.mean(ratios):.3f}  中央値: {np.median(ratios):.3f}")
        good  = sum(1 for r in ratios if 0.85 <= r <= 1.15)
        ok    = sum(1 for r in ratios if (0.7 <= r < 0.85) or (1.15 < r <= 1.3))
        bad   = sum(1 for r in ratios if r < 0.7 or r > 1.3)
        print(f"  🟢 良好 (0.85〜1.15): {good}  🟠 中程度: {ok}  🔴 大バイアス: {bad}")
    print("\nアプリを再起動すると新しいキャリブレーションが反映されます。")
    print("（ターミナルで Ctrl+C → streamlit run app.py）")


if __name__ == "__main__":
    main()
