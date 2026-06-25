#!/usr/bin/env bash
# Convenience wrapper: build once, then run a mission interactively.
#
#   ./run.sh "Map the leadership and funding of the top 5 AI safety nonprofits"
#
# Anything after the script name becomes the mission brief. If you omit it,
# Scout will prompt you for one.
set -euo pipefail

if [ ! -f .env ]; then
  echo "No .env found. Copy .env.example to .env and add your model + key first:"
  echo "    cp .env.example .env"
  exit 1
fi

mkdir -p output sources

# Build only if the image is missing or the Dockerfile/source changed.
docker compose build

docker compose run --rm scout "$@"
