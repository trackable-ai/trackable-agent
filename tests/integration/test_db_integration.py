"""
Integration tests for database operations.

These tests require actual Cloud SQL connection and are marked as manual.
Run with: uv run pytest tests/integration/test_db_integration.py -v
"""

import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from dotenv import load_dotenv
from sqlalchemy import text

# Load environment variables from .env
load_dotenv()

# Skip all tests if database is not configured
pytestmark = pytest.mark.skipif(
    not os.getenv("INSTANCE_CONNECTION_NAME"),
    reason="Database not configured (INSTANCE_CONNECTION_NAME not set)",
)

# Fixed test user email for consistency across test runs
TEST_USER_EMAIL = "integration-test@trackable.test"


@pytest.fixture(scope="module")
def db_connection():
    """Initialize database connection for tests."""
    from trackable.db import DatabaseConnection

    DatabaseConnection.initialize()
    yield DatabaseConnection
    DatabaseConnection.close()


@pytest.fixture(scope="module")
def test_user(db_connection):
    """Get or create a test user for the integration tests."""
    from trackable.db import DatabaseConnection

    session = DatabaseConnection.get_session()
    try:
        # Try to find existing test user
        result = session.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": TEST_USER_EMAIL},
        )
        row = result.fetchone()

        if row:
            return str(row[0])

        # Create new test user if not found
        now = datetime.now(timezone.utc)
        user_id = str(uuid4())
        session.execute(
            text("""
                INSERT INTO users (id, email, status, created_at, updated_at)
                VALUES (:id, :email, 'active', :now, :now)
                """),
            {"id": user_id, "email": TEST_USER_EMAIL, "now": now},
        )
        session.commit()
        return user_id
    finally:
        session.close()


@pytest.fixture
def uow(db_connection):
    """Create a unit of work for each test."""
    from trackable.db import UnitOfWork

    return UnitOfWork()


class TestMerchantRepository:
    """Tests for MerchantRepository."""

    def test_create_merchant(self, uow):
        """Test creating a new merchant."""
        from trackable.models.order import Merchant

        merchant = Merchant(
            id=str(uuid4()),
            name="Test Merchant",
            domain=f"test-merchant-{uuid4().hex[:8]}.com",  # Unique domain
        )

        with uow:
            created = uow.merchants.create(merchant)
            uow.commit()

        assert created.id == merchant.id
        assert created.name == "Test Merchant"
        assert created.domain == merchant.domain

    def test_upsert_merchant_by_domain(self, uow):
        """Test upserting merchant by domain."""
        from trackable.models.order import Merchant

        domain = f"upsert-test-{uuid4().hex[:8]}.com"

        merchant1 = Merchant(
            id=str(uuid4()),
            name="Original Name",
            domain=domain,
        )

        merchant2 = Merchant(
            id=str(uuid4()),
            name="Updated Name",
            domain=domain,
            support_email="support@example.com",
        )

        with uow:
            created = uow.merchants.upsert_by_domain(merchant1)
            uow.commit()

        first_id = created.id

        # Upsert with same domain should update
        from trackable.db import UnitOfWork

        with UnitOfWork() as uow2:
            updated = uow2.merchants.upsert_by_domain(merchant2)
            uow2.commit()

        # Same ID, updated name
        assert updated.id == first_id
        assert updated.name == "Updated Name"
        assert updated.support_email == "support@example.com"

    def test_upsert_normalizes_merchant_name(self, uow):
        """Test that upsert normalizes merchant names."""
        from trackable.models.order import Merchant

        unique_suffix = uuid4().hex[:8]
        domain = f"amazon-test-{unique_suffix}.com"

        # Create merchant with uppercase name
        merchant = Merchant(
            id="",  # Let repository generate ID
            name="AMAZON",
            domain=domain,
        )

        with uow:
            created = uow.merchants.upsert_by_domain(merchant)
            uow.commit()

        # Name should be normalized to "Amazon" (known merchant)
        assert created.name == "Amazon"
        assert created.domain == domain
        # Should have aliases generated
        assert len(created.aliases) > 0
        assert "amazon" in created.aliases

    def test_upsert_normalizes_domain(self, uow):
        """Test that upsert normalizes domains (removes www prefix)."""
        from trackable.db import UnitOfWork
        from trackable.models.order import Merchant

        unique_suffix = uuid4().hex[:8]

        merchant = Merchant(
            id="",
            name="Test Store",
            domain=f"www.teststore-{unique_suffix}.com",
        )

        with uow:
            created = uow.merchants.upsert_by_domain(merchant)
            uow.commit()

        # Domain should have www. removed
        assert created.domain == f"teststore-{unique_suffix}.com"

        # Should be able to look up by normalized domain
        with UnitOfWork() as uow2:
            found = uow2.merchants.get_by_domain(f"teststore-{unique_suffix}.com")
            assert found is not None
            assert found.id == created.id

    def test_get_by_name_or_domain_finds_by_domain(self, uow):
        """Test get_by_name_or_domain finds merchant by domain."""
        from trackable.db import UnitOfWork
        from trackable.models.order import Merchant

        unique_suffix = uuid4().hex[:8]
        domain = f"findme-{unique_suffix}.com"

        merchant = Merchant(
            id="",
            name="Find Me Store",
            domain=domain,
        )

        with uow:
            created = uow.merchants.upsert_by_domain(merchant)
            uow.commit()

        # Find by domain
        with UnitOfWork() as uow2:
            found = uow2.merchants.get_by_name_or_domain(domain=domain)
            assert found is not None
            assert found.id == created.id

    def test_get_by_name_or_domain_finds_by_name(self, uow):
        """Test get_by_name_or_domain finds merchant by name (case-insensitive)."""
        from trackable.db import UnitOfWork
        from trackable.models.order import Merchant

        unique_suffix = uuid4().hex[:8]

        merchant = Merchant(
            id="",
            name=f"Unique Store {unique_suffix}",
            domain=f"uniquestore-{unique_suffix}.com",
        )

        with uow:
            created = uow.merchants.upsert_by_domain(merchant)
            uow.commit()

        # Find by name (case-insensitive)
        with UnitOfWork() as uow2:
            found = uow2.merchants.get_by_name_or_domain(
                name=f"unique store {unique_suffix}"
            )
            assert found is not None
            assert found.id == created.id

    def test_get_by_name_or_domain_finds_by_alias(self, uow):
        """Test get_by_name_or_domain finds merchant by alias."""
        from trackable.db import UnitOfWork
        from trackable.models.order import Merchant

        unique_suffix = uuid4().hex[:8]
        domain = f"mystore-{unique_suffix}.com"

        merchant = Merchant(
            id="",
            name="My Store",
            domain=domain,
        )

        with uow:
            created = uow.merchants.upsert_by_domain(merchant)
            uow.commit()

        # Aliases should include "mystore" (name without spaces)
        assert "mystore" in created.aliases

        # Find by alias
        with UnitOfWork() as uow2:
            found = uow2.merchants.get_by_name_or_domain(name="mystore")
            assert found is not None
            assert found.id == created.id


