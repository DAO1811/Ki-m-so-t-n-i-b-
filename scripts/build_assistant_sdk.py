#!/usr/bin/env python3
"""Copy pinned browser-only runtime assets, or verify the checked-in artifacts."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DESTINATION = ROOT / "static/vendor/transformers-3.8.1"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node-modules", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    metadata = DESTINATION / "PROVENANCE.json"
    info = json.loads(metadata.read_text())
    if args.check:
        for name, expected in info["files"].items():
            path = DESTINATION / name
            if (
                path.name != name
                or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected
            ):
                parser.exit(
                    1, "Assistant artifact differs from provenance: " + name + "\n"
                )
        print("Assistant runtime assets match pinned provenance.")
        return
    if args.node_modules is None:
        parser.error(
            "--node-modules is required to rebuild; --check needs no Node dependencies"
        )
    modules = args.node_modules.resolve()
    sdk = modules / "@huggingface/transformers"
    ort = modules / "onnxruntime-web"
    if json.loads((sdk / "package.json").read_text())["version"] != info["version"]:
        parser.error("Expected @huggingface/transformers 3.8.1")
    if (
        json.loads((ort / "package.json").read_text())["version"]
        != info["onnxruntime_web_version"]
    ):
        parser.error("Unexpected ONNX Runtime version")
    for original, target in [
        ("transformers.min.js", "transformers-3.8.1.mjs"),
        ("ort-wasm-simd-threaded.jsep.mjs", "ort-wasm-simd-threaded.jsep.mjs"),
        ("ort-wasm-simd-threaded.jsep.wasm", "ort-wasm-simd-threaded.jsep.wasm"),
    ]:
        shutil.copyfile(sdk / "dist" / original, DESTINATION / target)
    shutil.copyfile(sdk / "LICENSE", DESTINATION / "TRANSFORMERS-LICENSE.txt")
    shutil.copyfile(
        modules / "@huggingface/jinja/LICENSE", DESTINATION / "JINJA-LICENSE.txt"
    )
    info["files"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(DESTINATION.iterdir())
        if p.name != "PROVENANCE.json"
    }
    metadata.write_text(json.dumps(info, indent=2) + "\n")
    print("Copied pinned browser runtime; model revision unchanged.")


if __name__ == "__main__":
    main()
