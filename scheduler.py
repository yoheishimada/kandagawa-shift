"""
バックグラウンド日次更新スケジューラー
- 毎日 02:00 (JST) に daily_update.py を実行
- 毎週日曜 02:30 (JST) に parse_sheets.py → build_calibration.py を実行
- startCommand から & で並列起動される
- PIDファイルで多重起動を防止
"""
import os
import sys
import time
import subprocess
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE        = os.path.join(DATA_DIR, ".scheduler_pid")
STAMP_FILE      = os.path.join(DATA_DIR, ".last_update_date")
CALIB_STAMP     = os.path.join(DATA_DIR, ".last_calibration_week")
JST = timezone(timedelta(hours=9))
RUN_HOUR        = 2    # 毎日 02:00 JST に daily_update 実行
CALIB_HOUR      = 2    # 毎週日曜 02:30 JST にキャリブレーション実行
CALIB_MINUTE    = 30
CALIB_WEEKDAY   = 6    # 0=月曜 … 6=日曜


def already_running():
    if not os.path.exists(PID_FILE):
        return False
    with open(PID_FILE) as f:
        pid_str = f.read().strip()
    try:
        pid = int(pid_str)
        os.kill(pid, 0)   # プロセスが生きているか確認
        return True
    except (ValueError, ProcessLookupError, PermissionError):
        return False


def write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def last_run_date():
    try:
        with open(STAMP_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def stamp_today(today_str):
    with open(STAMP_FILE, "w") as f:
        f.write(today_str)


def last_calibration_week():
    """直近のキャリブレーション実行週（ISO週番号 YYYY-WW）を返す"""
    try:
        with open(CALIB_STAMP) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def stamp_calibration_week(week_str: str):
    with open(CALIB_STAMP, "w") as f:
        f.write(week_str)


def run_update():
    print(f"[scheduler] daily_update.py 開始", flush=True)
    result = subprocess.run(
        [sys.executable, os.path.join(DATA_DIR, "daily_update.py")],
        capture_output=False,
    )
    print(f"[scheduler] daily_update.py 終了 (rc={result.returncode})", flush=True)
    return result.returncode == 0


def run_calibration():
    """parse_sheets.py → build_calibration.py を順番に実行する"""
    print("[scheduler] 週次キャリブレーション開始", flush=True)

    # Step 1: スプレッドシートから実績取得
    r1 = subprocess.run(
        [sys.executable, os.path.join(DATA_DIR, "parse_sheets.py")],
        capture_output=False,
    )
    print(f"[scheduler] parse_sheets.py 終了 (rc={r1.returncode})", flush=True)
    if r1.returncode != 0:
        print("[scheduler] parse_sheets.py が失敗したため build_calibration をスキップ", flush=True)
        return False

    # Step 2: キャリブレーション再構築
    r2 = subprocess.run(
        [sys.executable, os.path.join(DATA_DIR, "build_calibration.py")],
        capture_output=False,
    )
    print(f"[scheduler] build_calibration.py 終了 (rc={r2.returncode})", flush=True)
    return r2.returncode == 0


def main():
    if already_running():
        print("[scheduler] 既に起動中です。終了します。", flush=True)
        return

    write_pid()
    print(f"[scheduler] 起動 PID={os.getpid()}", flush=True)

    try:
        while True:
            now = datetime.now(JST)
            today = now.date().isoformat()

            # ── 日次: daily_update ──────────────────────────────────────
            if now.hour >= RUN_HOUR and last_run_date() != today:
                ok = run_update()
                if ok:
                    stamp_today(today)

            # ── 週次: キャリブレーション（日曜 02:30 以降）──────────────
            past_calib_time = (
                now.hour > CALIB_HOUR
                or (now.hour == CALIB_HOUR and now.minute >= CALIB_MINUTE)
            )
            if now.weekday() == CALIB_WEEKDAY and past_calib_time:
                iso_week = now.strftime("%Y-W%W")
                if last_calibration_week() != iso_week:
                    ok = run_calibration()
                    if ok:
                        stamp_calibration_week(iso_week)

            # 30分ごとにチェック
            time.sleep(1800)
    finally:
        try:
            os.remove(PID_FILE)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