class TestJobRepository:
    """Tests for JobRepository."""

    def test_job_lifecycle(self, uow, test_user):
        """Test job status transitions."""
        from trackable.db import UnitOfWork
        from trackable.models.job import Job, JobStatus, JobType

        job_id = str(uuid4())
        now = datetime.now(timezone.utc)

        job = Job(
            id=job_id,
            user_id=test_user,
            job_type=JobType.PARSE_EMAIL,
            status=JobStatus.QUEUED,
            input_data={"test": "data"},
            queued_at=now,
            created_at=now,
            updated_at=now,
        )

        # Create job
        with uow:
            created = uow.jobs.create(job)
            uow.commit()

        assert created.status == JobStatus.QUEUED

        # Mark as started
        with UnitOfWork() as uow2:
            uow2.jobs.mark_started(job_id)
            uow2.commit()

        # Verify started
        with UnitOfWork() as uow3:
            started = uow3.jobs.get_by_id(job_id)
            assert started is not None
            assert started.status == JobStatus.PROCESSING

        # Mark as completed
        with UnitOfWork() as uow4:
            uow4.jobs.mark_completed(job_id, {"result": "success"})
            uow4.commit()

        # Verify completed
        with UnitOfWork() as uow5:
            completed = uow5.jobs.get_by_id(job_id)
            assert completed is not None
            assert completed.status == JobStatus.COMPLETED
            assert completed.output_data == {"result": "success"}


class TestSourceRepository:
    """Tests for SourceRepository."""

    def test_create_source_and_find_by_hash(self, uow, test_user):
        """Test creating source and finding by image hash."""
        from trackable.db import UnitOfWork
        from trackable.models.order import SourceType
        from trackable.models.source import Source

        image_hash = f"sha256_{uuid4().hex}"
        source_id = str(uuid4())
        now = datetime.now(timezone.utc)

        source = Source(
            id=source_id,
            user_id=test_user,
            source_type=SourceType.SCREENSHOT,
            image_hash=image_hash,
            processed=False,
            created_at=now,
            updated_at=now,
        )

        with uow:
            created = uow.sources.create(source)
            uow.commit()

        assert created.id == source_id

        # Find by hash
        with UnitOfWork() as uow2:
            found = uow2.sources.find_by_image_hash(test_user, image_hash)
            assert found is not None
            assert found.id == source_id
            assert found.image_hash == image_hash


