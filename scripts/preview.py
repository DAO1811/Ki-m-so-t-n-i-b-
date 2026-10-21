#!/usr/bin/env python3
"""Run an isolated preview inside the VS Code Dev Container; never deploy."""

import argparse
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.preview import validate_preview_environment  # noqa: E402

STATE = ROOT / ".preview"
PYTHON = ROOT / ".venv/bin/python"
PID_FILE = STATE / "server.pid"
PORT = int(os.environ.get("DHD_PREVIEW_PORT", "8000"))


def run(*args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def credentials():
    file = STATE / "credentials.json"
    if not file.exists():
        STATE.mkdir(mode=0o700, exist_ok=True)
        fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(
                {"username": "preview_admin", "password": secrets.token_urlsafe(20)},
                output,
            )
    return json.loads(file.read_text())


def setup():
    validate_preview_environment()
    if not PYTHON.exists():
        run(sys.executable, "-m", "venv", str(ROOT / ".venv"))
    run(str(PYTHON), "-m", "pip", "install", "-r", "requirements-dev.txt")
    env = dict(os.environ, DHD_PREVIEW_ADMIN_PASSWORD=credentials()["password"])
    # Settings refuse non-local databases before migrate or sample data commands.
    for args in [("migrate", "--noinput"), ("setup_roles",), ("setup_preview",)]:
        run(str(PYTHON), "manage.py", *args, env=env)
    run(str(PYTHON), "scripts/build_styles.py")


def server_pid():
    if not PID_FILE.exists():
        return None
    pid = int(PID_FILE.read_text())
    try:
        command = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except FileNotFoundError:
        return None
    if (
        str(ROOT / "scripts/preview.py").encode() not in command
        or b"serve" not in command
    ):
        return None  # Old container PID was reused; never signal unrelated processes.
    return pid


def start():
    validate_preview_environment()
    if server_pid():
        print(f"Bản thử đang chạy: http://localhost:{PORT}")
        return
    if not PYTHON.exists() or not (STATE / "credentials.json").exists():
        raise RuntimeError("Chạy python scripts/preview.py setup trước.")
    with socket.socket() as probe:
        probe.bind(("0.0.0.0", PORT))
    with (STATE / "server.log").open("a") as log:
        process = subprocess.Popen(
            [str(PYTHON), str(ROOT / "scripts/preview.py"), "serve"],
            cwd=ROOT,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    PID_FILE.write_text(str(process.pid))
    for _ in range(40):
        if process.poll() is not None:
            raise RuntimeError("Bản thử chưa khởi động được; xem .preview/server.log.")
        try:
            with urlopen(f"http://127.0.0.1:{PORT}/healthz/", timeout=1) as response:
                if response.status == 200:
                    break
        except (URLError, TimeoutError):
            pass
        time.sleep(0.25)
    else:
        raise RuntimeError(
            "Bản thử chưa sẵn sàng sau 10 giây; xem .preview/server.log."
        )
    print(f"Đã khởi động bản thử: http://localhost:{PORT}")
    print("Xem đăng nhập: Terminal → Run Task → DHD: Xem tài khoản thử")
    print(f"Log: {STATE / 'server.log'}")


def stop():
    pid = server_pid()
    if pid:
        os.killpg(pid, signal.SIGTERM)
    PID_FILE.unlink(missing_ok=True)


def serve():
    validate_preview_environment()
    process = subprocess.Popen(
        [str(PYTHON), "manage.py", "runserver", f"0.0.0.0:{PORT}"],
        cwd=ROOT,
    )
    signature = None
    try:
        while process.poll() is None:
            current = [
                (p.name, p.stat().st_mtime_ns)
                for p in sorted((ROOT / "assets/styles").glob("*.css"))
            ]
            if signature is not None and current != signature:
                run(str(PYTHON), "scripts/build_styles.py")
                print("Đã ghép CSS mới. Làm mới trình duyệt để xem.", flush=True)
            signature = current
            time.sleep(1)
    finally:
        if process.poll() is None:
            process.terminate()


def update():
    validate_preview_environment()
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True
    ).strip()
    if not branch.startswith("preview/"):
        raise RuntimeError("Chỉ cập nhật trên nhánh preview/*, không đổi main.")
    if subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).strip():
        raise RuntimeError(
            "Có code bạn đang sửa. Lưu bằng commit trên nhánh riêng trước; bản thử không tự ghi đè."
        )
    run("git", "fetch", "origin", branch)
    stop()
    run("git", "merge", "--ff-only", f"origin/{branch}")
    setup()
    start()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=["setup", "start", "stop", "serve", "update", "credentials", "status"],
    )
    args = parser.parse_args()
    validate_preview_environment()
    if args.action == "credentials":
        file = STATE / "credentials.json"
        if not file.exists():
            raise RuntimeError(
                "Chưa tạo bản thử. Chạy task setup hoặc mở lại Dev Container."
            )
        data = json.loads(file.read_text())
        print(f"Tài khoản thử: {data['username']}\nMật khẩu thử: {data['password']}")
        print("Chỉ dùng tại bản thử local, không dùng để đăng nhập phần mềm chính.")
    elif args.action == "status":
        revision = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
        print(
            f"Phiên bản code: {revision}; {'đang chạy' if server_pid() else 'đã dừng'}."
        )
    else:
        globals()[args.action]()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        sys.exit(str(exc))
