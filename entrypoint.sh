#!/bin/sh
# Runs every time the web container starts: apply database changes and make sure
# the default matrix and hazard library exist (existing data is never overwritten).
set -e
python manage.py migrate --noinput
python manage.py load_defaults
exec "$@"
