#!/usr/bin/env bash
# 小食叙记数据库定时备份脚本
# 用法：
#   1. sudo chmod +x /opt/bjtu-meal/deploy/backup.sh
#   2. sudo crontab -e 增加一行（每天凌晨 3 点执行）：
#      0 3 * * * /opt/bjtu-meal/deploy/backup.sh >> /opt/bjtu-meal/backups/backup.log 2>&1
set -euo pipefail

DB="/opt/bjtu-meal/database.db"
BACKUP_DIR="/opt/bjtu-meal/backups"
mkdir -p "$BACKUP_DIR"

# 使用 sqlite3 在线备份，避免直接 cp 正在写入的库导致损坏
sqlite3 "$DB" ".backup '${BACKUP_DIR}/database-$(date +%F-%H%M).db'"

# 只保留最近 30 份，其余删除
ls -1t "$BACKUP_DIR"/database-*.db 2>/dev/null | tail -n +31 | xargs -r rm -f

echo "[$(date '+%F %T')] 备份完成: ${BACKUP_DIR}/database-$(date +%F-%H%M).db"
