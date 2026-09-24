-- PostgreSQL 初始化脚本

-- 启用 pgvector 扩展（用于向量检索）
CREATE EXTENSION IF NOT EXISTS vector;

-- 启用 pg_trgm 扩展（用于全文检索）
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 创建监控用数据库（Grafana）
-- 主数据库已由 POSTGRES_DB 环境变量创建

-- 验证扩展安装
SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'pg_trgm');
