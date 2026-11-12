#!/bin/bash
DB_PATH="/home/ubuntu/TrackerBot/tracker.db"
BACKUP_DIR="/home/ubuntu/TrackerBot/backups"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Generate timestamped backup file safely while DB is running
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/tracker_backup_$TIMESTAMP.db'"

# Optional: Keep only the last 7 days of backups to save disk space
find "$BACKUP_DIR" -type f -name "tracker_backup_*.db" -mtime +7 -delete
