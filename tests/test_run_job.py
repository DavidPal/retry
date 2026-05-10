"""Unit tests for the run_job() function."""

import unittest

from retry.runner import run_job


class TestRunJob(unittest.TestCase):
    """Tests for run_job()."""

    def test_returns_correct_job_index(self) -> None:
        """job_index in the result matches the argument."""
        result = run_job(job_index=7, num_attempts=0, command="true")
        self.assertEqual(result.job_index, 7)

    def test_returns_correct_num_attempts(self) -> None:
        """num_attempts in the result matches the argument."""
        result = run_job(job_index=0, num_attempts=3, command="true")
        self.assertEqual(result.num_attempts, 3)

    def test_returns_correct_command(self) -> None:
        """Command in the result matches the argument."""
        result = run_job(job_index=0, num_attempts=0, command="echo hello")
        self.assertEqual(result.command, "echo hello")

    def test_successful_command_has_exit_code_zero(self) -> None:
        """A command that succeeds returns exit_code 0."""
        result = run_job(job_index=0, num_attempts=0, command="true")
        self.assertEqual(result.exit_code, 0)

    def test_failing_command_has_nonzero_exit_code(self) -> None:
        """A command that fails returns a non-zero exit_code."""
        result = run_job(job_index=0, num_attempts=0, command="false")
        self.assertNotEqual(result.exit_code, 0)

    def test_captures_stdout(self) -> None:
        """Stdout from the command is captured in the result."""
        result = run_job(job_index=0, num_attempts=0, command="echo hello")
        self.assertEqual(result.stdout, "hello\n")

    def test_captures_stderr(self) -> None:
        """Stderr from the command is captured in the result."""
        result = run_job(job_index=0, num_attempts=0, command="echo error >&2")
        self.assertEqual(result.stderr, "error\n")

    def test_stdout_and_stderr_are_separate(self) -> None:
        """Stdout and stderr are captured independently."""
        result = run_job(
            job_index=0,
            num_attempts=0,
            command="echo out; echo err >&2",
        )
        self.assertEqual(result.stdout, "out\n")
        self.assertEqual(result.stderr, "err\n")

    def test_elapsed_seconds_is_positive(self) -> None:
        """elapsed_seconds is a positive number."""
        result = run_job(job_index=0, num_attempts=0, command="true")
        self.assertGreater(result.elapsed_seconds, 0)

    def test_exit_code_reflects_command_exit_status(self) -> None:
        """exit_code matches the exit status of the shell command."""
        result = run_job(job_index=0, num_attempts=0, command="exit 42")
        self.assertEqual(result.exit_code, 42)


if __name__ == "__main__":
    unittest.main()
