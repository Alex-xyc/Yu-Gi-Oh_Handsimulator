#!/usr/bin/env bash
# One-time Google Cloud setup for deploying the web app to Cloud Run (see README "Deploy on
# Google Cloud Run"). Run it in Cloud Shell (or anywhere gcloud is logged in as the project owner):
#   bash cloudrun-setup.sh <project-id>
# Safe to run again: anything that already exists is left as it is.
#
# What it creates:
#   - an Artifact Registry repository for the images (keeps the 3 newest, to stay in the free 0.5 GB)
#   - a Cloud Storage bucket for the card image cache, mounted at /cache in the container
#   - a service account the app runs as (may only read and write that bucket)
#   - a service account GitHub Actions deploys as, signed in with Workload Identity Federation,
#     so no key is stored in GitHub; only this repository's workflows can use it
# Then it prints the GitHub repository variables the Deploy workflow reads.

set -euo pipefail

PROJECT_ID="${1:?usage: bash cloudrun-setup.sh <project-id>}"
# us-central1: Cloud Run's cheaper price tier, and Cloud Storage's free 5 GB only applies in US regions
REGION="${REGION:-us-central1}"
GITHUB_REPO="${GITHUB_REPO:-Alex-xyc/Yu-Gi-Oh_Handsimulator}"

BUCKET="${PROJECT_ID}-ygo-cache"
RUN_SA="ygo-calc-run@${PROJECT_ID}.iam.gserviceaccount.com"
DEPLOY_SA="github-deploy@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"

echo "== Enabling APIs (takes a minute the first time)"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com storage.googleapis.com \
    iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com

echo "== Image repository"
gcloud artifacts repositories describe ygo-calc --location="$REGION" >/dev/null 2>&1 ||
    gcloud artifacts repositories create ygo-calc --repository-format=docker --location="$REGION" \
        --description="YGO-Calc web app images"
POLICY="$(mktemp)"
cat > "$POLICY" <<'EOF'
[
  {"name": "keep-newest", "action": {"type": "Keep"}, "mostRecentVersions": {"keepCount": 3}},
  {"name": "delete-rest", "action": {"type": "Delete"}, "condition": {"tagState": "any"}}
]
EOF
gcloud artifacts repositories set-cleanup-policies ygo-calc --location="$REGION" --policy="$POLICY" --no-dry-run
rm -f "$POLICY"

echo "== Image cache bucket"
gcloud storage buckets describe "gs://$BUCKET" >/dev/null 2>&1 ||
    gcloud storage buckets create "gs://$BUCKET" --location="$REGION" --default-storage-class=STANDARD \
        --uniform-bucket-level-access --public-access-prevention

echo "== Service accounts"
gcloud iam service-accounts describe "$RUN_SA" >/dev/null 2>&1 ||
    gcloud iam service-accounts create ygo-calc-run --display-name="YGO-Calc web app"
gcloud iam service-accounts describe "$DEPLOY_SA" >/dev/null 2>&1 ||
    gcloud iam service-accounts create github-deploy --display-name="GitHub Actions deploy"
# Accounts can take a few seconds to become usable in IAM bindings
sleep 10

# The app: read and write the cache bucket, nothing else
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
    --member="serviceAccount:$RUN_SA" --role=roles/storage.objectUser >/dev/null
# The deployer: push images, deploy the service (run.admin so it can make it public), run it as the app account
gcloud artifacts repositories add-iam-policy-binding ygo-calc --location="$REGION" \
    --member="serviceAccount:$DEPLOY_SA" --role=roles/artifactregistry.writer >/dev/null
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$DEPLOY_SA" --role=roles/run.admin --condition=None >/dev/null
gcloud iam service-accounts add-iam-policy-binding "$RUN_SA" \
    --member="serviceAccount:$DEPLOY_SA" --role=roles/iam.serviceAccountUser >/dev/null

echo "== GitHub sign-in (Workload Identity Federation)"
gcloud iam workload-identity-pools describe github --location=global >/dev/null 2>&1 ||
    gcloud iam workload-identity-pools create github --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers describe github --location=global \
        --workload-identity-pool=github >/dev/null 2>&1 ||
    gcloud iam workload-identity-pools providers create-oidc github --location=global \
        --workload-identity-pool=github --display-name="GitHub Actions" \
        --issuer-uri="https://token.actions.githubusercontent.com" \
        --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
        --attribute-condition="assertion.repository == '$GITHUB_REPO'"
gcloud iam service-accounts add-iam-policy-binding "$DEPLOY_SA" --role=roles/iam.workloadIdentityUser \
    --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/attribute.repository/$GITHUB_REPO" \
    >/dev/null

PROVIDER="projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github/providers/github"
cat <<EOF

Done. Add these as GitHub repository variables (Settings > Secrets and variables > Actions >
Variables), or run these commands where the GitHub CLI is logged in:

  gh variable set GCP_PROJECT_ID --repo $GITHUB_REPO --body "$PROJECT_ID"
  gh variable set GCP_REGION --repo $GITHUB_REPO --body "$REGION"
  gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --repo $GITHUB_REPO --body "$PROVIDER"
  gh variable set GCP_DEPLOY_SERVICE_ACCOUNT --repo $GITHUB_REPO --body "$DEPLOY_SA"

Then push to main (or re-run the Deploy workflow); the first deploy creates the service and
prints its URL. IAM changes can take a few minutes to apply.
EOF
