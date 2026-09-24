# RAG 知识库：pgvector + IVFFlat 方案

## 一、架构对比

### 当前方案（FAISS + SQLite）

```
存储层：
├── SQLite (data/database/jsj_agent.db)
│   └── 业务数据表（站点、降雨数据等）
├── FAISS 向量索引（knowledge/vector_store/dqh_faiss/）
│   ├── index.faiss（向量索引，内存加载）
│   └── index.pkl（文档元数据）
└── BM25 索引（knowledge/vector_store/dqh_bm25.pkl）

问题：
❌ 数据分散在3个存储系统
❌ FAISS 索引需要全量加载到内存
❌ 扩展性受限（单机内存瓶颈）
```

### pgvector 方案（统一到 PostgreSQL）

```
存储层：PostgreSQL 数据库
├── 业务数据表（站点、降雨数据等）
├── 向量表 + IVFFlat 索引（pgvector 扩展）
│   ├── knowledge_chunks 表（chunk文本 + 512维向量）
│   └── IVFFlat 索引（聚类中心 + 倒排列表）
└── 全文检索索引（PostgreSQL GIN 索引，替代 BM25）

优势：
✅ 统一存储，事务一致性
✅ 索引按需加载，内存占用小
✅ 天然支持分布式（Citus扩展）
✅ SQL直接查询向量+业务数据
```

---

## 二、pgvector + IVFFlat 原理

### 2.1 pgvector 扩展

**PostgreSQL 原生向量类型：**
```sql
-- 创建向量类型列
CREATE TABLE knowledge_chunks (
    id SERIAL PRIMARY KEY,
    basin_id TEXT,
    source TEXT,
    chunk_id INT,
    content TEXT,
    embedding VECTOR(512)  -- ← pgvector 提供的向量类型
);
```

**核心能力：**
- `VECTOR(n)` 数据类型：存储 n 维浮点向量
- 向量运算符：`<->` (L2距离)、`<#>` (内积)、`<=>` (余弦距离)
- 向量索引：IVFFlat、HNSW

### 2.2 IVFFlat 索引结构

**IVF（Inverted File with Flat compression）= 倒排文件索引**

**核心思想：聚类 + 倒排**

```
步骤1：K-Means 聚类（建索引时）
  将100万个向量聚类为1000个簇（cluster）
  每个簇有一个聚类中心（centroid）

步骤2：构建倒排列表
  Cluster 0 → [vec_5, vec_12, vec_89, ...]
  Cluster 1 → [vec_3, vec_45, vec_71, ...]
  ...
  Cluster 999 → [vec_8, vec_22, vec_94, ...]

检索时：
  1. 计算查询向量到所有聚类中心的距离
  2. 只搜索最近的 N 个簇（probes参数）
  3. 在这 N 个簇内暴力搜索
  
  时间复杂度：O(K + N*M)
    K = 簇数量（计算距离）
    N = 搜索簇数（probes）
    M = 每簇平均向量数
```

**示例：**
```
原始数据：100万个向量
聚类参数：lists=1000（1000个簇）
检索参数：probes=10（搜索10个簇）

建索引时间：~5分钟（K-Means聚类）
索引大小：~2GB（向量数据 + 聚类中心）
检索延迟：~50ms（计算1000个簇距离 + 搜索10个簇）

对比 FAISS Flat（暴力搜索）：
  检索延迟：~500ms（扫描全部100万向量）
  内存占用：2GB（全量加载）
```

---

## 三、数据库表设计

### 3.1 核心表结构

```sql
-- ========== 知识库向量表 ==========
CREATE TABLE knowledge_chunks (
    id SERIAL PRIMARY KEY,
    basin_id TEXT NOT NULL,                -- 流域ID（dqh/btpzh）
    source TEXT NOT NULL,                  -- 源文件名
    chunk_id INT NOT NULL,                 -- 块序号
    content TEXT NOT NULL,                 -- 原始文本内容
    embedding VECTOR(512) NOT NULL,        -- BGE向量（512维）
    token_count INT,                       -- 分词数（用于BM25替代）
    created_at TIMESTAMP DEFAULT NOW()
);

-- IVFFlat 向量索引
CREATE INDEX idx_chunks_embedding_ivfflat 
ON knowledge_chunks 
USING ivfflat (embedding vector_cosine_ops)  -- 余弦距离
WITH (lists = 100);  -- 聚类数 = sqrt(总行数) 推荐值

-- 业务查询索引
CREATE INDEX idx_chunks_basin ON knowledge_chunks(basin_id);
CREATE INDEX idx_chunks_source ON knowledge_chunks(source);

-- 全文检索索引（替代 BM25）
CREATE INDEX idx_chunks_content_gin 
ON knowledge_chunks 
USING gin(to_tsvector('jiebacfg', content));  -- 使用 jieba 中文分词
```

