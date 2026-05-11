"""Unit tests for the JobResult class."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from retry.runner import JobResult


def _make_result(**kwargs: object) -> JobResult:
    """Creates a JobResult with sensible defaults, overridden by kwargs."""
    fields: dict[str, object] = {
        "job_index": 0,
        "num_attempts": 0,
        "command": "echo hello",
        "exit_code": 0,
        "elapsed_seconds": 1.5,
        "stdout": "hello\n",
        "stderr": "",
    }
    fields.update(kwargs)
    return JobResult(**fields)  # type: ignore[arg-type]


class TestSerialize(unittest.TestCase):
    """Tests for JobResult.serialize()."""

    def setUp(self) -> None:
        """Creates a temporary directory for testing."""
        self._tmp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self._tmp_path = Path(self._tmp_dir.name)

    def tearDown(self) -> None:
        """Removes the temporary directory."""
        self._tmp_dir.cleanup()

    def test_creates_directory_with_correct_name(self) -> None:
        """Directory name is formatted as job_{index:05d}_{attempts:05d}."""
        result = _make_result(job_index=0, num_attempts=0)
        result.serialize(self._tmp_path)
        self.assertTrue((self._tmp_path / "job_00000_00000").is_dir())

    def test_directory_name_formatting_with_nonzero_values(self) -> None:
        """Directory name is zero-padded to 5 digits for both index and attempts."""
        result = _make_result(job_index=7, num_attempts=3)
        result.serialize(self._tmp_path)
        self.assertTrue((self._tmp_path / "job_00007_00003").is_dir())

    def test_writes_stdout_file(self) -> None:
        """stdout.txt contains the captured stdout of the job."""
        result = _make_result(stdout="hello world\n")
        result.serialize(self._tmp_path)
        stdout_file = self._tmp_path / "job_00000_00000" / "stdout.txt"
        self.assertEqual(stdout_file.read_text(), "hello world\n")

    def test_writes_stderr_file(self) -> None:
        """stderr.txt contains the captured stderr of the job."""
        result = _make_result(stderr="error message\n")
        result.serialize(self._tmp_path)
        stderr_file = self._tmp_path / "job_00000_00000" / "stderr.txt"
        self.assertEqual(stderr_file.read_text(), "error message\n")

    def test_writes_valid_job_state_json(self) -> None:
        """job_state.json is valid JSON containing all JobResult fields."""
        result = _make_result(job_index=2, num_attempts=1, exit_code=1, elapsed_seconds=2.5)
        result.serialize(self._tmp_path)
        json_file = self._tmp_path / "job_00002_00001" / "job_state.json"
        data = json.loads(json_file.read_text())
        self.assertEqual(data["job_index"], 2)
        self.assertEqual(data["num_attempts"], 1)
        self.assertEqual(data["exit_code"], 1)
        self.assertAlmostEqual(data["elapsed_seconds"], 2.5, places=5)
        self.assertEqual(data["command"], "echo hello")


class TestPrint(unittest.TestCase):
    """Tests for JobResult.print()."""

    @staticmethod
    def _capture_print(result: JobResult) -> str:
        """Calls result.print() and returns what was printed to stdout."""
        buf = io.StringIO()
        with redirect_stdout(buf):
            result.print()
        return buf.getvalue()

    def test_prints_succeeded_on_exit_code_zero(self) -> None:
        """Prints 'succeeded' when exit_code is 0 and stdout contains 'State: success'."""
        result = _make_result(
            job_index=3,
            exit_code=0,
            elapsed_seconds=2.0,
            stdout="State: success\n",
        )
        output = self._capture_print(result)
        self.assertIn("succeeded", output)
        self.assertIn("3", output)

    def test_prints_failed_on_nonzero_exit_code(self) -> None:
        """Prints 'failed' when exit_code is non-zero."""
        result = _make_result(job_index=5, exit_code=1, elapsed_seconds=0.5)
        output = self._capture_print(result)
        self.assertIn("failed", output)
        self.assertIn("5", output)

    def test_elapsed_seconds_formatted_to_two_decimal_places(self) -> None:
        """Elapsed time is printed with exactly two decimal places."""
        result = _make_result(exit_code=1, elapsed_seconds=1.5)
        output = self._capture_print(result)
        self.assertIn("1.50", output)

    def test_exit_code_two_prints_failed(self) -> None:
        """Any non-zero exit code is treated as failure."""
        result = _make_result(exit_code=2, elapsed_seconds=1.0)
        output = self._capture_print(result)
        self.assertIn("failed", output)


if __name__ == "__main__":
    unittest.main()
