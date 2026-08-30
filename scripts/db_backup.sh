#!/usr/bin/env bash
# AstroForge 数据库每日备份脚本（macOS/Linux cron）
# 凭据经临时 pgpass 文件注入（权限 600），脚本内不出现明文口令
set -e
[ -n "$ASTROFORGE_PG_PASSWORD" ] || { echo "[MISS] ASTROFORGE_PG_PASSWORD not set"; exit 1; }
BACKUP_DIR="$(dirname "$0")/../data/backups"
mkdir -p "$BACKUP_DIR"

PGPASSFILE="$(mktemp)"
trap 'rm -f "$PGPASSFILE"' EXIT
chmod 600 "$PGPASSFILE"
printf '127.0.0.1:5432:astroforge:astroforge:%s\n' "$ASTROFORGE_PG_PASSWORD" > "$PGPASSFILE"
export PGPASSFILE

TODAY=$(date +%Y%m%d)
pg_dump -Fc -U astroforge -T monitor_metrics -f "$BACKUP_DIR/astroforge_$TODAY.dump" astroforge
# 轮转：删除 7 天前的备份
find "$BACKUP_DIR" -name "astroforge_*.dump" -mtime +7 -delete
echo "[OK] backup done: astroforge_$TODAY.dump"
