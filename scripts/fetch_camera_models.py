"""Fetch optional evaluation weights from a pinned, licensed OpenCV Zoo commit."""

import argparse
import hashlib
import json
import os
import tempfile
import urllib.request
from pathlib import Path

COMMIT = "48b10fa505aeb51fbd127fc60a5c660040e823b7"
ROOT = f"https://media.githubusercontent.com/media/opencv/opencv_zoo/{COMMIT}/models/"
RAW = f"https://raw.githubusercontent.com/opencv/opencv_zoo/{COMMIT}/models/"
MODELS = [
    (
        "face_detection_yunet",
        "face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
        232589,
        "MIT",
    ),
    (
        "face_recognition_sface",
        "face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
        38696353,
        "Apache-2.0",
    ),
]
FIXTURE = (
    "face_recognition_sface",
    "example_outputs/demo.jpg",
    "0f879881a598fea6fec74e047e6a1d00e36d81de63bf0ed392b628e6ab6c2fc4",
    156282,
    "Apache-2.0",
)


def fetch(url, target, *, digest=None, expected_size=None):
    if (
        target.exists()
        and digest
        and hashlib.sha256(target.read_bytes()).hexdigest() == digest
    ):
        return
    fd, temporary = tempfile.mkstemp(prefix=".camera-download-", dir=target.parent)
    try:
        with (
            os.fdopen(fd, "wb") as output,
            urllib.request.urlopen(url, timeout=45) as response,
        ):
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > (expected_size or 100_000):
                    raise RuntimeError("Unexpected download size")
                output.write(chunk)
        data = Path(temporary).read_bytes()
        if expected_size is not None and len(data) != expected_size:
            raise RuntimeError("Unexpected download size")
        if digest and hashlib.sha256(data).hexdigest() != digest:
            raise RuntimeError("Model checksum mismatch")
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--include-test-fixture", action="store_true")
    args = parser.parse_args()
    root = args.destination.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    entries = []
    for directory, filename, digest, size, license_name in MODELS + (
        [FIXTURE] if args.include_test_fixture else []
    ):
        target = root / Path(filename).name
        fetch(
            ROOT + directory + "/" + filename, target, digest=digest, expected_size=size
        )
        license_target = root / (directory + "-LICENSE.txt")
        fetch(RAW + directory + "/LICENSE", license_target)
        entries.append(
            {
                "filename": target.name,
                "sha256": digest,
                "bytes": size,
                "license": license_name,
                "license_file": license_target.name,
                "source": ROOT + directory + "/" + filename,
            }
        )
        print(f"Verified {target.name}: {size} bytes, {license_name}")
    (root / "manifest.json").write_text(
        json.dumps({"commit": COMMIT, "files": entries}, indent=2)
    )


if __name__ == "__main__":
    main()
