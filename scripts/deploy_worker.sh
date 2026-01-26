#!/bin/bash
# Deploy Trackable Worker Service to Cloud Run
# This script deploys the worker service for processing Cloud Tasks

set -e  # Exit on error

# Configuration
PROJECT_ID="gen-lang-client-0659747538"
REGION="us-central1"
SERVICE_NAME="trackable-worker"
SERVICE_ACCOUNT="trackable-ai-dev@gen-lang-client-0659747538.iam.gserviceaccount.com"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔨 Deploying Trackable Worker to Cloud Run${NC}"
echo "=================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo "=================================="

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Copy Dockerfile to root for Cloud Run build
cp docker/Dockerfile.worker Dockerfile.worker

# Deploy to Cloud Run with Dockerfile
echo -e "${YELLOW}📦 Deploying to Cloud Run (this will build the container image)...${NC}"

gcloud run deploy $SERVICE_NAME \
  --source . \
  --dockerfile Dockerfile.worker \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --no-allow-unauthenticated \
  --service-account $SERVICE_ACCOUNT \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION" \
  --cpu 2 \
  --memory 2Gi \
  --timeout 900 \
  --max-instances 10 \
  --min-instances 0 \
  --concurrency 10 \
  --port 8080

# Clean up temporary Dockerfile
rm Dockerfile.worker

echo -e "${GREEN}✅ Deployment complete!${NC}"

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --format 'value(status.url)')

echo ""
echo "=================================="
echo -e "${GREEN}Service URL: $SERVICE_URL${NC}"
echo "=================================="
echo ""
echo "⚠️  Note: This is an internal service (authentication required)"
echo ""
echo "Test the deployment:"
echo "  Health check:"
echo "    TOKEN=\$(gcloud auth print-identity-token)"
echo "    curl -H \"Authorization: Bearer \$TOKEN\" $SERVICE_URL/health"
echo ""
echo "Next steps:"
echo "  1. Create Cloud Tasks queue"
echo "  2. Configure task queue to target this service"
echo "  3. Grant Cloud Tasks service account permission to invoke this service"