class TestOrderRepository:
    """Tests for OrderRepository."""

    def test_create_order_with_items(self, uow, test_user):
        """Test creating order with nested items."""
        from trackable.db import UnitOfWork
        from trackable.models.order import (
            Item,
            Merchant,
            Money,
            Order,
            OrderStatus,
            SourceType,
        )

        # First create a merchant
        merchant_id = str(uuid4())
        order_id = str(uuid4())
        merchant = Merchant(
            id=merchant_id,
            name="Test Store",
            domain=f"store-{uuid4().hex[:8]}.com",
        )

        with uow:
            saved_merchant = uow.merchants.create(merchant)
            uow.commit()

        # Create order with items
        now = datetime.now(timezone.utc)

        order = Order(
            id=order_id,
            user_id=test_user,
            merchant=saved_merchant,
            order_number=f"ORD-{uuid4().hex[:8]}",
            order_date=now,
            status=OrderStatus.CONFIRMED,
            source_type=SourceType.EMAIL,
            items=[
                Item(
                    id=str(uuid4()),
                    order_id=order_id,
                    name="Test Product 1",
                    quantity=2,
                    price=Money(amount=Decimal("29.99"), currency="USD"),
                ),
                Item(
                    id=str(uuid4()),
                    order_id=order_id,
                    name="Test Product 2",
                    quantity=1,
                    price=Money(amount=Decimal("49.99"), currency="USD"),
                ),
            ],
            total=Money(amount=Decimal("109.97"), currency="USD"),
            confidence_score=0.95,
            created_at=now,
            updated_at=now,
        )

        with UnitOfWork() as uow2:
            created = uow2.orders.create(order)
            uow2.commit()

        assert created.id == order_id

        # Retrieve and verify
        with UnitOfWork() as uow3:
            retrieved = uow3.orders.get_by_id(order_id)
            assert retrieved is not None
            assert retrieved.order_number == order.order_number
            assert len(retrieved.items) == 2
            assert retrieved.items[0].name == "Test Product 1"
            assert retrieved.total is not None
            assert retrieved.total.amount == Decimal("109.97")

    def test_get_by_unique_key(self, uow, test_user):
        """Test finding order by user_id + merchant_id + order_number."""
        from trackable.db import UnitOfWork
        from trackable.models.order import (
            Merchant,
            Money,
            Order,
            OrderStatus,
            SourceType,
        )

        # Create a merchant
        merchant = Merchant(
            id=str(uuid4()),
            name="Unique Key Test Store",
            domain=f"unique-key-{uuid4().hex[:8]}.com",
        )

        with uow:
            saved_merchant = uow.merchants.create(merchant)
            uow.commit()

        # Create order
        now = datetime.now(timezone.utc)
        order_number = f"UK-{uuid4().hex[:8]}"
        order_id = str(uuid4())

        order = Order(
            id=order_id,
            user_id=test_user,
            merchant=saved_merchant,
            order_number=order_number,
            status=OrderStatus.CONFIRMED,
            source_type=SourceType.EMAIL,
            total=Money(amount=Decimal("50.00"), currency="USD"),
            created_at=now,
            updated_at=now,
        )

        with UnitOfWork() as uow2:
            uow2.orders.create(order)
            uow2.commit()

        # Find by unique key
        with UnitOfWork() as uow3:
            found = uow3.orders.get_by_unique_key(
                user_id=test_user,
                merchant_id=saved_merchant.id,
                order_number=order_number,
            )
            assert found is not None
            assert found.id == order_id
            assert found.order_number == order_number

        # Should not find with wrong merchant_id
        with UnitOfWork() as uow4:
            not_found = uow4.orders.get_by_unique_key(
                user_id=test_user,
                merchant_id=str(uuid4()),  # Wrong merchant
                order_number=order_number,
            )
            assert not_found is None

    def test_upsert_creates_new_order(self, uow, test_user):
        """Test upsert creates new order when not found."""
        from trackable.db import UnitOfWork
        from trackable.models.order import (
            Merchant,
            Money,
            Order,
            OrderStatus,
            SourceType,
        )

        # Create a merchant
        merchant = Merchant(
            id=str(uuid4()),
            name="Upsert Create Test Store",
            domain=f"upsert-create-{uuid4().hex[:8]}.com",
        )

        with uow:
            saved_merchant = uow.merchants.create(merchant)
            uow.commit()

        # Create order via upsert
        now = datetime.now(timezone.utc)
        order_number = f"UPS-NEW-{uuid4().hex[:8]}"

        order = Order(
            id=str(uuid4()),
            user_id=test_user,
            merchant=saved_merchant,
            order_number=order_number,
            status=OrderStatus.DETECTED,
            source_type=SourceType.EMAIL,
            total=Money(amount=Decimal("75.00"), currency="USD"),
            confidence_score=0.85,
            created_at=now,
            updated_at=now,
        )

        with UnitOfWork() as uow2:
            result, is_new = uow2.orders.upsert_by_order_number(order)
            uow2.commit()

        assert is_new is True
        assert result.order_number == order_number
        assert result.status == OrderStatus.DETECTED
        assert result.total is not None
        assert result.total.amount == Decimal("75.00")

    def test_upsert_updates_existing_order(self, uow, test_user):
        """Test upsert updates existing order when found."""
        from trackable.db import UnitOfWork
        from trackable.models.order import (
            Item,
            Merchant,
            Money,
            Order,
            OrderStatus,
            SourceType,
        )

        # Create a merchant
        merchant = Merchant(
            id=str(uuid4()),
            name="Upsert Update Test Store",
            domain=f"upsert-update-{uuid4().hex[:8]}.com",
        )

        with uow:
            saved_merchant = uow.merchants.create(merchant)
            uow.commit()

        # Create initial order
        now = datetime.now(timezone.utc)
        order_number = f"UPS-UPD-{uuid4().hex[:8]}"
        original_order_id = str(uuid4())

        original_order = Order(
            id=original_order_id,
            user_id=test_user,
            merchant=saved_merchant,
            order_number=order_number,
            status=OrderStatus.DETECTED,
            source_type=SourceType.EMAIL,
            total=Money(amount=Decimal("100.00"), currency="USD"),
            confidence_score=0.70,
            notes=["Original note"],
            created_at=now,
            updated_at=now,
        )

        with UnitOfWork() as uow2:
            uow2.orders.create(original_order)
            uow2.commit()

        # Upsert with updated data
        updated_order = Order(
            id=str(uuid4()),  # Different ID, but same order_number + merchant + user
            user_id=test_user,
            merchant=saved_merchant,
            order_number=order_number,
            status=OrderStatus.SHIPPED,  # Status progression
            source_type=SourceType.EMAIL,
            items=[
                Item(
                    id=str(uuid4()),
                    order_id=original_order_id,
                    name="New Item",
                    quantity=1,
                    price=Money(amount=Decimal("100.00"), currency="USD"),
                ),
            ],
            total=Money(amount=Decimal("110.00"), currency="USD"),
            confidence_score=0.90,  # Higher confidence
            notes=["Updated note"],
            created_at=now,
            updated_at=now,
        )

        with UnitOfWork() as uow3:
            result, is_new = uow3.orders.upsert_by_order_number(updated_order)
            uow3.commit()

        # New status creates a new row (order history preservation)
        assert is_new is True
        assert result.status == OrderStatus.SHIPPED

        # Verify both rows exist (original DETECTED + new SHIPPED)
        with UnitOfWork() as uow4:
            history = uow4.orders.get_order_history(
                user_id=test_user,
                merchant_id=saved_merchant.id,
                order_number=order_number,
            )
        assert len(history) == 2
        statuses = [o.status for o in history]
        assert OrderStatus.DETECTED in statuses
        assert OrderStatus.SHIPPED in statuses

    def test_upsert_same_status_merges(self, uow, test_user):
        """Test upsert with same status merges into existing row."""
        from trackable.db import UnitOfWork
        from trackable.models.order import (
            Item,
            Merchant,
            Money,
            Order,
            OrderStatus,
            SourceType,
        )

        merchant = Merchant(
            id=str(uuid4()),
            name="Same Status Merge Store",
            domain=f"same-status-{uuid4().hex[:8]}.com",
        )

        with uow:
            saved_merchant = uow.merchants.create(merchant)
            uow.commit()

        now = datetime.now(timezone.utc)
        order_number = f"MERGE-{uuid4().hex[:8]}"
        original_order_id = str(uuid4())

        original_order = Order(
            id=original_order_id,
            user_id=test_user,
            merchant=saved_merchant,
            order_number=order_number,
            status=OrderStatus.DETECTED,
            source_type=SourceType.EMAIL,
            confidence_score=0.70,
            notes=["Original note"],
            created_at=now,
            updated_at=now,
        )

        with UnitOfWork() as uow2:
            uow2.orders.create(original_order)
            uow2.commit()

        # Upsert with same status but updated data
        updated_order = Order(
            id=str(uuid4()),
            user_id=test_user,
            merchant=saved_merchant,
            order_number=order_number,
            status=OrderStatus.DETECTED,  # Same status
            source_type=SourceType.EMAIL,
            confidence_score=0.90,
            notes=["Updated note"],
            created_at=now,
            updated_at=now,
        )

        with UnitOfWork() as uow3:
            result, is_new = uow3.orders.upsert_by_order_number(updated_order)
            uow3.commit()

        assert is_new is False
        assert result.id == original_order_id  # Same row preserved
        assert result.confidence_score == 0.90  # Higher confidence used
        assert "Original note" in result.notes
        assert "Updated note" in result.notes

    def test_upsert_different_status_creates_new_row(self, uow, test_user):
        """Test upsert with different status creates a new row (order history)."""
        from trackable.db import UnitOfWork
        from trackable.models.order import (
            Merchant,
            Money,
            Order,
            OrderStatus,
            SourceType,
        )

        merchant = Merchant(
            id=str(uuid4()),
            name="Status History Test Store",
            domain=f"status-history-{uuid4().hex[:8]}.com",
        )

        with uow:
            saved_merchant = uow.merchants.create(merchant)
            uow.commit()

        now = datetime.now(timezone.utc)
        order_number = f"HIST-{uuid4().hex[:8]}"

        original_order = Order(
            id=str(uuid4()),
            user_id=test_user,
            merchant=saved_merchant,
            order_number=order_number,
            status=OrderStatus.SHIPPED,
            source_type=SourceType.EMAIL,
            total=Money(amount=Decimal("50.00"), currency="USD"),
            created_at=now,
            updated_at=now,
        )

        with UnitOfWork() as uow2:
            uow2.orders.create(original_order)
            uow2.commit()

        # Upsert with a different status (even "lower")
        new_status_order = Order(
            id=str(uuid4()),
            user_id=test_user,
            merchant=saved_merchant,
            order_number=order_number,
            status=OrderStatus.DETECTED,
            source_type=SourceType.EMAIL,
            total=Money(amount=Decimal("50.00"), currency="USD"),
            created_at=now,
            updated_at=now,
        )

        with UnitOfWork() as uow3:
            result, is_new = uow3.orders.upsert_by_order_number(new_status_order)
            uow3.commit()

        # Different status = new row
        assert is_new is True
        assert result.status == OrderStatus.DETECTED


