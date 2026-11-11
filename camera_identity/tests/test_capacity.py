"""Resource failures must stop optional inference, never the existing web app."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from camera_identity import capacity, engine


class CapacityTests(SimpleTestCase):
    def read_files(self, files):
        def read(path, *args, **kwargs):
            if str(path) not in files:
                raise FileNotFoundError()
            return files[str(path)]

        return patch.object(Path, "read_text", read)

    def test_container_limit_takes_precedence_over_host_capacity(self):
        with self.read_files(
            {
                "/sys/fs/cgroup/memory.max": str(512 * capacity.MIB),
                "/sys/fs/cgroup/memory.current": str(400 * capacity.MIB),
                "/proc/meminfo": "MemAvailable: 10000000 kB\n",
            }
        ):
            self.assertEqual(capacity.remaining_memory(), 112 * capacity.MIB)

    def test_v1_limit_and_over_limit_usage_are_handled(self):
        with self.read_files(
            {
                "/sys/fs/cgroup/memory.max": "max",
                "/sys/fs/cgroup/memory/memory.limit_in_bytes": "500",
                "/sys/fs/cgroup/memory/memory.usage_in_bytes": "501",
            }
        ):
            self.assertEqual(capacity.remaining_memory(), 0)

    def test_no_capacity_observation_is_not_treated_as_unlimited(self):
        with self.read_files({}):
            self.assertIsNone(capacity.remaining_memory())
        with (
            patch.object(engine, "remaining_memory", return_value=None),
            patch.object(engine.subprocess, "Popen") as popen,
        ):
            with self.assertRaises(engine.CameraEngineError) as caught:
                engine._run("/python", Path("/app"), {}, [])
            self.assertEqual(caught.exception.code, "engine_capacity")
            popen.assert_not_called()

    def test_inference_is_not_started_when_memory_is_low(self):
        with (
            patch.object(engine, "remaining_memory", return_value=299 * capacity.MIB),
            patch.object(engine.subprocess, "Popen") as popen,
        ):
            with self.assertRaises(engine.CameraEngineError):
                engine._run("/python", Path("/app"), {}, [])
            popen.assert_not_called()

    def test_memory_pressure_terminates_only_inference_child(self):
        child = Mock()
        child.poll.return_value = None
        with (
            patch.object(
                engine, "remaining_memory", side_effect=[400 * capacity.MIB, 1]
            ),
            patch.object(engine.subprocess, "Popen", return_value=child),
        ):
            with self.assertRaises(engine.CameraEngineError) as caught:
                engine._run("/python", Path("/app"), {}, [])
            self.assertEqual(caught.exception.code, "engine_capacity")
        child.kill.assert_called_once()
        child.communicate.assert_called_once_with()

    def test_timed_out_inference_child_is_killed_and_reaped(self):
        child = Mock()
        child.poll.return_value = None
        with (
            patch.object(engine, "remaining_memory", return_value=400 * capacity.MIB),
            patch.object(engine.subprocess, "Popen", return_value=child),
            patch.object(engine.time, "monotonic", side_effect=[0, 21]),
        ):
            with self.assertRaises(engine.CameraEngineError) as caught:
                engine._run("/python", Path("/app"), {}, [])
            self.assertEqual(caught.exception.code, "engine_timeout")
        child.kill.assert_called_once()
        child.communicate.assert_called_once_with()

    def test_communication_retry_does_not_resend_sensitive_frames(self):
        child = Mock()
        child.args = ["/python", "-m", "camera_identity.worker"]
        child.returncode = 0
        child.poll.return_value = 0
        child.communicate.side_effect = [
            subprocess.TimeoutExpired(child.args, 0.05),
            ('{"model_id":"synthetic-test"}', ""),
            ("", ""),
        ]
        with (
            patch.object(engine, "remaining_memory", return_value=400 * capacity.MIB),
            patch.object(engine.subprocess, "Popen", return_value=child),
        ):
            result = engine._run("/python", Path("/app"), {}, ["synthetic-image"])
        self.assertEqual(result.returncode, 0)
        calls = child.communicate.call_args_list
        self.assertIn("synthetic-image", calls[0].kwargs["input"])
        self.assertIsNone(calls[1].kwargs["input"])
        child.kill.assert_not_called()
