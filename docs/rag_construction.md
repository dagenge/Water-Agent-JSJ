# RAG 知识库构建流程

## 一、构建流程概览

**不是逐字词向量化，而是按语义块（chunk）向量化**

```
原始文档（.md文件）
    ↓
文本切分（600字/块，重叠80字）
    ↓
每个chunk生成一个512维向量
    ↓
并行构建两个索引：
    ├─ FAISS 向量索引（语义相似度）
    └─ BM25 关键词索引（精确匹配）
    ↓
检索时融合两路结果（RRF算法）
```

---

## 二、详细步骤拆解

### 2.1 文档加载与切分

**代码位置：** `knowledge/rag_engine.py` Line 120-140

```python
def load_documents(self) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,        # 每块600字符
        chunk_overlap=80,      # 块间重叠80字符（防止语义割裂）
        separators=["\n## ", "\n### ", "\n", "。", ".", " "],  # 按标题→段落→句子优先切分
    )
    
    for fname in sorted(os.listdir(self.doc_dir)):
        if not fname.endswith(".md"):
            continue
        with open(os.path.join(self.doc_dir, fname), encoding="utf-8") as f:
            content = f.read()
        for i, chunk in enumerate(splitter.split_text(content)):
            docs.append(Document(
                page_content=chunk,  # 切分后的文本块
                metadata={"basin_id": "dqh", "source": fname, "chunk_id": i}
            ))
```

**切分策略：**
1. **优先按结构切分**：Markdown 标题（`## `、`### `）→ 段落（`\n`）→ 句子（`。`、`.`）
2. **保持语义完整**：尽量不在句子中间切断
3. **重叠设计**：80字符重叠，避免边界信息丢失

**示例：**
```
原始文档（1500字）
    ↓
切分后：
  chunk_0: [0-600] "## 定曲河流域概况\n定曲河位于..."
  chunk_1: [520-1120] "...流域面积3200平方公里\n## 站点分布\n共4个..."
  chunk_2: [1040-1500] "...监测频率为每小时一次..."
  
注意：chunk_1的起始位置是520（600-80），实现了重叠
```

---

### 2.2 向量化（Embedding）

**代码位置：** `knowledge/rag_engine.py` Line 161

```python
self.vectorstore = FAISS.from_documents(docs, self.embeddings)
```

**向量化机制：**

**使用模型：** BAAI/bge-small-zh-v1.5（中文语义向量模型）
- 向量维度：512
- 模型大小：~84MB
- 运行环境：纯CPU，首次自动下载到 `~/.cache/huggingface`

**向量化单位：** **整个 chunk（600字符块）**，而非逐字词

```python
# 伪代码演示
chunk_text = "定曲河位于云南省,流域面积3200平方公里,共有4个水文站点..."

# 调用 Sentence-Transformers
vector = model.encode(chunk_text)  # 生成512维向量
# vector = [0.123, -0.456, 0.789, ..., 0.234]  # 共512个浮点数
```

**向量含义：**
- 每个维度捕捉文本的某个语义特征
- 相似语义的文本向量距离更近（余弦相似度）

**批量处理：**
```python
# BGEEmbeddings.embed_documents (Line 67-74)
def embed_documents(self, texts: list[str]) -> list[list[float]]:
    vecs = self._model.encode(
        texts,  # 一次处理多个chunk
        normalize_embeddings=True,  # 归一化，提升检索效果
        batch_size=32,  # 每批32个chunk
    )
    return vecs.tolist()

# 示例：
chunks = [chunk_0, chunk_1, chunk_2, ...]  # 100个chunk
vectors = embeddings.embed_documents(chunks)
# vectors = [[0.1, 0.2, ...], [0.3, -0.1, ...], ...]  # 100个512维向量
```

---

### 2.3 FAISS 索引构建

**FAISS（Facebook AI Similarity Search）：**
- 高效的向量相似度搜索引擎
- 支持海量向量（百万级）的毫秒级检索
- 使用余弦相似度衡量语义接近程度

**索引结构：**
```
FAISS索引文件（index.faiss）
├─ 向量列表：[[vec_0], [vec_1], ..., [vec_n]]
├─ 文档映射：{0: chunk_0, 1: chunk_1, ..., n: chunk_n}
└─ 检索算法：余弦相似度（归一化后内积）
```

**检索过程：**
```python
# 用户查询："定曲河有多少站点"
query_vector = embeddings.embed_query("定曲河有多少站点")  # 生成512维向量

# FAISS 计算相似度
similarities = cosine_similarity(query_vector, all_chunk_vectors)
# 结果：[0.85, 0.32, 0.91, 0.15, ...]

# 返回相似度最高的5个chunk
top_5_chunks = [chunk_2, chunk_0, chunk_5, ...]
```

