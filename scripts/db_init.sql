-- AstroForge PostgreSQL 初始化脚本（方案 3.9 部署约定）
--
-- 用法（密码经 psql 变量传入，不落明文）：
--   psql -U postgres -v pgpassword="你的密码" -f scripts/db_init.sql
--
-- 服务端建议（postgresql.conf）：
--   listen_addresses = 'localhost'
--   shared_buffers = 512MB
--   timezone = 'UTC'
--
-- 恢复（备份轮转见 scripts/db_backup.*）：
--   pg_restore -d astroforge --clean --if-exists data/backups/astroforge_YYYYMMDD.dump

CREATE ROLE astroforge LOGIN PASSWORD :'pgpassword';

CREATE DATABASE astroforge
    OWNER astroforge
    ENCODING 'UTF8'
    TEMPLATE template0;

-- 业务账号仅授权本库（最小权限）
GRANT ALL PRIVILEGES ON DATABASE astroforge TO astroforge;
