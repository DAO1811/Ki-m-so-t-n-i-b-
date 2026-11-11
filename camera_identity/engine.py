"""Bounded subprocess adapter; importing this module never loads face models."""

import hashlib
import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from .capacity import RUN_HEADROOM, START_HEADROOM, remaining_memory

MAX_FRAMES = 5
MAX_ENCODED_FRAME = 400_000
MODEL_ID = "opencv-sface-2021dec-0ba9fbfa01b5270c-yunet-2023mar-8f2383e4dd3cfbb4"
_local_lock = threading.Lock()


class CameraEngineError(Exception):
    def __init__(self, code="engine_unavailable"):
        self.code = code
        super().__init__(code)


def _setting(name, default=""):
    try:
        from django.conf import settings

        if settings.configured:
            return getattr(settings, name, os.environ.get(name, default))
    except ImportError:
        pass
    return os.environ.get(name, default)


def configuration_ready():
    """Read metadata only; no inference, subprocess, or database write."""
    python = Path(str(_setting("CAMERA_IDENTITY_ENGINE_PYTHON")))
    models = Path(str(_setting("CAMERA_IDENTITY_MODEL_DIR")))
    return (
        python.is_absolute()
        and python.is_file()
        and os.access(python, os.X_OK)
        and models.is_absolute()
        and all(
            (models / filename).is_file()
            for filename in (
                "face_detection_yunet_2023mar.onnx",
                "face_recognition_sface_2021dec.onnx",
            )
        )
    )


def _require_capacity(threshold):
    available = remaining_memory()
    if available is None or available < threshold:
        raise CameraEngineError("engine_capacity")


def _run(python, root, env, frames):
    _require_capacity(START_HEADROOM)
    try:
        child = subprocess.Popen(
            [python, "-m", "camera_identity.worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=root,
            env=env,
        )
    except OSError:
        raise CameraEngineError() from None
    pending_input = json.dumps({"frames": frames}, separators=(",", ":"))
    deadline = time.monotonic() + 20
    try:
        while True:
            _require_capacity(RUN_HEADROOM)
            if time.monotonic() >= deadline:
                raise CameraEngineError("engine_timeout")
            try:
                stdout, stderr = child.communicate(input=pending_input, timeout=0.05)
                return subprocess.CompletedProcess(
                    child.args, child.returncode, stdout, stderr
                )
            except subprocess.TimeoutExpired:
                pending_input = None
    finally:
        if child.poll() is None:
            child.kill()
        child.communicate()


def analyse(frames):
    """Return descriptors/quality/pose from trusted local inference, never a login."""
    if (
        not isinstance(frames, list)
        or not 1 <= len(frames) <= MAX_FRAMES
        or any(
            not isinstance(f, str) or not 1 <= len(f) <= MAX_ENCODED_FRAME
            for f in frames
        )
    ):
        raise CameraEngineError("invalid_frames")
    python = str(_setting("CAMERA_IDENTITY_ENGINE_PYTHON"))
    models = str(_setting("CAMERA_IDENTITY_MODEL_DIR"))
    if not configuration_ready():
        raise CameraEngineError("model_unavailable")
    root = Path(__file__).resolve().parent.parent
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "C.UTF-8",
        "PYTHONPATH": str(root),
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "CAMERA_IDENTITY_MODEL_DIR": models,
    }
    if not _local_lock.acquire(blocking=False):
        raise CameraEngineError("engine_busy")
    lock_fd = None
    try:
        try:
            import fcntl

            key = hashlib.sha256(str(root).encode()).hexdigest()[:16]
            flags = os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
            lock_fd = os.open(
                Path(tempfile.gettempdir()) / f"ksnb-camera-{key}.lock", flags, 0o600
            )
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except ImportError:
            pass  # A Windows development server still has the in-process lock.
        except (BlockingIOError, OSError):
            raise CameraEngineError("engine_busy") from None
        try:
            result = _run(python, root, env, frames)
        except OSError:
            raise CameraEngineError() from None
        if len(result.stdout) > 65_536:
            raise CameraEngineError()
        try:
            data = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise CameraEngineError() from None
        if not isinstance(data, dict):
            raise CameraEngineError()
        if result.returncode or "error" in data:
            allowed = {
                "invalid_frames",
                "invalid_image",
                "no_face",
                "multiple_faces",
                "face_too_small",
                "low_light",
                "blurry",
                "model_unavailable",
            }
            code = data.get("error")
            raise CameraEngineError(code if code in allowed else "engine_unavailable")
        if data.get("model_id") != MODEL_ID:
            raise CameraEngineError()
        return data
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        _local_lock.release()
