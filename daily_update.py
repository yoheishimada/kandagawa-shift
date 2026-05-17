"""
毎晩自動実行パイプライン
1. Square APIから昨日の売上を取得・CSV追記
2. dataset.pkl を再構築
3. models.pkl を再学習
4. models.pkl.gz に圧縮

Railway の cron: 毎晩 23:30 に実行
"""
import os
import sys
import gzip
import pickle
import subprocess
from datetime import date, timedelta

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def step1_fetch():
    """直近7日間の欠落日を自動補完して取得する。
    Railwayの再デプロイでCSVが消えても、翌朝には自動で埋め戻される。"""
    print("\n=== STEP 1: Square APIからデータ取得（直近7日の欠落補完）===")
    from fetch_square import run, load_existing_dates
    existing = load_existing_dates()
    yesterday = date.today() - timedelta(days=1)
    total_rows = 0
    for days_ago in range(7, 0, -1):   # 7日前 → 昨日 の順に確認
        target = yesterday - timedelta(days=days_ago - 1)
        if str(target) in existing:
            print(f"  {target}: 取得済みスキップ")
            continue
        try:
            n = run(target)
            total_rows += n
        except Exception as e:
            print(f"  {target}: 取得エラー ({e})")
    print(f"  完了: 合計{total_rows}行追記")
    return total_rows


def step2_preprocess():
    print("\n=== STEP 2: データセット再構築 ===")
    # preprocess.pyはload_sales()でCSVを読む
    # 自動取得したCSVも含めるため、SALES_FILESに追加
    import importlib.util
    spec = importlib.util.spec_from_file_location("preprocess", os.path.join(DATA_DIR, "preprocess.py"))
    pre = importlib.util.load_from_spec(spec)
    spec.loader.exec_module(pre)

    # 自動取得CSVをSALES_FILESに追加
    auto_csv = os.path.join(DATA_DIR, "商品-square-auto.csv")
    if os.path.exists(auto_csv) and auto_csv not in pre.SALES_FILES:
        pre.SALES_FILES.append("商品-square-auto.csv")

    records, latest_unit_prices = pre.build_dataset()
    products = pre.get_all_products(records)

    out_path = os.path.join(DATA_DIR, "dataset.pkl")
    with open(out_path, "wb") as f:
        pickle.dump({
            "records": records,
            "products": products,
            "latest_unit_prices": latest_unit_prices,
        }, f)
    print(f"  完了: {len(records)}日分  {len(products)}商品")
    return len(records)


def step3_train():
    print("\n=== STEP 3: モデル再学習 ===")
    result = subprocess.run(
        [sys.executable, os.path.join(DATA_DIR, "train.py")],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("エラー:", result.stderr)
        return False
    return True


def step4_compress():
    print("\n=== STEP 4: モデル圧縮 ===")
    pkl  = os.path.join(DATA_DIR, "models.pkl")
    gz   = os.path.join(DATA_DIR, "models.pkl.gz")
    with open(pkl, "rb") as f_in:
        with gzip.open(gz, "wb") as f_out:
            f_out.write(f_in.read())
    size_mb = os.path.getsize(gz) / 1024 / 1024
    print(f"  完了: models.pkl.gz ({size_mb:.1f}MB)")
    return True


def main():
    print(f"[daily_update] {date.today()} 実行開始")

    try:
        n = step1_fetch()
    except Exception as e:
        print(f"  STEP1 エラー: {e}")
        n = 0

    # 新データがなくても再学習はスキップ（毎日は重いため週次に変更可）
    # 新データがある場合のみ再学習
    if n == 0:
        print("\n新データなし。再学習をスキップします。")
        return

    try:
        step2_preprocess()
    except Exception as e:
        print(f"  STEP2 エラー: {e}")
        return

    try:
        ok = step3_train()
    except Exception as e:
        print(f"  STEP3 エラー: {e}")
        return

    if ok:
        try:
            step4_compress()
        except Exception as e:
            print(f"  STEP4 エラー: {e}")

    print(f"\n[daily_update] 完了")


if __name__ == "__main__":
    main()
