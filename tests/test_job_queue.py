"""Unit tests for the JobQueue class."""

import json
import tempfile
import unittest
from pathlib import Path

from retry.runner import JobQueue


class TestReadFromCommandsFile(unittest.TestCase):
    """Tests for JobQueue.read_from_commands_file()."""

    def setUp(self) -> None:
        """Creates temporary directory for testing."""
        self.tmp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        """Deletes temporary directory."""
        self.tmp_dir.cleanup()

    def test_three_commands(self) -> None:
        """Reads three commands and initializes all lists correctly."""
        commands_file = self.tmp_path / "commands.txt"
        commands_file.write_text("echo hello\necho world\necho foo\n", encoding="utf-8")
        job_queue = JobQueue.read_from_commands_file(commands_file)
        self.assertEqual(job_queue.commands, ["echo hello", "echo world", "echo foo"])
        self.assertEqual(job_queue.queued_jobs, [0, 1, 2])
        self.assertEqual(job_queue.running_jobs, [])
        self.assertEqual(job_queue.succeeded_jobs, [])
        self.assertEqual(job_queue.num_attempts, [0, 0, 0])

    def test_single_command(self) -> None:
        """Reads a file with one command."""
        commands_file = self.tmp_path / "commands.txt"
        commands_file.write_text("echo hello\n", encoding="utf-8")
        job_queue = JobQueue.read_from_commands_file(commands_file)
        self.assertEqual(job_queue.commands, ["echo hello"])
        self.assertEqual(job_queue.queued_jobs, [0])
        self.assertEqual(job_queue.running_jobs, [])
        self.assertEqual(job_queue.succeeded_jobs, [])
        self.assertEqual(job_queue.num_attempts, [0])

    def test_strips_whitespace_from_each_line(self) -> None:
        """Leading and trailing whitespace is stripped from each command."""
        commands_file = self.tmp_path / "commands.txt"
        commands_file.write_text("  echo hello  \n  echo world  \n", encoding="utf-8")
        job_queue = JobQueue.read_from_commands_file(commands_file)
        self.assertEqual(job_queue.commands, ["echo hello", "echo world"])


class TestWriteAndReadFromJsonFile(unittest.TestCase):
    """Tests for JobQueue.write_to_json_file() and read_from_json_file()."""

    def setUp(self) -> None:
        """Creates temporary directory for testing."""
        self.tmp_dir = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        """Deletes temporary directory."""
        self.tmp_dir.cleanup()

    def test_round_trip_preserves_state(self) -> None:
        """Serializing and deserializing produces an equivalent queue."""
        original = JobQueue(
            commands=["echo hello", "echo world"],
            succeeded_jobs=[1],
            queued_jobs=[0],
            running_jobs=[],
            num_attempts=[0, 1],
        )
        json_file = self.tmp_path / "queue.json"
        original.write_to_json_file(json_file)
        loaded = JobQueue.read_from_json_file(json_file)
        self.assertEqual(loaded.commands, original.commands)
        self.assertEqual(loaded.queued_jobs, original.queued_jobs)
        self.assertEqual(loaded.running_jobs, [])
        self.assertEqual(loaded.succeeded_jobs, original.succeeded_jobs)
        self.assertEqual(loaded.num_attempts, original.num_attempts)

    def test_running_jobs_moved_to_queued_on_read(self) -> None:
        """Reading from JSON moves running jobs back into the queue."""
        job_queue = JobQueue(
            commands=["echo a", "echo b", "echo c"],
            succeeded_jobs=[],
            queued_jobs=[0],
            running_jobs=[1, 2],
            num_attempts=[0, 0, 0],
        )
        json_file = self.tmp_path / "queue.json"
        job_queue.write_to_json_file(json_file)
        loaded = JobQueue.read_from_json_file(json_file)
        self.assertEqual(loaded.running_jobs, [])
        self.assertIn(0, loaded.queued_jobs)
        self.assertIn(1, loaded.queued_jobs)
        self.assertIn(2, loaded.queued_jobs)

    def test_written_file_contains_valid_json(self) -> None:
        """The output file is valid JSON with the expected top-level keys."""
        job_queue = JobQueue.create_from_commands(["echo hello"])
        json_file = self.tmp_path / "queue.json"
        job_queue.write_to_json_file(json_file)
        data = json.loads(json_file.read_text(encoding="utf-8"))
        self.assertIn("commands", data)
        self.assertIn("queued_jobs", data)
        self.assertIn("running_jobs", data)
        self.assertIn("succeeded_jobs", data)
        self.assertIn("num_attempts", data)


