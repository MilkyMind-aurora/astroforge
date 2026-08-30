#!/usr/bin/env bash
# AstroForge 数据库每日备份脚本（macOS/Linux cron）
set -e
[ -n "$ASTROFORGE_PG_PASSWORD" ] || { echo "[MISS] ASTROFORGE_PG_PASSWORD not set"; exit 1; }
BACKUP_DIR="$(dirname "$0")/../data/backups"
mkdir -p "$BACKUP_DIR"
export PGPASSWORD="$ASTROFORGE_PG_PASSWORD"
TODAY=$(date +%Y%m%d)
pg_dump -Fc -U astroforge -T monitor_metrics -f "$BACKUP_DIR/astroforge_$TODAY.dump" astroforge
# 轮转：删除 7 天前的备份
find "$BACKUP_DIR" -name "astroforge_*.dump" -mtime +7 -delete
echo "[OK] backup done: astroforge_$TODAY.dump"
