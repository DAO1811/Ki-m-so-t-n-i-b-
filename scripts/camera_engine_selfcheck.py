"""Functional model check on the licensed OpenCV example, not an accuracy/PAD test."""

import argparse
import base64
import hashlib
import json
import os
import resource
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    os.environ["CAMERA_IDENTITY_MODEL_DIR"] = str(args.models.resolve())
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import cv2
    import numpy as np

    from camera_identity.worker import CaptureError, _model_files, analyse_frames

    digest = hashlib.sha256(args.fixture.read_bytes()).hexdigest()
    if digest != "0f879881a598fea6fec74e047e6a1d00e36d81de63bf0ed392b628e6ab6c2fc4":
        raise SystemExit("Only the pinned licensed OpenCV demo fixture is accepted")
    start = time.monotonic()
    cv2.setNumThreads(1)
    image = cv2.imread(str(args.fixture))
    height, width = image.shape[:2]
    detector_path, _ = _model_files()
    detector = cv2.FaceDetectorYN.create(
        detector_path, "", (width, height), 0.85, 0.3, 5000
    )
    _, faces = detector.detect(image)
    if faces is None or len(faces) < 2:
        raise SystemExit("Licensed fixture did not produce expected face regions")
    # The montage includes tiny result thumbnails. They are deliberately below
    # this evaluator's minimum capture quality; use only full-size regions.
    usable = [face for face in faces if min(face[2], face[3]) >= 72]
    if not usable:
        raise SystemExit("Licensed fixture has no usable full-size face")
    descriptors = []
    for face in sorted(usable, key=lambda f: f[0]):
        x, y, fw, fh = face[:4]
        x0, y0 = max(0, int(x - fw * 0.22)), max(0, int(y - fh * 0.22))
        x1, y1 = min(width, int(x + fw * 1.22)), min(height, int(y + fh * 1.22))
        crop = image[y0:y1, x0:x1]
        crop = cv2.resize(crop, (max(160, crop.shape[1]), max(120, crop.shape[0])))
        ok, jpeg = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
        assert ok
        encoded = base64.b64encode(jpeg).decode()
        result = analyse_frames([encoded, encoded, encoded])
        assert result["descriptors"][0] == result["descriptors"][1]
        descriptor = result["descriptors"][0]
        assert len(descriptor) == 128 and abs(np.linalg.norm(descriptor) - 1) < 1e-6
        descriptors.append(descriptor)
    ok, montage = cv2.imencode(".jpg", image)
    assert ok
    try:
        analyse_frames([base64.b64encode(montage).decode()])
    except CaptureError as error:
        assert str(error) == "multiple_faces"
    else:
        raise AssertionError("Multiple-face image must be refused")
    ok, blank = cv2.imencode(".jpg", np.zeros((240, 320, 3), dtype=np.uint8))
    assert ok
    try:
        analyse_frames([base64.b64encode(blank).decode()])
    except CaptureError as error:
        assert str(error) == "no_face"
    else:
        raise AssertionError("No-face image must be refused")
    report = {
        "fixture": "Official OpenCV Zoo SFace demo, Apache-2.0",
        "fixture_sha256": digest,
        "face_regions_processed": len(descriptors),
        "descriptor_dimension": 128,
        "same_input_deterministic": True,
        "no_face_refused": True,
        "multiple_faces_refused": True,
        "pair_cosines": [
            [round(float(np.dot(a, b)), 6) for b in descriptors] for a in descriptors
        ],
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "process_max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "real_user_accuracy_tested": False,
        "presentation_attack_detection_tested": False,
    }
    if args.report:
        args.report.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
