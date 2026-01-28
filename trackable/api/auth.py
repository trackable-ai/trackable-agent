"""
Authentication dependencies for API routes.

Assumes an API gateway performs authentication and forwards
the user ID in the X-User-ID header.
"""

from uuid import UUID

from fastapi import Header, HTTPException, status

from trackable.db import DatabaseConnection, UnitOfWork


async def get_user_id(
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> str:
    """
    Extract user ID from X-User-ID header.

    The API gateway is responsible for authentication and sets this header.
    If the database is connected and the user doesn't exist, they are
    auto-created with a placeholder email.

    Args:
        x_user_id: User ID from X-User-ID header

    Returns:
        User ID string

    Raises:
        HTTPException: 401 if X-User-ID header is missing
        HTTPException: 400 if user ID is not a valid UUID format
    """
    if x_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-ID header is required",
        )

    try:
        UUID(x_user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-ID must be a valid UUID",
        )

    # Auto-create user if database is connected and user doesn't exist
    if DatabaseConnection.is_initialized():
        with UnitOfWork() as uow:
            uow.users.get_or_create(x_user_id)
            uow.commit()

    return x_user_id
