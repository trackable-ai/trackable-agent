"""
Job repository for database operations.

Handles job CRUD and status transitions.
"""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Table, select

from trackable.db.repositories.base import BaseRepository
from trackable.db.tables import jobs
from trackable.models.job import Job, JobStatus, JobType


class JobRepository(BaseRepository[Job]):
    """Repository for Job operations with status management."""

    @property
    def table(self) -> Table:
        return jobs

    def _row_to_model(self, row: Any) -> Job:
        """Convert database row to Job model."""
        return Job(
            id=str(row.id),
            user_id=str(row.user_id) if row.user_id else None,
            job_type=JobType(row.job_type),
            status=JobStatus(row.status),
            input_data=row.input_data or {},
            output_data=row.output_data or {},
            error_message=row.error_message,
            retry_count=row.retry_count or 0,
            task_name=row.task_name,
            queued_at=row.queued_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _model_to_dict(self, model: Job) -> dict:
        """Convert Job model to database dict."""
        now = datetime.now(timezone.utc)
        return {
            "id": UUID(model.id) if model.id else uuid4(),
            "user_id": UUID(model.user_id) if model.user_id else None,
            "job_type": model.job_type.value,
            "status": model.status.value,
            "input_data": model.input_data,
            "output_data": model.output_data,
            "error_message": model.error_message,
            "retry_count": model.retry_count,
            "task_name": model.task_name,
            "queued_at": model.queued_at,
            "started_at": model.started_at,
            "completed_at": model.completed_at,
            "created_at": now,
            "updated_at": now,
        }

    def get_by_task_name(self, task_name: str) -> Job | None:
        """
        Get job by Cloud Task name.

        Args:
            task_name: Cloud Task name

        Returns:
            Job or None if not found
        """
        stmt = select(self.table).where(self.table.c.task_name == task_name)
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def get_pending_jobs(
        self, user_id: str | None = None, limit: int = 100
    ) -> list[Job]:
        """
        Get jobs that are queued or processing.

        Args:
            user_id: Optional user ID filter
            limit: Maximum number of jobs to return

        Returns:
            List of pending jobs
        """
        stmt = select(self.table).where(
            self.table.c.status.in_(
                [JobStatus.QUEUED.value, JobStatus.PROCESSING.value]
            )
        )

        if user_id:
            stmt = stmt.where(self.table.c.user_id == UUID(user_id))

        stmt = stmt.order_by(self.table.c.queued_at.asc()).limit(limit)

        result = self.session.execute(stmt)
        return [self._row_to_model(row) for row in result.fetchall()]

    def mark_started(self, job_id: str | UUID) -> bool:
        """
        Mark job as started (processing).

        Args:
            job_id: Job ID

        Returns:
            True if job was updated
        """
        now = datetime.now(timezone.utc)
        return self.update_by_id(
            job_id,
            status=JobStatus.PROCESSING.value,
            started_at=now,
            updated_at=now,
        )

    def mark_completed(
        self, job_id: str | UUID, output_data: dict[str, Any] | None = None
    ) -> bool:
        """
        Mark job as completed.

        Args:
            job_id: Job ID
            output_data: Optional output data to store

        Returns:
            True if job was updated
        """
        now = datetime.now(timezone.utc)
        update_fields = {
            "status": JobStatus.COMPLETED.value,
            "completed_at": now,
            "updated_at": now,
        }

        if output_data is not None:
            update_fields["output_data"] = output_data

        return self.update_by_id(job_id, **update_fields)

    def mark_failed(self, job_id: str | UUID, error_message: str) -> bool:
        """
        Mark job as failed.

        Args:
            job_id: Job ID
            error_message: Error description

        Returns:
            True if job was updated
        """
        now = datetime.now(timezone.utc)
        return self.update_by_id(
            job_id,
            status=JobStatus.FAILED.value,
            error_message=error_message,
            completed_at=now,
            updated_at=now,
        )

    def increment_retry(self, job_id: str | UUID) -> Job | None:
        """
        Increment retry count and reset to queued status.

        Args:
            job_id: Job ID

        Returns:
            Updated Job or None if not found
        """
        job = self.get_by_id(job_id)
        if job is None:
            return None

        now = datetime.now(timezone.utc)
        self.update_by_id(
            job_id,
            status=JobStatus.QUEUED.value,
            retry_count=job.retry_count + 1,
            started_at=None,
            completed_at=None,
            error_message=None,
            updated_at=now,
        )

        return self.get_by_id(job_id)
