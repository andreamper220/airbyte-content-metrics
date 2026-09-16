#!/bin/bash
set -eu
ROOT=/var/www/content
cd "$ROOT"
BASE_IMAGE="docker.io/airbyte/python-connector-base:4.0.0@sha256:d9894b6895923b379f3006fa251147806919c62b7d9021b5cd125bb67d7bbe22"
docker build -f docker-images/Dockerfile.python-connector \
  --build-arg BASE_IMAGE="$BASE_IMAGE" \
  --build-arg CONNECTOR_NAME=source-yandex-metrica \
  -t airbyte/source-yandex-metrica:dev \
  airbyte-integrations/connectors/source-yandex-metrica
kind load docker-image airbyte/source-yandex-metrica:dev -n airbyte-abctl
cp /var/www/content/deploy/secrets/source-metrika-config.json /tmp/metrika-config.json
chmod 644 /tmp/metrika-config.json
docker run --rm -v /tmp/metrika-config.json:/config.json:ro airbyte/source-yandex-metrica:dev check --config /config.json | tail -3
