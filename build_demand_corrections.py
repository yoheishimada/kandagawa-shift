"""
打ち切りデータ（censored demand）補正スクリプト

スプレッドシートの実績（製造数・売切時刻・ロス）をもとに、
早期売切日の「真の需要」を推定し、demand_corrections.pkl に保存する。

補正式:
  ロスゼロ かつ 売切時刻 T の場合:
    adjusted_qty = seizo × (1 + (CLOSE_MIN - T) / (CLOSE_MIN - OPEN_MIN))
    ※ 最大2.0倍にキャップ

例: 閉店18:00、開店10:00、製造10個、売切14:00
  → 10 × (1 + (1080-840)/480) = 10 × 1.5 = 15個と推定
"""
import os, pickle
from collections import defaultdict

# スプレッドシート名 → POS名 の手動マッピング（fuzzyマッチで拾えないもの）
MANUAL_MAP = {
    "あんこクリームチーズ":          "あんことクリームチーズ",
    "あんこ塩パン":                  "あんこ塩ぱん",
    "そら（枝）豆とゴーダチーズのフォカッチャ": "そら豆とゴーダチーズのフォカッチャ",
    "よもぎとクリームチーズ":         "よもぎとクリームチーズのフォカッチャ",
    "カンパーニュ（180g)":           "小さなカンパーニュ",
    "カンパフレンチ（小）":           "小さなカンパーニュ",
    "カンパフレンチ（大）":           "カンパーニュ",
    "レーズン&くるみ（小）":          "小さなレーズンとくるみのカンパーニュ",
    "ハム  or  ベーコンロール":       "ハムロール",
    "3種のチーズぱん":               "3種のチーズパン",
    "ジャーマンポテトとハニーマスタードのバゲット": "ジャーマンポテト",
    "プレーンフォカッチャ":           "プレーンフォカッチャ",
    "カリカリハニートースト":         "カリカリハニー",
}

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

OPEN_MIN  = 10 * 60   # 開店 10:00
CLOSE_MIN = 18 * 60   # 閉店 18:00
MAX_FACTOR = 2.0      # 補正の上限（2倍まで）
MIN_SAIKIRI = CLOSE_MIN - 2 * 60  # 補正対象：2時間以上前に売切（16:00以前）


def fuzzy_match(sheet_name, pos_names):
    """スプレッドシート商品名をPOS商品名にマッチング（優先度付き最長一致）"""
    # 優先1: 完全一致
    if sheet_name in pos_names:
        return sheet_name
    # 優先2: sheet_name が pos_name の部分文字列（短い名前が長い名前にマッチ）
    matches = [p for p in pos_names if sheet_name in p]
    if matches:
        return min(matches, key=len)  # 最短（最も近い）
    # 優先3: pos_name が sheet_name の部分文字列
    matches = [p for p in pos_names if p in sheet_name]
    if matches:
        return max(matches, key=len)  # 最長
    return None


def main():
    # sheet_actuals.pkl を読み込む
    actuals_path = os.path.join(DATA_DIR, "sheet_actuals.pkl")
    if not os.path.exists(actuals_path):
        print("sheet_actuals.pkl が見つかりません。先にスプレッドシートを解析してください。")
        return

    with open(actuals_path, "rb") as f:
        all_records = pickle.load(f)
    print(f"実績レコード数: {len(all_records)}")

    # dataset.pkl から POS 商品名リストを取得
    dataset_path = os.path.join(DATA_DIR, "dataset.pkl")
    with open(dataset_path, "rb") as f:
        dataset = pickle.load(f)
    pos_names = set(dataset["products"])

    # スプレッドシート商品名 → POS 商品名 のキャッシュ
    name_map = {}
    unmatched = set()
    for r in all_records:
        sn = r["product"]
        if sn not in name_map:
            # 手動マッピング優先
            if sn in MANUAL_MAP:
                name_map[sn] = MANUAL_MAP[sn]
            else:
                matched = fuzzy_match(sn, pos_names)
                if matched:
                    name_map[sn] = matched
                else:
                    unmatched.add(sn)

    print(f"名前マッチング: {len(name_map)}品マッチ / {len(unmatched)}品未マッチ")
    if unmatched:
        print(f"  未マッチ例: {sorted(unmatched)[:10]}")

    # 補正辞書を構築: {(date_str, pos_product): adjusted_qty}
    corrections = {}
    skipped = 0
    corrected = 0

    for r in all_records:
        saikiri = r["saikiri_min"]
        loss    = r["loss"]
        seizo   = r["seizo"]
        dt_str  = r["date"]
        sheet_p = r["product"]

        # 補正対象: ロスゼロ かつ 早期売切
        if loss != 0 or saikiri is None or saikiri >= MIN_SAIKIRI:
            skipped += 1
            continue

        pos_p = name_map.get(sheet_p)
        if pos_p is None:
            skipped += 1
            continue

        # 補正量の計算
        elapsed   = max(30, saikiri - OPEN_MIN)        # 開店〜売切（最低30分）
        remaining = CLOSE_MIN - saikiri                 # 売切〜閉店
        factor    = 1.0 + remaining / (CLOSE_MIN - OPEN_MIN)
        factor    = min(factor, MAX_FACTOR)
        adjusted  = seizo * factor

        key = (dt_str, pos_p)
        # 同一商品・同日で複数エントリある場合は大きい方を採用
        if key not in corrections or corrections[key] < adjusted:
            corrections[key] = adjusted
        corrected += 1

    print(f"補正レコード: {corrected}件 / スキップ: {skipped}件")

    # 補正の統計
    all_factors = []
    for (dt, prod), adj in corrections.items():
        orig_records = [r for r in all_records if r["date"] == dt and name_map.get(r["product"]) == prod]
        if orig_records:
            seizo = orig_records[0]["seizo"]
            if seizo > 0:
                all_factors.append(adj / seizo)

    if all_factors:
        import numpy as np
        print(f"補正倍率: 平均 {np.mean(all_factors):.2f}x  中央値 {np.median(all_factors):.2f}x  最大 {max(all_factors):.2f}x")

    # 保存
    out_path = os.path.join(DATA_DIR, "demand_corrections.pkl")
    with open(out_path, "wb") as f:
        pickle.dump(corrections, f)
    print(f"demand_corrections.pkl 保存完了: {len(corrections)}件")


if __name__ == "__main__":
    main()
