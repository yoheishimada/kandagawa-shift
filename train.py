"""
モデル学習スクリプト
- 日次売上合計モデル（弱気/普通/強気の3分位点）
- 商品別数量モデル（普通予測のみ）
"""
import os
import pickle
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

BASE_FEATURES = [
    "year", "month", "day", "weekday",
    "is_weekend", "is_holiday",
    "is_school_holiday", "is_waseda_holiday",
    "temp_max", "temp_min", "temp_mean",
    "sunshine_sec", "wind_max", "weather_code",
    "rain_lunch_total", "rain_lunch_max", "rain_lunch_heavy",
    "rain_evening_total", "rain_evening_max", "rain_evening_heavy",
    "rain_morning", "is_rainy_lunch", "is_rainy_evening",
    # 桜特徴量
    "sakura_score", "days_from_mankai", "is_sakura_peak",
    # 梅雨特徴量
    "is_tsuyu", "days_into_tsuyu",
    # 猛暑特徴量
    "heat_excess", "is_hot_day", "is_very_hot",
]

CYCLIC_FEATURES = ["month_sin", "month_cos", "weekday_sin", "weekday_cos"]
ALL_FEATURES = BASE_FEATURES + CYCLIC_FEATURES

MIN_SALES_DAYS = 30
QUANTILES = {"bear": 0.25, "normal": 0.50, "bull": 0.75}


def make_hgb(quantile=None):
    if quantile is not None:
        return HistGradientBoostingRegressor(
            loss="quantile", quantile=quantile,
            learning_rate=0.05, max_iter=500,
            max_leaf_nodes=31, min_samples_leaf=10, random_state=42,
        )
    return HistGradientBoostingRegressor(
        loss="absolute_error",
        learning_rate=0.05, max_iter=500,
        max_leaf_nodes=31, min_samples_leaf=10, random_state=42,
    )


def add_cyclic_features(records):
    for r in records:
        r["month_sin"] = np.sin(2 * np.pi * r["month"] / 12)
        r["month_cos"] = np.cos(2 * np.pi * r["month"] / 12)
        r["weekday_sin"] = np.sin(2 * np.pi * r["weekday"] / 7)
        r["weekday_cos"] = np.cos(2 * np.pi * r["weekday"] / 7)
    return records


def records_to_xy(records, target_col):
    X, y = [], []
    for r in records:
        if target_col not in r:
            continue
        X.append([r.get(f, 0) for f in ALL_FEATURES])
        y.append(r[target_col])
    return np.array(X), np.array(y)


def train_quantile_models(X, y, label=""):
    """弱気/普通/強気の3モデルを学習"""
    models = {}
    maes = {}
    tscv = TimeSeriesSplit(n_splits=3)

    for name, q in QUANTILES.items():
        fold_maes = []
        for train_idx, val_idx in tscv.split(X):
            m = make_hgb(q)
            m.fit(X[train_idx], y[train_idx])
            fold_maes.append(mean_absolute_error(y[val_idx], m.predict(X[val_idx])))
        mae = np.mean(fold_maes)
        maes[name] = mae
        # 全データで最終学習
        m = make_hgb(q)
        m.fit(X, y)
        models[name] = m

    if label:
        print(f"  {label}: 弱気MAE=¥{maes['bear']:,.0f} / 普通MAE=¥{maes['normal']:,.0f} / 強気MAE=¥{maes['bull']:,.0f}")
    return models


def train_single_model(X, y):
    """商品別数量モデル（普通予測のみ）"""
    tscv = TimeSeriesSplit(n_splits=3)
    for train_idx, val_idx in tscv.split(X):
        m = make_hgb()
        m.fit(X[train_idx], y[train_idx])
    m = make_hgb()
    m.fit(X, y)
    return m


def main():
    path = os.path.join(DATA_DIR, "dataset.pkl")
    with open(path, "rb") as f:
        data = pickle.load(f)

    records = add_cyclic_features(data["records"])
    all_products = data["products"]
    print(f"学習データ: {len(records)}日分")

    # --- 売上合計：3分位点モデル ---
    print("\n[1] 売上合計モデルを学習中（弱気/普通/強気）...")
    X_s, y_s = records_to_xy(records, "total_sales")
    sales_models = train_quantile_models(X_s, y_s, "売上合計")

    # --- 商品別数量モデル ---
    print("\n[2] 商品別数量モデルを学習中...")
    target_products = [
        p for p in all_products
        if sum(1 for r in records if r.get(f"qty_{p}", 0) > 0) >= MIN_SALES_DAYS
    ]
    print(f"  対象: {len(target_products)}商品")

    product_models = {}
    for i, product in enumerate(target_products):
        X, y = records_to_xy(records, f"qty_{product}")
        if len(X) < 50:
            continue
        product_models[product] = train_single_model(X, y)
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(target_products)} 完了...")

    print(f"  → {len(product_models)}商品 完了")

    out_path = os.path.join(DATA_DIR, "models.pkl")
    with open(out_path, "wb") as f:
        pickle.dump({
            "sales_models": sales_models,
            "product_models": product_models,
            "features": ALL_FEATURES,
            "target_products": target_products,
        }, f)
    print(f"\nモデル保存完了: {out_path}")


if __name__ == "__main__":
    main()
