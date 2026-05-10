"""Runs shell commands in parallel."""

from __future__ import annotations

import argparse
import random
import subprocess
import time
from concurrent.futures import FIRST_COMPLETED
from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait
from pathlib import Path

from pydantic import BaseModel


class JobQueue(BaseModel):
    """Queue of jobs.

    The jobs are indexed from 0 to N-1 where N is the number of jobs.
    """

    commands: list[str]
    succeeded_jobs: list[int]
    queued_jobs: list[int]
    num_attempts: list[int]

    @staticmethod
    def read_from_commands_file(file: Path) -> JobQueue:
        """Creates JobQueue object from a text file.

        Args:
            file: A path to a text file. The text file must contain one command per line.

        Returns:
            A new instance of JobQueue class.
        """
        commands = [line.strip() for line in file.read_text(encoding="utf-8").strip().splitlines()]
        return JobQueue(
            commands=commands,
            succeeded_jobs=[],
            queued_jobs=list(range(len(commands))),
            num_attempts=len(commands) * [0],
        )

    def write_to_json_file(self, file: Path) -> None:
        """Serializes the object to a JSON file.

        Args:
            file: A path to a JSON file.
        """
        json_data = self.model_dump_json(indent=4)
        file.write_text(json_data, encoding="utf-8")

    @staticmethod
    def read_from_json_file(file: Path) -> JobQueue:
        """Creates JobQueue object from a JSON file.

        Args:
            file: A path to JSON file.

        Returns:
            A new instance of JobQueue class.
        """
        json_data = file.read_text(encoding="utf-8")
        job_queue = JobQueue.model_validate_json(json_data)
        job_queue.queued_jobs = list(range(len(job_queue.commands)))
        for job_index in job_queue.succeeded_jobs:
            job_queue.queued_jobs.remove(job_index)
        return job_queue

    def get_random_job(self) -> tuple[int, int, str]:
        """Gets a random job from the queue.

        Returns:
            A tuple of job_index and job command.
            If the queue is empty, returns None.

        Raises:
            ValueError: If the queue is empty.
        """
        if not self.queued_jobs:
            raise ValueError("JobQueue is empty")
        job_index: int = random.choice(self.queued_jobs)
        self.queued_jobs.remove(job_index)
        return job_index, self.num_attempts[job_index], self.commands[job_index]

    def mark_job_as_succeeded(self, job_index: int) -> None:
        """Marks a job as succeeded.

        Args:
            job_index: The index of the job. A number between 0 and N-1 where N
                is the number of jobs.
        """
        self.succeeded_jobs.append(job_index)
        self.queued_jobs.remove(job_index)

    def mark_job_as_failed(self, job_index: int) -> None:
        """Marks a job as failed.

        Args:
            job_index: The index of the job. A number between 0 and N-1 where N
                is the number of jobs.
        """
        self.num_attempts[job_index] += 1
        self.queued_jobs.append(job_index)

    def is_empty(self) -> bool:
        """Checks if the queue is empty."""
        return not self.queued_jobs


class JobResult(BaseModel):
    """Result of running a shell command."""

    job_index: int
    num_attempts: int
    command: str
    exit_code: int
    elapsed_seconds: float
    stdout: str
    stderr: str

    def serialize(self, base_directory: Path) -> None:
        """Serializes the object to text files."""
        json_data = self.model_dump_json()
        directory = base_directory / f"job_{self.job_index:05d}_{self.num_attempts:05d}"
        directory.mkdir(parents=True, exist_ok=True)
        stdout_file = Path(directory) / "stdout.txt"
        stderr_file = Path(directory) / "stderr.txt"
        job_state_file = Path(directory) / "job_state.json"
        stdout_file.write_text(self.stdout)
        stderr_file.write_text(self.stderr)
        job_state_file.write_text(json_data)

    def print(self) -> None:
        """Prints the status of the job."""
        if self.exit_code == 0:
            print(f"Job {self.job_index} succeeded after {self.elapsed_seconds:.2f} seconds.")
        else:
            print(f"Job {self.job_index} failed after {self.elapsed_seconds:.2f} seconds.")


def run_job(job_index: int, num_attempts: int, command: str) -> JobResult:
    """Runs a shell command and captures its output.

    Args:
        job_index: The index of the job to run.
        num_attempts: The number of failures to run.
        command: The shell command to run.

    Returns:
        A CommandResult with stdout, stderr, exit code, and elapsed time.
    """
    start = time.perf_counter()
    result = subprocess.run(
        command,
        shell=True,
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = time.perf_counter() - start
    return JobResult(
        job_index=job_index,
        num_attempts=num_attempts,
        command=command,
        exit_code=result.returncode,
        elapsed_seconds=elapsed,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def run_jobs(job_queue: JobQueue, max_workers: int, base_directory: Path) -> None:
    """Runs all queued jobs on a thread pool, grabbing one job at a time.

    Jobs are submitted one at a time to keep the pool full.

    Args:
        job_queue: The job queue to run.
        max_workers: Maximum number of parallel workers.
        base_directory: The base directory where to write files.
    """
    pending: set[Future[JobResult]] = set()
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while not job_queue.is_empty():
            # Add jobs to thread pool.
            while len(pending) < max_workers and not job_queue.is_empty():
                job_index, num_attempts, command = job_queue.get_random_job()
                print(f"Starting job {job_index}, attempt {num_attempts}.")
                future = executor.submit(run_job, job_index, num_attempts, command)
                pending.add(future)

            job_queue.write_to_json_file(base_directory / "queue_state.json")

            # Get finished futures.
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                pending.remove(future)
                result = future.result()
                result.print()
                result.serialize(base_directory)
                if result.exit_code == 0:
                    job_queue.mark_job_as_succeeded(job_index)
                else:
                    job_queue.mark_job_as_failed(job_index)

            job_queue.write_to_json_file(base_directory / "queue_state.json")


def parse_arguments() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(description="Run shell commands on a thread pool.")
    parser.add_argument(
        "--max_workers",
        type=int,
        default=5,
        required=True,
        help="Maximum number of parallel workers.",
    )
    parser.add_argument(
        "--base_directory",
        type=Path,
        required=True,
        help="Base directory where to write files.",
    )
    parser.add_argument(
        "--commands",
        type=Path,
        required=True,
        help="File with commands to run.",
    )
    parser.add_argument(
        "--resume",
        type=bool,
        action="store_true",
        default=False,
        help="File with jobs to run.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point of the script."""
    parsed_args = parse_arguments()
    if parsed_args.resume:
        job_queue = JobQueue.read_from_json_file(parsed_args.base_directory / "queue_state.json")
    else:
        job_queue = JobQueue.read_from_commands_file(parsed_args.commands)
    run_jobs(
        job_queue,
        max_workers=parsed_args.max_workers,
        base_directory=parsed_args.base_directory,
    )


if __name__ == "__main__":
    main()
