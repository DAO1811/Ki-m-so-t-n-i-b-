"""Offline face feature extraction. This is NOT a presentation-attack detector."""

import base64
import hashlib
import io
import json
import math
import os
import sys
import warnings
from pathlib import Path

MODEL_ID = "opencv-sface-2021dec-0ba9fbfa01b5270c-yunet-2023mar-8f2383e4dd3cfbb4"
MODELS = {
    "face_detection_yunet_2023mar.onnx": "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    "face_recognition_sface_2021dec.onnx": "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
}
MAX_INPUT = 2_100_000


class CaptureError(Exception):
    pass


def _model_files():
    root = Path(os.environ.get("CAMERA_IDENTITY_MODEL_DIR", ""))
    if not root.is_absolute():
        raise CaptureError("model_unavailable")
    paths = []
    for name, expected in MODELS.items():
        path = root / name
        if not path.is_file():
            raise CaptureError("model_unavailable")
        with path.open("rb") as model:
            digest = hashlib.file_digest(model, "sha256").hexdigest()
        if digest != expected:
            raise CaptureError("model_unavailable")
        paths.append(str(path))
    return paths


def _image(value):
    import cv2
    import numpy as np
    from PIL import Image, ImageOps

    if not isinstance(value, str) or not 1 <= len(value) <= 400_000:
        raise CaptureError("invalid_image")
    try:
        raw = base64.b64decode(value, validate=True)
        if len(raw) > 300_000 or not raw.startswith(b"\xff\xd8\xff"):
            raise ValueError()
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != "JPEG" or getattr(image, "n_frames", 1) != 1:
                    raise ValueError()
                width, height = image.size
                if (
                    not 160 <= width <= 1280
                    or not 120 <= height <= 1280
                    or width * height > 1_638_400
                ):
                    raise ValueError()
                image.load()
                rgb = np.array(ImageOps.exif_transpose(image).convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except Exception:
        raise CaptureError("invalid_image") from None


def analyse_frames(frames):
    import cv2
    import numpy as np

    if not isinstance(frames, list) or not 1 <= len(frames) <= 5:
        raise CaptureError("invalid_frames")
    cv2.setNumThreads(1)
    detector_path, recognizer_path = _model_files()
    detector = cv2.FaceDetectorYN.create(detector_path, "", (320, 320), 0.85, 0.3, 5000)
    recognizer = cv2.FaceRecognizerSF.create(recognizer_path, "")
    descriptors, quality, poses = [], [], []
    for encoded in frames:
        image = _image(encoded)
        height, width = image.shape[:2]
        detector.setInputSize((width, height))
        _, faces = detector.detect(image)
        if faces is None or len(faces) == 0:
            raise CaptureError("no_face")
        if len(faces) != 1:
            raise CaptureError("multiple_faces")
        face = faces[0]
        x, y, fw, fh = (float(v) for v in face[:4])
        if not all(math.isfinite(v) for v in face):
            raise CaptureError("invalid_image")
        if min(fw, fh) < 72 or fw * fh / (width * height) < 0.035:
            raise CaptureError("face_too_small")
        x0, y0 = max(0, int(x)), max(0, int(y))
        x1, y1 = min(width, int(x + fw)), min(height, int(y + fh))
        crop = image[y0:y1, x0:x1]
        if crop.size == 0:
            raise CaptureError("invalid_image")
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        brightness = float(gray.mean())
        sharpness = float(cv2.Laplacian(cv2.resize(gray, (112, 112)), cv2.CV_64F).var())
        if not 30 <= brightness <= 230:
            raise CaptureError("low_light")
        if sharpness < 14:
            raise CaptureError("blurry")
        aligned = recognizer.alignCrop(image, face)
        vector = recognizer.feature(aligned).reshape(-1).astype(np.float64)
        norm = float(np.linalg.norm(vector))
        if vector.size != 128 or not np.isfinite(vector).all() or norm <= 1e-9:
            raise CaptureError("invalid_image")
        vector /= norm
        eye_mid = (float(face[4]) + float(face[6])) / 2
        eye_distance = abs(float(face[6]) - float(face[4]))
        yaw = (float(face[8]) - eye_mid) / max(eye_distance, 1)
        pose = "LEFT" if yaw < -0.12 else "RIGHT" if yaw > 0.12 else "CENTER"
        descriptors.append([round(float(v), 8) for v in vector])
        quality.append(
            {
                "confidence": round(float(face[-1]), 5),
                "face_ratio": round(fw * fh / (width * height), 5),
                "brightness": round(brightness, 2),
                "sharpness": round(sharpness, 2),
            }
        )
        poses.append({"yaw": round(yaw, 5), "label": pose})
    return {
        "model_id": MODEL_ID,
        "descriptors": descriptors,
        "quality": quality,
        "poses": poses,
    }


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise CaptureError("invalid_frames")
        data = json.loads(raw)
        if not isinstance(data, dict) or set(data) != {"frames"}:
            raise CaptureError("invalid_frames")
        result = analyse_frames(data["frames"])
    except CaptureError as error:
        print(json.dumps({"error": str(error)}))
        return 1
    except Exception:
        print(json.dumps({"error": "engine_unavailable"}))
        return 1
    print(json.dumps(result, separators=(",", ":"), allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
