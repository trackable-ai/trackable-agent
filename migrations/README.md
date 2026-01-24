# Database Migrations

This directory contains SQL migration files for the Trackable PostgreSQL database.

## Prerequisites

1. **Cloud SQL Instance**: PostgreSQL instance with IAM authentication enabled
2. **Service Account**: With Cloud SQL Client role and database user created
3. **Application Default Credentials**: Configured locally

### Enable IAM Authentication on Cloud SQL

```bash
# Enable IAM authentication on your database user
gcloud sql users create SERVICE_ACCOUNT_EMAIL \
  --instance=INSTANCE_NAME \
  --type=CLOUD_IAM_SERVICE_ACCOUNT

# Grant necessary permissions
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:SERVICE_ACCOUNT_EMAIL" \
  --role="roles/cloudsql.client"
```

## Configuration

Set database connection in `.env`:

```bash
# Cloud SQL instance connection name (format: project:region:instance)
INSTANCE_CONNECTION_NAME=your-project:us-central1:your-instance
DB_NAME=trackable

# Service account email for IAM authentication (no password needed)
DB_USER=your-service-account@your-project.iam.gserviceaccount.com

# Service account key file
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json
```

The migration script uses:

- **SQLAlchemy**: ORM and connection management
- **Cloud SQL Python Connector**: Secure connection with automatic SSL
- **IAM Authentication**: No passwords, uses service account credentials

## Running Migrations

```bash
python scripts/run_migration.py
```

The script will:

1. Connect to Cloud SQL using the Python Connector
2. List all available migrations
3. Confirm before applying
4. Execute migrations in a transaction

## Migration Files

- `001_initial_schema.sql` - Initial database schema (8 tables aligned with Pydantic models)

See [docs/database_schema.md](../docs/database_schema.md) for detailed schema documentation.
