"""Tests for order history response models."""

from datetime import datetime, timezone

from trackable.models.order import (
    OrderHistoryResponse,
    OrderStatus,
    OrderTimelineEntry,
    SourceType,
)


class TestOrderTimelineEntry:
    def test_create_timeline_entry(self):
        now = datetime.now(timezone.utc)
        entry = OrderTimelineEntry(
            id="entry-uuid",
            status=OrderStatus.SHIPPED,
            source_type=SourceType.EMAIL,
            source_id="email-123",
            created_at=now,
            updated_at=now,
        )
        assert entry.status == OrderStatus.SHIPPED
        assert entry.source_type == SourceType.EMAIL

    def test_timeline_entry_optional_fields(self):
        now = datetime.now(timezone.utc)
        entry = OrderTimelineEntry(
            id="entry-uuid",
            status=OrderStatus.DETECTED,
            source_type=SourceType.EMAIL,
            created_at=now,
            updated_at=now,
        )
        assert entry.source_id is None
        assert entry.confidence_score is None
        assert entry.notes == []


class TestOrderHistoryResponse:
    def test_create_history_response(self):
        now = datetime.now(timezone.utc)
        entry = OrderTimelineEntry(
            id="entry-1",
            status=OrderStatus.DETECTED,
            source_type=SourceType.EMAIL,
            created_at=now,
            updated_at=now,
        )
        response = OrderHistoryResponse(
            order_number="ORD-001",
            merchant_name="TestStore",
            user_id="user-uuid",
            timeline=[entry],
        )
        assert response.order_number == "ORD-001"
        assert len(response.timeline) == 1