---

### 2.4 BM25 关键词索引

**代码位置：** `knowledge/rag_engine.py` Line 164-167

```python
tokenized = [_tokenize(d.page_content) for d in docs]
self.bm25 = BM25Okapi(tokenized)
```

**BM25（Best Matching 25）：**
- 经典的关键词检索算法（ElasticSearch 的核心）
- 基于词频（TF）和逆文档频率（IDF）
- 擅长精确匹配（如站点名、事件代码）

**中文分词策略：** `_tokenize` 函数（Line 38-52）

```python
def _tokenize(text: str) -> list[str]:
    tokens = []
    for seg in re.split(r'[\s\n,.;:!?()（）【】""''—…·/\\|@#$%]+', text):
        if re.search(r'[一-鿿]', seg):  # 判断是否包含中文
            # 中文：生成 bigram（字+双字组合）
            for i in range(len(seg)):
                tokens.append(seg[i])       # 单字："定", "曲", "河"
                if i < len(seg) - 1:
                    tokens.append(seg[i:i+2])  # 双字："定曲", "曲河"
        elif len(seg) > 1:
            # 英文/数字：整词
            tokens.append(seg.lower())
    return tokens

# 示例：
text = "定曲河流域 2009050100 事件"
tokens = _tokenize(text)
# ["定", "定曲", "曲", "曲河", "河", "河流", "流", "流域", "域", "2009050100", "事", "事件", "件"]
```

**为什么用 bigram？**
- 平衡粒度：单字太细（"河"太常见），整词太粗（分词器不准）
- 提升召回：查询"定曲"能匹配包含"定曲河"的文档

---

### 2.5 混合检索（Hybrid Search）

**代码位置：** `knowledge/rag_engine.py` Line 185-209

```python
def hybrid_search(self, query: str, top_k: int = 5) -> list[Document]:
    n = top_k * 2  # 每路取10个候选（最终返回5个）
    
    # 路径1：FAISS 语义检索
    semantic = self.vectorstore.similarity_search_with_score(query, k=n)
    
    # 路径2：BM25 关键词检索
    q_tokens = _tokenize(query)
    bm25_scores = self.bm25.get_scores(q_tokens)
    bm25_ranked = sorted(enumerate(bm25_scores), key=lambda x: x[1], reverse=True)[:n]
    
    # RRF 融合（Reciprocal Rank Fusion）
    k = 60
    fused = {}
    for rank, (doc, _) in enumerate(semantic):
        idx = self._doc_index(doc)
        fused[idx] = fused.get(idx, 0) + 1.0 / (k + rank + 1)
    
    for rank, (idx, _) in enumerate(bm25_ranked):
        fused[idx] = fused.get(idx, 0) + 1.0 / (k + rank + 1)
    
    # 按融合分数排序
    ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)
    return [self.documents[i] for i, _ in ranked[:top_k]]
```

**RRF 算法原理：**

```
用户查询："定曲河2009050100事件降雨统计"

FAISS 语义检索结果：
  Rank 1: chunk_15（分数0.92）
  Rank 2: chunk_8 （分数0.88）
  Rank 3: chunk_3 （分数0.85）

BM25 关键词检索结果：
  Rank 1: chunk_8 （包含"2009050100"）
  Rank 2: chunk_15（包含"降雨统计"）
  Rank 3: chunk_22（包含"定曲河"）

RRF 融合计算：
  chunk_15: 1/(60+1) + 1/(60+2) = 0.0164 + 0.0161 = 0.0325
  chunk_8:  1/(60+2) + 1/(60+1) = 0.0161 + 0.0164 = 0.0325
  chunk_3:  1/(60+3) + 0       = 0.0159
  chunk_22: 0       + 1/(60+3) = 0.0159

最终排序：chunk_15 ≈ chunk_8 > chunk_3 ≈ chunk_22
```

**优势：**
- **互补性**：语义检索抓大意，关键词检索抓细节
- **鲁棒性**：一路失效，另一路兜底
- **公平性**：不依赖绝对分数，只看相对排序

---

## 三、存储结构

