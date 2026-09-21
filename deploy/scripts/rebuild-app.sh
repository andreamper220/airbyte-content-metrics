#!/bin/bash
set -eu
cd /var/www/content/deploy
docker compose build app
docker compose up -d app