### 3.2 索引参数说明

**IVFFlat 参数：**

| 参数 | 说明 | 推荐值 | 本项目 |
|-----|------|--------|--------|
| `lists` | 聚类数（建索引时） | `sqrt(总行数)` | 100（假设1万chunks） |
| `probes` | 搜索簇数（查询时） | `lists * 0.1 ~ 0.2` | 10-20 |

**查询时设置 probes：**
```sql
SET ivfflat.probes = 10;  -- 搜索10个最近的簇

SELECT id, content, 1 - (embedding <=> '[0.1, 0.2, ...]') AS similarity
FROM knowledge_chunks
ORDER BY embedding <=> '[0.1, 0.2, ...]'  -- 查询向量
LIMIT 5;
```

**probes 权衡：**
- `probes=1`：最快，但召回率低（~60%）
- `probes=10`：平衡（召回率 ~90%，延迟 +10ms）
- `probes=lists`：等同于暴力搜索（召回率 100%，慢）

---

## 四、构建流程

### 4.1 文档处理（不变）

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

# 1. 文档切分（同当前方案）
splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=80,
    separators=["\n## ", "\n### ", "\n", "。", ".", " "],
)

docs = []
for fname in os.listdir("knowledge/basins/dqh"):
    with open(fname) as f:
        content = f.read()
    for i, chunk in enumerate(splitter.split_text(content)):
        docs.append({
            "basin_id": "dqh",
            "source": fname,
            "chunk_id": i,
            "content": chunk
        })

# 2. 向量化（同当前方案）
model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
embeddings = model.encode([d["content"] for d in docs], normalize_embeddings=True)

for doc, emb in zip(docs, embeddings):
    doc["embedding"] = emb.tolist()  # 转为Python list
```

### 4.2 入库（新增 PostgreSQL 操作）

```python
import psycopg2
from pgvector.psycopg2 import register_vector

# 连接 PostgreSQL
conn = psycopg2.connect(
    host="localhost",
    database="jsj_agent",
    user="postgres",
    password="your_password"
)
register_vector(conn)  # 注册 pgvector 类型

cur = conn.cursor()

# 批量插入
insert_sql = """
INSERT INTO knowledge_chunks (basin_id, source, chunk_id, content, embedding)
VALUES (%s, %s, %s, %s, %s)
"""

batch_data = [
    (d["basin_id"], d["source"], d["chunk_id"], d["content"], d["embedding"])
    for d in docs
]

cur.executemany(insert_sql, batch_data)
conn.commit()

print(f"✅ 插入 {len(docs)} 个 chunks")
```

### 4.3 创建索引（关键步骤）

```sql
-- 等所有数据插入完毕后再创建索引（性能优化）
CREATE INDEX idx_chunks_embedding_ivfflat 
ON knowledge_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 执行时间：~30秒（1万行）
-- 索引大小：~20MB
```

**注意事项：**
- 先插入数据，后建索引（避免每次插入都更新索引）
- `lists` 参数一旦设定不可修改（需重建索引）
- 推荐 `lists = sqrt(行数)`，本项目约 1万 chunks → `lists=100`

---

## 五、检索流程

### 5.1 纯向量检索（单路）

```python
import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

# 1. 查询向量化
model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
query = "定曲河流域有哪些站点？"
query_vector = model.encode(query, normalize_embeddings=True).tolist()

# 2. 向量检索
conn = psycopg2.connect(...)
register_vector(conn)
cur = conn.cursor()

cur.execute("SET ivfflat.probes = 10")  # 搜索10个簇

