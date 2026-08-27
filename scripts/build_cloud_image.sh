#!/usr/bin/env bash
# Build a cloud image that includes the prebuilt index.
# Docker only reads ".dockerignore" from the build context root, so we
# temporarily swap in .dockerignore.cloud for this build.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f index/index_meta.json ]]; then
  echo "ERROR: index/ missing. Run: python scripts/build_index.py" >&2
  exit 1
fi

TAG="${1:-fin-rag-lab:cloud}"
DOCKER="${DOCKER:-docker}"
if ! command -v "$DOCKER" >/dev/null 2>&1; then
  if [[ -x /Applications/Docker.app/Contents/Resources/bin/docker ]]; then
    DOCKER=/Applications/Docker.app/Contents/Resources/bin/docker
  else
    echo "ERROR: docker not found" >&2
    exit 1
  fi
fi

cleanup() {
  if [[ -f .dockerignore.bak-cloud ]]; then
    mv -f .dockerignore.bak-cloud .dockerignore
  fi
}
trap cleanup EXIT

cp .dockerignore .dockerignore.bak-cloud
# Cloud ignore: keep index + embeddings, still exclude secrets
cat > .dockerignore <<'EOF'
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
.venv/
venv/
.env
.env.*
!.env.example
.git/
.github/
notebooks/
cache_bundle.zip
chroma_db*/
tmp_chroma_*/
tmp_*.csv
cache/docs/
cache/vlm/
.idea/
.vscode/
.cursor/
.DS_Store
Thumbs.db
*.md
!README.md
EOF

echo "Building $TAG with baked index + embeddings cache (linux/amd64 for Fargate)…"
"$DOCKER" build --platform linux/amd64 -f Dockerfile.cloud -t "$TAG" .
echo "Done: $TAG"
