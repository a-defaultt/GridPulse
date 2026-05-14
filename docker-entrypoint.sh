#!/bin/bash
set -e

# Initialize DB if needed (main.py calls init_db, but we can be explicit)
# python3 -c "from src.database.db_handler import init_db; init_db()"

if [ "$1" = 'scheduler' ]; then
    echo "Starting GridPulse V5 Scheduler..."
    exec python3 -m src.delivery.scheduler
else
    # Allow running manual commands (e.g. ./run.py --edition daily)
    exec "$@"
fi