sql = """
SELECT 
    id,
    basin_id,
    source,
    content,
    1 - (embedding <=> %s::vector) AS similarity  -- 余弦相似度
FROM knowledge_chunks
WHERE basin_id = %s  -- 可选：限定流域
ORDER BY embedding <=> %s::vector
LIMIT 5
"""

cur.execute(sql, (query_vector, "dqh", query_vector))
results = cur.fetchall()

for row in results:
    print(f"[{row[1]}] {row[2]} (相似度: {row[4]:.3f})")
    print(row[3][:100], "...\n")
```

**SQL 解释：**
- `embedding <=> %s::vector`：余弦距离运算符（pgvector 提供）
- `1 - 距离`：转换为相似度（0~1，越大越相似）
- `ORDER BY embedding <=> ...`：触发 IVFFlat 索引

### 5.2 混合检索（向量 + 全文）

**PostgreSQL 原生全文检索替代 BM25：**

```sql
-- 设置检索参数
SET ivfflat.probes = 10;

-- 混合检索（CTE 写法）
WITH vector_results AS (
    SELECT 
        id,
        content,
        1 - (embedding <=> %s::vector) AS vec_score
    FROM knowledge_chunks
    WHERE basin_id = %s
    ORDER BY embedding <=> %s::vector
    LIMIT 20  -- 向量检索取20个候选
),
fulltext_results AS (
    SELECT 
        id,
        content,
        ts_rank(to_tsvector('jiebacfg', content), query) AS text_score
    FROM knowledge_chunks, to_tsquery('jiebacfg', %s) query
    WHERE basin_id = %s
      AND to_tsvector('jiebacfg', content) @@ query
    ORDER BY text_score DESC
    LIMIT 20  -- 全文检索取20个候选
)
-- RRF 融合（Reciprocal Rank Fusion）
SELECT 
    COALESCE(v.id, f.id) AS id,
    COALESCE(v.content, f.content) AS content,
    (
        COALESCE(1.0 / (60 + (ROW_NUMBER() OVER (ORDER BY v.vec_score DESC))), 0) +
        COALESCE(1.0 / (60 + (ROW_NUMBER() OVER (ORDER BY f.text_score DESC))), 0)
    ) AS fused_score
FROM vector_results v
FULL OUTER JOIN fulltext_results f ON v.id = f.id
ORDER BY fused_score DESC
LIMIT 5;
```

**参数说明：**
- `%s::vector`：查询向量（Python list → pgvector 类型）
- `to_tsquery('jiebacfg', %s)`：全文检索查询（需配置 jieba 分词）
- `ts_rank(...)`：PostgreSQL 的 TF-IDF 相似度（类似 BM25）

### 5.3 Python 封装

```python
class PgvectorRAG:
    def __init__(self, conn_string: str):
        self.conn = psycopg2.connect(conn_string)
        register_vector(self.conn)
        self.model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    
    def search(self, query: str, basin_id: str = None, top_k: int = 5):
        # 1. 查询向量化
        query_vector = self.model.encode(query, normalize_embeddings=True).tolist()
        
        # 2. 设置 IVFFlat 参数
        cur = self.conn.cursor()
        cur.execute("SET ivfflat.probes = 10")
        
        # 3. 向量检索
        sql = """
        SELECT id, basin_id, source, content, 
               1 - (embedding <=> %s::vector) AS similarity
        FROM knowledge_chunks
        WHERE (%s IS NULL OR basin_id = %s)
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """
        cur.execute(sql, (query_vector, basin_id, basin_id, query_vector, top_k))
        
        results = []
        for row in cur.fetchall():
            results.append({
                "id": row[0],
                "basin_id": row[1],
                "source": row[2],
                "content": row[3],
                "similarity": row[4]
            })
        
        return results
    
    def search_with_context(self, query: str, basin_id: str = None, top_k: int = 5) -> str:
        results = self.search(query, basin_id, top_k)
        parts = []
        for r in results:
            parts.append(f"[来源：{r['basin_id']} — {r['source']}]\n{r['content']}")
        return "\n\n---\n\n".join(parts)