**目录结构：**
```
knowledge/
├── basins/
│   ├── dqh/              # 定曲河知识库源文件
│   │   ├── 流域概况.md
│   │   └── 站点说明.md
│   └── btpzh/            # 巴塘—攀枝花知识库
│       └── 区域特征.md
└── vector_store/
    ├── dqh_faiss/
    │   ├── index.faiss   # FAISS向量索引（二进制）
    │   └── index.pkl     # 文档元数据
    ├── dqh_bm25.pkl      # BM25索引+分词结果
    ├── btpzh_faiss/
    │   └── ...
    └── btpzh_bm25.pkl
```

**文件说明：**
- `index.faiss`：FAISS C++ 层的向量索引文件（~数MB）
- `index.pkl`：LangChain 的文档映射（Python pickle）
- `dqh_bm25.pkl`：包含 `{"documents": [...], "bm25": BM25Okapi对象, "tokenized": [...]}`

---

## 四、关键设计决策

### 4.1 为什么是 600 字符/块？

**实验对比：**

| chunk_size | 召回率 | 精确度 | tokens消耗 |
|-----------|--------|--------|-----------|
| 200       | 低     | 高     | 少        |
| 600       | **高** | **中** | **中**    |
| 1500      | 中     | 低     | 多        |

- 太小（200）：语义碎片化，上下文不足
- 太大（1500）：噪声多，向量表征不精确
- **600**：平衡点，约等于1-2个段落

### 4.2 为什么用 BGE 而非 OpenAI Embedding？

| 模型 | 维度 | 成本 | 私有化 | 中文效果 |
|------|------|------|--------|---------|
| OpenAI text-embedding-3-small | 1536 | $0.02/1M tokens | ❌ | 中 |
| **BAAI/bge-small-zh-v1.5** | 512 | **免费** | **✅** | **强** |

- BGE 针对中文优化，MTEB中文榜前列
- 本地部署，无API调用成本
- 离线可用，数据不出内网

### 4.3 为什么同时用 FAISS + BM25？

**单一检索的局限性：**

| 查询类型 | FAISS表现 | BM25表现 |
|---------|----------|----------|
| "定曲河流域特点" | ✅ 优秀（语义理解） | ⚠️ 一般（分词不精确） |
| "站点编号 dqh_C3" | ❌ 较差（数字无语义） | ✅ 优秀（精确匹配） |
| "2009050100 事件" | ❌ 较差（事件代码） | ✅ 优秀（关键词命中） |

**混合检索：** 1+1 > 2

---

## 五、技术栈对比

### 传统方案 vs 当前方案

| 维度 | 传统SQL检索 | ElasticSearch | **当前方案（FAISS+BM25）** |
|-----|-----------|---------------|--------------------------|
| 语义理解 | ❌ | ⚠️（需NLP插件） | ✅（BGE向量） |
| 精确匹配 | ✅ | ✅ | ✅（BM25） |
| 部署复杂度 | 低 | 高（Java依赖） | **低（纯Python）** |
| 成本 | 低 | 中 | **低（离线模型）** |
| 扩展性 | 低 | 高 | 中 |

---

## 六、使用示例

**Agent 工具调用：**
```python
from knowledge.rag_engine import get_rag

rag = get_rag()

# 查询
context = rag.search_with_context(
    query="定曲河流域有哪些站点？",
    basin_id="dqh",  # 可选，限定流域
    top_k=3
)

print(context)
# 输出：
# [来源：定曲河 — 站点说明.md chunk#2]
# 定曲河流域共有4个水文站点：
# - dqh_C1 古学
# - dqh_C2 得荣
# - dqh_C3 热打
# - dqh_C4 乡城
#
# ---
#
# [来源：定曲河 — 流域概况.md chunk#0]
# 定曲河位于金沙江上游...
```

**LLM 接收到的上下文：**
- Agent 自动将 `context` 拼接到 System Prompt
- LLM 基于检索到的 chunks 回答问题

---

## 七、核心代码索引

| 功能 | 文件 | 行号 | 说明 |
|-----|------|------|------|
| 文档切分 | `knowledge/rag_engine.py` | 120-140 | RecursiveCharacterTextSplitter |
| 向量化 | `knowledge/rag_engine.py` | 161 | FAISS.from_documents |
| 中文分词 | `knowledge/rag_engine.py` | 38-52 | bigram分词策略 |
| BM25索引 | `knowledge/rag_engine.py` | 164-167 | BM25Okapi构建 |
| 混合检索 | `knowledge/rag_engine.py` | 185-209 | RRF融合算法 |
| BGE模型封装 | `knowledge/rag_engine.py` | 57-84 | Sentence-Transformers |

---

**总结：不是逐字词向量化，而是将文档切分为600字的语义块，每个块生成一个512维向量，同时构建BM25关键词索引，检索时两路融合。**