class TestFullWorkflow:
    """Test full ingest workflow with database."""

    def test_email_ingest_workflow(self, uow, test_user):
        """Test complete email ingest workflow."""
        from trackable.db import UnitOfWork
        from trackable.models.job import Job, JobStatus, JobType
        from trackable.models.order import SourceType
        from trackable.models.source import Source

        job_id = str(uuid4())
        source_id = str(uuid4())
        now = datetime.now(timezone.utc)

        # Step 1: Create Job (like ingest API does)
        job = Job(
            id=job_id,
            user_id=test_user,
            job_type=JobType.PARSE_EMAIL,
            status=JobStatus.QUEUED,
            input_data={
                "source_id": source_id,
                "email_subject": "Your Amazon order",
                "email_from": "orders@amazon.com",
            },
            queued_at=now,
            created_at=now,
            updated_at=now,
        )

        source = Source(
            id=source_id,
            user_id=test_user,
            source_type=SourceType.EMAIL,
            email_subject="Your Amazon order",
            email_from="orders@amazon.com",
            email_date=now,
            processed=False,
            created_at=now,
            updated_at=now,
        )

        with uow:
            uow.jobs.create(job)
            uow.sources.create(source)
            uow.commit()

        # Step 2: Mark job started (like worker does)
        with UnitOfWork() as uow2:
            uow2.jobs.mark_started(job_id)
            uow2.commit()

        # Step 3: Mark job completed (like worker does after parsing)
        with UnitOfWork() as uow3:
            uow3.jobs.mark_completed(job_id, {"status": "success"})
            uow3.sources.update_by_id(source_id, processed=True)
            uow3.commit()

        # Verify final state
        with UnitOfWork() as uow4:
            final_job = uow4.jobs.get_by_id(job_id)
            final_source = uow4.sources.get_by_id(source_id)

            assert final_job is not None
            assert final_job.status == JobStatus.COMPLETED
            assert final_source is not None
            assert final_source.processed is True

        print(f"Workflow test passed: job_id={job_id}")