```

---

## 六、性能对比

### 6.1 检索性能

| 方案 | 索引类型 | 数据量 | 检索延迟 | 召回率 | 内存占用 |
|-----|---------|--------|---------|--------|---------|
| FAISS Flat | 暴力搜索 | 1万 | 50ms | 100% | 200MB（全量） |
| FAISS IVFFlat | 聚类索引 | 1万 | 10ms | 95% | 200MB（全量） |
| **pgvector IVFFlat** | 聚类索引 | 1万 | 15ms | 95% | **20MB（按需）** |
| pgvector HNSW | 图索引 | 1万 | 5ms | 98% | 50MB（按需） |

**扩展到百万级：**

| 数据量 | FAISS Flat | pgvector IVFFlat (lists=1000) | pgvector HNSW |
|--------|-----------|------------------------------|---------------|
| 10万   | 500ms     | 50ms                         | 10ms          |
| 100万  | 5000ms    | 100ms                        | 15ms          |
| 内存   | 2GB       | 200MB                        | 500MB         |

### 6.2 写入性能

```
批量插入 1万 chunks：
  - 插入数据：2秒
  - 建 IVFFlat 索引：30秒
  - 建 GIN 全文索引：5秒
  总计：~40秒

对比 FAISS：
  - 向量化：10秒
  - FAISS 索引：5秒
  - BM25 索引：3秒
  - 序列化保存：2秒
  总计：~20秒
```

**结论：** 初次构建稍慢，但运行时优势明显

---

## 七、方案对比总结

### 7.1 技术架构

| 维度 | FAISS + SQLite | pgvector + PostgreSQL |
|-----|---------------|----------------------|
| 存储统一性 | ❌ 分散（3个系统） | ✅ 统一数据库 |
| 事务一致性 | ❌ 无 | ✅ ACID 保证 |
| 内存占用 | ❌ 全量加载 | ✅ 按需加载 |
| 扩展性 | ❌ 单机内存瓶颈 | ✅ 支持分布式（Citus） |
| 部署复杂度 | ✅ 低（纯Python） | ⚠️ 中（需PostgreSQL） |

### 7.2 功能对比

| 功能 | FAISS + BM25 | pgvector + GIN |
|-----|-------------|----------------|
| 向量检索 | ✅ | ✅ |
| 关键词检索 | ✅ BM25 | ✅ PostgreSQL 全文检索 |
| 混合检索 | ✅ RRF 融合 | ✅ SQL JOIN 融合 |
| 过滤查询 | ⚠️ 需先过滤再检索 | ✅ SQL WHERE 原生支持 |
| 分页查询 | ⚠️ 需手动实现 | ✅ LIMIT OFFSET |
| 元数据查询 | ❌ 需额外存储 | ✅ 直接 JOIN 业务表 |

### 7.3 适用场景

**选择 FAISS：**
- ✅ 数据量小（<10万向量）
- ✅ 纯向量检索，无复杂业务逻辑
- ✅ 快速原型验证
- ✅ 离线部署，无数据库依赖

**选择 pgvector：**
- ✅ 数据量大（>10万向量）
- ✅ 需要结合业务数据查询（JOIN）
- ✅ 需要事务一致性
- ✅ 团队有 PostgreSQL 运维能力
- ✅ 生产环境部署

---

## 八、迁移方案

### 8.1 从 FAISS 迁移到 pgvector

**步骤 1：安装 pgvector**
```bash
# Ubuntu/Debian
sudo apt install postgresql-16-pgvector

# 或从源码编译
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

**步骤 2：数据库初始化**
```sql
CREATE EXTENSION vector;

CREATE TABLE knowledge_chunks (
    id SERIAL PRIMARY KEY,
    basin_id TEXT NOT NULL,
    source TEXT NOT NULL,
    chunk_id INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(512) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

**步骤 3：数据迁移脚本**
```python
import pickle
from langchain_community.vectorstores import FAISS
import psycopg2
from pgvector.psycopg2 import register_vector

# 1. 加载 FAISS 索引
vectorstore = FAISS.load_local("knowledge/vector_store/dqh_faiss", ...)

# 2. 提取向量和文档
docs = vectorstore.docstore._dict.values()

# 3. 写入 PostgreSQL
conn = psycopg2.connect(...)
register_vector(conn)
cur = conn.cursor()