class TestGetRandomJob(unittest.TestCase):
    """Tests for JobQueue.get_random_job()."""

    def test_returns_valid_job_index_and_command(self) -> None:
        """Returns a job index in range and its corresponding command."""
        job_queue = JobQueue.create_from_commands(["echo hello", "echo world"])
        job_index, num_attempts, command = job_queue.get_random_job()
        self.assertIn(job_index, [0, 1])
        self.assertEqual(num_attempts, 0)
        self.assertEqual(command, job_queue.commands[job_index])

    def test_moves_job_from_queued_to_running(self) -> None:
        """The selected job leaves queued_jobs and enters running_jobs."""
        job_queue = JobQueue.create_from_commands(["echo hello"])
        job_index, _, _ = job_queue.get_random_job()
        self.assertNotIn(job_index, job_queue.queued_jobs)
        self.assertIn(job_index, job_queue.running_jobs)

    def test_returns_current_num_attempts(self) -> None:
        """Returns the attempt count before it is incremented."""
        job_queue = JobQueue(
            commands=["echo hello"],
            succeeded_jobs=[],
            queued_jobs=[0],
            running_jobs=[],
            num_attempts=[3],
        )
        _, num_attempts, _ = job_queue.get_random_job()
        self.assertEqual(num_attempts, 3)

    def test_raises_value_error_when_queue_is_empty(self) -> None:
        """Raises ValueError when called on an empty queue."""
        job_queue = JobQueue(
            commands=["echo hello"],
            succeeded_jobs=[0],
            queued_jobs=[],
            running_jobs=[],
            num_attempts=[1],
        )
        with self.assertRaises(ValueError):
            job_queue.get_random_job()

    def test_queue_becomes_empty_after_all_jobs_dequeued(self) -> None:
        """is_empty returns True after all jobs have been pulled."""
        job_queue = JobQueue.create_from_commands(["echo hello"])
        job_queue.get_random_job()
        self.assertTrue(job_queue.is_empty())


class TestMarkJobAsSucceeded(unittest.TestCase):
    """Tests for JobQueue.mark_job_as_succeeded()."""

    def test_moves_job_to_succeeded(self) -> None:
        """The job appears in succeeded_jobs and not in running_jobs or queued_jobs."""
        job_queue = JobQueue.create_from_commands(["echo hello", "echo world"])
        job_index, _, _ = job_queue.get_random_job()
        job_queue.mark_job_as_succeeded(job_index)
        self.assertIn(job_index, job_queue.succeeded_jobs)
        self.assertNotIn(job_index, job_queue.running_jobs)
        self.assertNotIn(job_index, job_queue.queued_jobs)

    def test_increments_num_attempts(self) -> None:
        """num_attempts is incremented after the job succeeds."""
        job_queue = JobQueue.create_from_commands(["echo hello", "echo world"])
        job_index, _, _ = job_queue.get_random_job()
        job_queue.mark_job_as_succeeded(job_index)
        self.assertEqual(job_queue.num_attempts[job_index], 1)


class TestMarkJobAsFailed(unittest.TestCase):
    """Tests for JobQueue.mark_job_as_failed()."""

    def test_moves_job_back_to_queued(self) -> None:
        """A failed job returns to queued_jobs and leaves running_jobs."""
        job_queue = JobQueue.create_from_commands(["echo hello", "echo world"])
        job_index, _, _ = job_queue.get_random_job()
        job_queue.mark_job_as_failed(job_index)
        self.assertIn(job_index, job_queue.queued_jobs)
        self.assertNotIn(job_index, job_queue.running_jobs)

    def test_increments_num_attempts(self) -> None:
        """num_attempts is incremented after the job fails."""
        job_queue = JobQueue.create_from_commands(["echo hello", "echo world"])
        job_index, _, _ = job_queue.get_random_job()
        job_queue.mark_job_as_failed(job_index)
        self.assertEqual(job_queue.num_attempts[job_index], 1)

    def test_failed_job_can_be_retrieved_again(self) -> None:
        """A failed job can be picked again with an incremented attempt count."""
        job_queue = JobQueue.create_from_commands(["echo hello"])
        job_index, _, _ = job_queue.get_random_job()
        job_queue.mark_job_as_failed(job_index)
        job_index2, num_attempts2, command2 = job_queue.get_random_job()
        self.assertEqual(job_index2, job_index)
        self.assertEqual(num_attempts2, 1)
        self.assertEqual(command2, "echo hello")


class TestIsEmpty(unittest.TestCase):
    """Tests for JobQueue.is_empty()."""

    def test_empty_when_no_queued_jobs(self) -> None:
        """Returns True when queued_jobs is empty."""
        job_queue = JobQueue(
            commands=["echo hello"],
            succeeded_jobs=[0],
            queued_jobs=[],
            running_jobs=[],
            num_attempts=[1],
        )
        self.assertTrue(job_queue.is_empty())

    def test_not_empty_when_jobs_queued(self) -> None:
        """Returns False when there are jobs in queued_jobs."""
        job_queue = JobQueue.create_from_commands(["echo hello"])
        self.assertFalse(job_queue.is_empty())

    def test_not_empty_with_multiple_queued_jobs(self) -> None:
        """Returns False when multiple jobs are queued."""
        job_queue = JobQueue.create_from_commands(["echo a", "echo b", "echo c"])
        self.assertFalse(job_queue.is_empty())


if __name__ == "__main__":
    unittest.main()
