#!/usr/bin/env bash
# One-command Hugging Face Space deploy (run locally — no GitHub Action needed).
#
# Prereqs (one-time):
#   1. Create the Space in the HF dashboard: New Space -> SDK: Docker ->
#      owner ashu010, name nexus-ai, template Blank.
#   2. Have an HF *write* token (https://huggingface.co/settings/tokens).
#
# Run from the repo root, one of:
#   HF_TOKEN=hf_xxx bash deploy/push-to-hf.sh
#   # or put the token in a gitignored file and just run the script:
#   echo "hf_xxx" > .hf_token && bash deploy/push-to-hf.sh
#
# It clones the Space, syncs backend/ + the HF Dockerfile/README/start
# script, and pushes — HF then builds and serves at
#   https://ashu010-nexus-ai.hf.space
set -euo pipefail

HF_USER="${HF_USER:-ashu010}"
HF_SPACE="${HF_SPACE:-nexus-ai}"

# Resolve token from env or .hf_token file.
TOKEN="${HF_TOKEN:-}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -z "$TOKEN" ] && [ -f "$REPO_ROOT/.hf_token" ]; then
  TOKEN="$(tr -d ' \t\r\n' < "$REPO_ROOT/.hf_token")"
fi
if [ -z "$TOKEN" ]; then
  echo "error: no HF token. Set HF_TOKEN=... or write it to .hf_token" >&2
  exit 2
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "push-to-hf: cloning Space ${HF_USER}/${HF_SPACE} ..."
git -c credential.helper= \
    -c "credential.helper=!f() { echo username=${HF_USER}; echo password=${TOKEN}; }; f" \
    clone "https://huggingface.co/spaces/${HF_USER}/${HF_SPACE}" "$WORK/space"

cd "$WORK/space"
git config user.email "deploy@nexus.local"
git config user.name "nexus-deploy"

echo "push-to-hf: syncing backend ..."
# Wipe everything except git metadata so deletions propagate.
find . -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +

# Copy backend tree + HF-specific Docker/README/start script to Space root.
cp -r "$REPO_ROOT/backend/." ./
cp "$REPO_ROOT/deploy/Dockerfile.hf" Dockerfile
cp "$REPO_ROOT/deploy/hf-readme.md" README.md
cp "$REPO_ROOT/deploy/start-hf.sh" start-hf.sh

# Never ship a plaintext .env or local caches to the Space.
rm -f .env
rm -rf .local .pytest_cache __pycache__ .memory storage/exports

git add -A
git commit -m "deploy: sync backend $(git -C "$REPO_ROOT" rev-parse --short HEAD)" --allow-empty
git -c credential.helper= \
    -c "credential.helper=!f() { echo username=${HF_USER}; echo password=${TOKEN}; }; f" \
    push origin main

echo ""
echo "push-to-hf: done. HF is building now."
echo "  Space:  https://huggingface.co/spaces/${HF_USER}/${HF_SPACE}"
echo "  Live:   https://${HF_USER}-${HF_SPACE}.hf.space/api/health"
