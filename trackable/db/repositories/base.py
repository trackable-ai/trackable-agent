"""
Base repository with common CRUD operations.

Provides generic database operations that can be inherited by specific repositories.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, Sequence, TypeVar
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import Table, delete, select, update
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT", bound=BaseModel)


def model_to_jsonb(model: BaseModel | None) -> dict | None:
    """Serialize Pydantic model for JSONB storage."""
    if model is None:
        return None
    return model.model_dump(mode="json")


def models_to_jsonb(models: Sequence[BaseModel]) -> list[dict]:
    """Serialize list of Pydantic models for JSONB storage."""
    return [m.model_dump(mode="json") for m in models]


def jsonb_to_model(data: dict | None, model_class: type[ModelT]) -> ModelT | None:
    """Deserialize JSONB to Pydantic model."""
    if data is None:
        return None
    return model_class.model_validate(data)


def jsonb_to_models(data: list[dict] | None, model_class: type[ModelT]) -> list[ModelT]:
    """Deserialize JSONB array to list of Pydantic models."""
    if data is None:
        return []
    return [model_class.model_validate(d) for d in data]


class BaseRepository(ABC, Generic[ModelT]):
    """
    Base repository with common CRUD operations.

    Subclasses must implement:
    - table property: Return the SQLAlchemy Table
    - _row_to_model: Convert database row to Pydantic model
    - _model_to_dict: Convert Pydantic model to database dict
    """

    def __init__(self, session: Session):
        self.session = session

    @property
    @abstractmethod
    def table(self) -> Table:
        """SQLAlchemy table for this repository."""
        pass

    @abstractmethod
    def _row_to_model(self, row: Any) -> ModelT:
        """Convert database row to Pydantic model."""
        pass

    @abstractmethod
    def _model_to_dict(self, model: ModelT) -> dict:
        """Convert Pydantic model to database dict."""
        pass

    def get_by_id(self, id: UUID | str) -> ModelT | None:
        """
        Get entity by ID.

        Args:
            id: UUID of the entity

        Returns:
            Pydantic model or None if not found
        """
        if isinstance(id, str):
            id = UUID(id)

        stmt = select(self.table).where(self.table.c.id == id)
        result = self.session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        return self._row_to_model(row)

    def create(self, model: ModelT) -> ModelT:
        """
        Create new entity.

        Args:
            model: Pydantic model to create

        Returns:
            Created model with database-generated fields
        """
        data = self._model_to_dict(model)
        stmt = self.table.insert().values(**data).returning(self.table)
        result = self.session.execute(stmt)
        row = result.fetchone()
        return self._row_to_model(row)

    def update_by_id(self, id: UUID | str, **kwargs) -> bool:
        """
        Update entity by ID with specific fields.

        Args:
            id: UUID of the entity
            **kwargs: Fields to update

        Returns:
            True if entity was updated, False if not found
        """
        if isinstance(id, str):
            id = UUID(id)

        stmt = update(self.table).where(self.table.c.id == id).values(**kwargs)
        result = self.session.execute(stmt)
        return result.rowcount > 0

    def delete_by_id(self, id: UUID | str) -> bool:
        """
        Delete entity by ID.

        Args:
            id: UUID of the entity

        Returns:
            True if entity was deleted, False if not found
        """
        if isinstance(id, str):
            id = UUID(id)

        stmt = delete(self.table).where(self.table.c.id == id)
        result = self.session.execute(stmt)
        return result.rowcount > 0
