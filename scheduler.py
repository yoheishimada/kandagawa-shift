"""
バックグラウンド日次更新スケジューラー
- 毎日 02:00 (JST) に daily_update.py を実行
- startCommand から & で並列起動される
- PIDファイルで多重起動を防止
"""
import os
import sys
import time
import subprocess
from datetime import datetime, timezone, timedelta

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE   = os.path.join(DATA_DIR, ".scheduler_pid")
STAMP_FILE = os.path.join(DATA_DIR, ".last_update_date")
JST = timezone(timedelta(hours=9))
RUN_HOUR = 2   # 毎日 02:00 JST に実行


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


def run_update():
    print(f"[scheduler] daily_update.py 開始", flush=True)
    result = subprocess.run(
        [sys.executable, os.path.join(DATA_DIR, "daily_update.py")],
        capture_output=False,
    )
    print(f"[scheduler] daily_update.py 終了 (rc={result.returncode})", flush=True)
    return result.returncode == 0


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

            if now.hour >= RUN_HOUR and last_run_date() != today:
                ok = run_update()
                if ok:
                    stamp_today(today)

            # 30分ごとにチェック
            time.sleep(1800)
    finally:
        try:
            os.remove(PID_FILE)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
