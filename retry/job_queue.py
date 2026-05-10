"""Implementation of a job queue."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from pathlib import Path


class JobQueue(BaseModel):
    """Queue of jobs.

    The jobs are indexed from 0 to N-1 where N is the number of jobs.
    """

    commands: list[str]
    succeeded_jobs: list[int]
    queued_jobs: list[int]

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
        return JobQueue.model_validate_json(json_data)

    def get_random_job(self) -> tuple[int, str] | None:
        """Gets a random job from the queue.

        Returns:
            A pair of job_index and job command.
            If the queue is empty, returns None.
        """
        if not self.queued_jobs:
            return None
        job_index: int = random.choice(self.queued_jobs)
        command = self.commands[job_index]
        return job_index, command

    def mark_job_as_succeeded(self, job_index: int) -> None:
        """Marks a job as succeeded.

        Args:
            job_index: The index of the job. A number between 0 and N-1 where N
                is the number of jobs.
        """
        self.succeeded_jobs.append(job_index)
        self.queued_jobs.remove(job_index)
