# Optional camera evaluation models

This evaluator extracts a 128-dimensional SFace feature on the server, from a
single face detected by YuNet. It does **not** implement evaluated presentation
attack detection (PAD), trusted capture or a banking-grade login mechanism. Pose
labels are approximate capture guidance from five landmarks, not proof of a live
person. Scores and thresholds need measurement on consented real-device samples.

Models are kept outside Git and outside the web image. The primary web dependency
file is unchanged. Run the worker with a separate Python environment; model
imports occur only inside that child process.

```sh
python -m venv .camera-venv
.camera-venv/bin/pip install -r requirements-camera-evaluation.txt
python scripts/fetch_camera_models.py --destination /private/camera-models --include-test-fixture
CAMERA_IDENTITY_MODEL_DIR=/private/camera-models .camera-venv/bin/python scripts/camera_engine_selfcheck.py --models /private/camera-models --fixture /private/camera-models/demo.jpg
```

Set `CAMERA_IDENTITY_ENGINE_PYTHON` to the absolute path of that environment's
Python and `CAMERA_IDENTITY_MODEL_DIR` to the private absolute model directory.
The adapter passes only the bounded JPEG request and a minimal environment to the
child. It does not pass database passwords, encryption keys, Drive or API tokens.
Runtime inference is offline. The adapter serializes inference on Linux and has
a 20-second timeout. No performance guarantee for Render Free or Windows 8 GB
follows from a check on this executor.

## Provenance and redistribution

All assets are pinned to the official OpenCV Zoo commit
`48b10fa505aeb51fbd127fc60a5c660040e823b7`, with SHA-256 values from its Git LFS
pointers. `fetch_camera_models.py` checks size and digest before installing files.
It downloads the model-directory license beside each model; retain those license
files and notices whenever distributing the optional models.

| Asset | SHA-256 | Bytes | License |
| --- | --- | ---: | --- |
| `face_detection_yunet_2023mar.onnx` | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` | 232589 | MIT, copyright 2020 Shiqi Yu |
| `face_recognition_sface_2021dec.onnx` | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` | 38696353 | Apache-2.0 |
| Optional SFace `example_outputs/demo.jpg` | `0f879881a598fea6fec74e047e6a1d00e36d81de63bf0ed392b628e6ab6c2fc4` | 156282 | Apache-2.0 |

The YuNet README explicitly says all files in its directory are under MIT. The
SFace README explicitly says all files in its directory are under Apache-2.0.
The repository-wide Apache license alone was not used to infer model licensing.

- [YuNet license](https://github.com/opencv/opencv_zoo/blob/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_detection_yunet/LICENSE)
- [YuNet declaration](https://github.com/opencv/opencv_zoo/blob/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_detection_yunet/README.md#license)
- [SFace license](https://github.com/opencv/opencv_zoo/blob/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_recognition_sface/LICENSE)
- [SFace declaration](https://github.com/opencv/opencv_zoo/blob/48b10fa505aeb51fbd127fc60a5c660040e823b7/models/face_recognition_sface/README.md#license)

The upstream published accuracy figures are benchmarks of its authors. They are
not measured false-accept/false-reject rates for KSNB, and do not evaluate spoof
resistance. The self-check processes licensed demo regions, verifies deterministic
normalized descriptors and refuses a blank image; it is not a real-user biometric
accuracy, identity, camera, fairness or liveness test.
