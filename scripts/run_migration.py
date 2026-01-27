"""
Run database migrations for Trackable.

This script applies SQL migration files to the Cloud SQL PostgreSQL instance.
Uses Cloud SQL Python Connector with SQLAlchemy and IAM authentication.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.cloud.sql.connector import Connector
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Load environment variables
load_dotenv()

# Database connection parameters
INSTANCE_CONNECTION_NAME = os.getenv(
    "INSTANCE_CONNECTION_NAME"
)  # Format: project:region:instance
DB_NAME = os.getenv("DB_NAME", "trackable")
DB_USER = os.getenv("DB_USER", "postgres")  # Should be service account email for IAM

# Migration directory
MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"

# Global connector instance
connector = Connector()


def getconn():
    """Create a database connection using Cloud SQL Python Connector with IAM auth."""
    if not INSTANCE_CONNECTION_NAME:
        print("❌ INSTANCE_CONNECTION_NAME not set in environment")
        print("   Format: project:region:instance")
        print("   Example: my-project:us-central1:trackable-db")
        sys.exit(1)

    try:
        conn = connector.connect(
            INSTANCE_CONNECTION_NAME,
            "pg8000",
            user=DB_USER,
            db=DB_NAME,
            enable_iam_auth=True,  # Use IAM authentication
        )
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to Cloud SQL: {e}")
        sys.exit(1)


def get_engine() -> Engine:
    """Create SQLAlchemy engine with Cloud SQL connector."""
    engine = create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    return engine


def run_migration(migration_file: Path, engine: Engine):
    """Run a single migration file using SQLAlchemy."""
    print(f"📝 Running migration: {migration_file.name}")

    with open(migration_file, "r") as f:
        sql = f.read()

    try:
        with engine.begin() as conn:
            # Execute the SQL migration within a transaction
            conn.execute(text(sql))
        print(f"✅ Migration {migration_file.name} completed successfully")
    except Exception as e:
        print(f"❌ Migration {migration_file.name} failed: {e}")
        sys.exit(1)


def grant_postgres_access(engine: Engine):
    """Grant postgres user access to all tables.

    When using IAM authentication, tables are owned by the service account.
    This grants the postgres user access so tables can be viewed in Cloud SQL Studio.
    """
    print("\n🔐 Granting postgres user access to tables...")

    try:
        with engine.begin() as conn:
            # Grant usage on schema
            conn.execute(text("GRANT USAGE ON SCHEMA public TO postgres"))

            # Grant all privileges on all tables
            conn.execute(
                text(
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO postgres"
                )
            )

            # Grant all privileges on all sequences
            conn.execute(
                text(
                    "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO postgres"
                )
            )

            # Set default privileges for future tables
            conn.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO postgres"
                )
            )

        print("✅ Postgres user access granted")
    except Exception as e:
        print(f"⚠️  Failed to grant postgres access (non-fatal): {e}")


def list_migrations():
    """List all available migration files."""
    migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
    # Exclude rollback files
    migrations = [m for m in migrations if "rollback" not in m.name.lower()]
    return migrations


def main():
    """Main function."""
    print("🚀 Trackable Database Migration Tool")
    print("=" * 50)

    # Check if migrations directory exists
    if not MIGRATIONS_DIR.exists():
        print(f"❌ Migrations directory not found: {MIGRATIONS_DIR}")
        sys.exit(1)

    # Check for specific migration file argument
    if len(sys.argv) > 1:
        migration_file = Path(sys.argv[1])
        if not migration_file.exists():
            # Try relative to migrations directory
            migration_file = MIGRATIONS_DIR / sys.argv[1]
        if not migration_file.exists():
            print(f"❌ Migration file not found: {sys.argv[1]}")
            sys.exit(1)
        migrations = [migration_file]
    else:
        # List all migrations
        migrations = list_migrations()

    if not migrations:
        print("⚠️  No migrations found")
        sys.exit(0)

    print(f"\nFound {len(migrations)} migration(s):")
    for migration in migrations:
        print(f"  - {migration.name}")

    # Confirm
    print("\n⚠️  This will apply migrations to:")
    print(f"   Instance: {INSTANCE_CONNECTION_NAME}")
    print(f"   Database: {DB_NAME}")
    print(f"   User: {DB_USER}")
    print(f"   Auth: IAM (Cloud SQL Connector)")

    response = input("\nProceed? (yes/no): ").strip().lower()
    if response not in ["yes", "y"]:
        print("❌ Migration cancelled")
        sys.exit(0)

    # Create engine
    print("\n🔌 Connecting to Cloud SQL...")
    engine = get_engine()

    # Run migrations
    print("\n" + "=" * 50)
    for migration in migrations:
        run_migration(migration, engine)

    # Grant postgres user access (for Cloud SQL Studio)
    grant_postgres_access(engine)

    # Clean up
    engine.dispose()
    connector.close()

    print("\n" + "=" * 50)
    print("✅ All migrations completed successfully!")


if __name__ == "__main__":
    main()