for doc in docs:
    # 重新向量化（FAISS 存储的向量可能不在 docstore）
    embedding = embeddings_model.encode(doc.page_content).tolist()
    
    cur.execute("""
        INSERT INTO knowledge_chunks (basin_id, source, chunk_id, content, embedding)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        doc.metadata["basin_id"],
        doc.metadata["source"],
        doc.metadata["chunk_id"],
        doc.page_content,
        embedding
    ))

conn.commit()
print("✅ 迁移完成")
```

**步骤 4：创建索引**
```sql
-- 等数据全部插入后再建索引
CREATE INDEX idx_chunks_embedding_ivfflat 
ON knowledge_chunks 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### 8.2 代码改造

**原 FAISS 代码：**
```python
from knowledge.rag_engine import get_rag

rag = get_rag()
results = rag.search("定曲河站点", basin_id="dqh", top_k=5)
```

**改为 pgvector：**
```python
from knowledge.pgvector_rag import PgvectorRAG

rag = PgvectorRAG("postgresql://user:pass@localhost/jsj_agent")
results = rag.search("定曲河站点", basin_id="dqh", top_k=5)
```

---

## 九、核心代码示例

**完整 pgvector RAG 实现（简化版）：**
```python
# knowledge/pgvector_rag.py
import psycopg2
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional

class PgvectorRAG:
    def __init__(self, conn_string: str, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.conn = psycopg2.connect(conn_string)
        register_vector(self.conn)
        self.model = SentenceTransformer(model_name)
        
    def add_documents(self, documents: List[Dict]):
        """批量添加文档"""
        cur = self.conn.cursor()
        
        # 批量向量化
        contents = [d["content"] for d in documents]
        embeddings = self.model.encode(contents, normalize_embeddings=True)
        
        # 批量插入
        insert_sql = """
        INSERT INTO knowledge_chunks (basin_id, source, chunk_id, content, embedding)
        VALUES (%s, %s, %s, %s, %s)
        """
        batch_data = [
            (d["basin_id"], d["source"], d["chunk_id"], d["content"], emb.tolist())
            for d, emb in zip(documents, embeddings)
        ]
        cur.executemany(insert_sql, batch_data)
        self.conn.commit()
        
    def search(
        self, 
        query: str, 
        basin_id: Optional[str] = None, 
        top_k: int = 5,
        probes: int = 10
    ) -> List[Dict]:
        """向量检索"""
        query_vector = self.model.encode(query, normalize_embeddings=True).tolist()
        
        cur = self.conn.cursor()
        cur.execute(f"SET ivfflat.probes = {probes}")
        
        sql = """
        SELECT id, basin_id, source, content, 
               1 - (embedding <=> %s::vector) AS similarity
        FROM knowledge_chunks
        WHERE (%s IS NULL OR basin_id = %s)
        ORDER BY embedding <=> %s::vector
        LIMIT %s
        """
        
        cur.execute(sql, (query_vector, basin_id, basin_id, query_vector, top_k))
        
        return [
            {
                "id": row[0],
                "basin_id": row[1],
                "source": row[2],
                "content": row[3],
                "similarity": float(row[4])
            }
            for row in cur.fetchall()
        ]
    
    def build_index(self, lists: int = 100):
        """创建 IVFFlat 索引"""
        cur = self.conn.cursor()
        cur.execute(f"""
        CREATE INDEX IF NOT EXISTS idx_chunks_embedding_ivfflat 
        ON knowledge_chunks 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = {lists})
        """)
        self.conn.commit()
        print(f"✅ 索引创建完成 (lists={lists})")
```

---

## 十、总结

**pgvector + IVFFlat 方案关键点：**

1. **统一存储**：向量、元数据、业务数据在同一个 PostgreSQL
2. **IVFFlat 索引**：通过聚类加速检索，内存占用小
3. **SQL 原生支持**：WHERE 过滤、JOIN 关联、事务保证
4. **渐进式迁移**：可从 FAISS 平滑迁移，代码改动小

**适合本项目的场景：**
- 知识库规模增长到 10万+ chunks
- 需要结合业务数据（站点信息、事件元数据）联合查询
- 生产环境要求高可用、可扩展

**推荐配置：**
- `lists = 100`（1万 chunks）
- `probes = 10`（平衡速度与召回）
- PostgreSQL 14+ + pgvector 0.5.0+
