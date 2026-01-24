#!/bin/bash
# Deploy Trackable Ingress Service to Cloud Run
# This script uses source-based deployment with automatic container building

set -e  # Exit on error

# Configuration
PROJECT_ID="gen-lang-client-0659747538"
REGION="us-central1"
SERVICE_NAME="trackable-ingress"
SERVICE_ACCOUNT="trackable-ai-dev@gen-lang-client-0659747538.iam.gserviceaccount.com"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Trackable Ingress to Cloud Run${NC}"
echo "=================================="
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo "=================================="

# Ensure we're in the project root
cd "$(dirname "$0")/.."

# Deploy to Cloud Run with source-based deployment
echo -e "${YELLOW}📦 Deploying to Cloud Run (this will build the container image)...${NC}"

gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --service-account $SERVICE_ACCOUNT \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION" \
  --cpu 2 \
  --memory 2Gi \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --port 8080

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
echo "Test the deployment:"
echo "  Health check: curl $SERVICE_URL/health"
echo "  Chat API: curl -X POST $SERVICE_URL/api/chat -H 'Content-Type: application/json' -d '{\"message\": \"Hello!\", \"user_id\": \"test\"}'"
