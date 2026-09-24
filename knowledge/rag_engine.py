"""
RAG 知识检索引擎 — 语义向量 + BM25 关键词 + RRF 融合

Embedding 模型：BAAI/bge-small-zh-v1.5（sentence-transformers，~84MB，纯 CPU）
检索策略：FAISS 向量检索 Top-K + BM25 关键词 Top-K → RRF(k=60) 融合排序

技术特点：
  - sentence-transformers 语义向量
  - 向量维度 512（bge-small-zh-v1.5），余弦相似度
  - 模型首次运行自动下载缓存，离线后复用
"""

import os
import pickle
import re
import shutil
import tempfile

import numpy as np
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters.character import RecursiveCharacterTextSplitter
from rank_bm25 import BM25Okapi

# 延迟导入 sentence_transformers 避免启动时加载 torch
_sentence_transformer = None

def _get_sentence_transformer():
    global _sentence_transformer
    if _sentence_transformer is None:
        from sentence_transformers import SentenceTransformer
        _sentence_transformer = SentenceTransformer
    return _sentence_transformer

VECTOR_STORE_DIR = os.path.join(os.path.dirname(__file__), "vector_store")
MODEL_NAME = "BAAI/bge-small-zh-v1.5"

BASIN_NAME_MAP = {
    "dqh": "定曲河",
    "btpzh": "巴塘—攀枝花",
}


# ─── 分词（BM25 用）──────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    """中文 bigram + 英文词分词，用于 BM25 索引"""
    tokens: list[str] = []
    for seg in re.split(r'[\s\n,.;:!?()（）【】""''—…·/\\|@#$%]+', text):
        seg = seg.strip()
        if not seg:
            continue
        if re.search(r'[一-鿿]', seg):
            for i in range(len(seg)):
                tokens.append(seg[i])
                if i < len(seg) - 1:
                    tokens.append(seg[i:i + 2])
        elif len(seg) > 1:
            tokens.append(seg.lower())
    return tokens


# ─── Sentence-Transformers Embedding 包装 ────────────────────

class BGEEmbeddings(Embeddings):
    """
    基于 BAAI/bge-small-zh-v1.5 的中文语义向量化。
    向量维度 512，余弦相似度，纯 CPU 运行。
    首次调用自动下载模型（~84MB）并缓存到 ~/.cache/huggingface。
    """

    def __init__(self, model_name: str = MODEL_NAME):
        SentenceTransformer = _get_sentence_transformer()
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(
            texts,
            normalize_embeddings=True,  # bge 官方建议归一化
            show_progress_bar=False,
            batch_size=32,
        )
        return vecs.tolist()

    def embed_query(self, text: str) -> list[float]:
        # bge 检索时 query 加前缀可提升效果
        prefixed = f"为这个句子生成表示以用于检索相关文章：{text}"
        vec = self._model.encode(
            prefixed,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vec.tolist()


# ─── 单流域知识库 ────────────────────────────────────────────

class BasinKnowledgeBase:
    """单个流域：FAISS 向量索引 + BM25 关键词索引"""

    def __init__(self, basin_id: str, basin_name: str, embeddings: BGEEmbeddings):
        self.basin_id = basin_id
        self.basin_name = basin_name
        self.doc_dir = os.path.join(os.path.dirname(__file__), "basins", basin_id)
        self.faiss_dir = os.path.join(VECTOR_STORE_DIR, f"{basin_id}_faiss")
        self.bm25_path = os.path.join(VECTOR_STORE_DIR, f"{basin_id}_bm25.pkl")
        self.embeddings = embeddings
        self.vectorstore: FAISS | None = None
        self.bm25: BM25Okapi | None = None
        self.documents: list[Document] = []
        # 哈希索引：page_content 的 id() → documents 下标，加速 _doc_index()
        self._content_index: dict[int, int] = {}

    def _build_content_index(self) -> None:
        self._content_index = {id(d.page_content): i for i, d in enumerate(self.documents)}

    def _doc_index(self, doc: Document) -> int | None:
        """O(1) 查找 doc 在 documents 列表中的位置"""
        idx = self._content_index.get(id(doc.page_content))
        if idx is not None:
            return idx
        # 回退：内容相等匹配（首次加载后 page_content str 可能不同对象）
        for i, d in enumerate(self.documents):
            if d.page_content == doc.page_content:
                self._content_index[id(doc.page_content)] = i
                return i
        return None

    def load_documents(self) -> list[Document]:
        docs: list[Document] = []
        if not os.path.exists(self.doc_dir):
            return docs
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=600,
            chunk_overlap=80,
            separators=["\n## ", "\n### ", "\n", "。", ".", " "],
        )
        for fname in sorted(os.listdir(self.doc_dir)):
            if not fname.endswith(".md"):
                continue
            with open(os.path.join(self.doc_dir, fname), encoding="utf-8") as f:
                content = f.read()
            for i, chunk in enumerate(splitter.split_text(content)):
                docs.append(Document(
                    page_content=chunk,
                    metadata={"basin_id": self.basin_id, "basin_name": self.basin_name,
                               "source": fname, "chunk_id": i},
                ))
        return docs

    def build_or_load(self, force_rebuild: bool = False) -> None:
        os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
        os.makedirs(self.faiss_dir, exist_ok=True)
        sentinel = os.path.join(self.faiss_dir, "index.faiss")

        if not force_rebuild and os.path.exists(sentinel) and os.path.exists(self.bm25_path):
            self.vectorstore = self._load_faiss_safe()
            with open(self.bm25_path, "rb") as f:
                data = pickle.load(f)
                self.documents = data["documents"]
                self.bm25 = data["bm25"]
            self._build_content_index()
            return

        docs = self.load_documents()
        if not docs:
            return
        self.documents = docs
        print(f"  [{self.basin_id}] 向量化 {len(docs)} chunks…")
        self.vectorstore = FAISS.from_documents(docs, self.embeddings)
        self._save_faiss_safe()

        tokenized = [_tokenize(d.page_content) for d in docs]
        self.bm25 = BM25Okapi(tokenized)
        with open(self.bm25_path, "wb") as f:
            pickle.dump({"documents": docs, "bm25": self.bm25, "tokenized": tokenized}, f)
        self._build_content_index()

    def _save_faiss_safe(self) -> None:
        """通过英文临时目录中转，规避 FAISS C++ 层中文路径问题"""
        with tempfile.TemporaryDirectory() as tmp:
            self.vectorstore.save_local(tmp)
            for fn in os.listdir(tmp):
                shutil.copy2(os.path.join(tmp, fn), os.path.join(self.faiss_dir, fn))

    def _load_faiss_safe(self) -> FAISS:
        with tempfile.TemporaryDirectory() as tmp:
            for fn in os.listdir(self.faiss_dir):
                shutil.copy2(os.path.join(self.faiss_dir, fn), os.path.join(tmp, fn))
            return FAISS.load_local(
                tmp, self.embeddings, allow_dangerous_deserialization=True
            )

    def hybrid_search(self, query: str, top_k: int = 5) -> list[Document]:
        if not self.vectorstore or not self.documents:
            return []
        n = min(top_k * 2, len(self.documents))

        # FAISS 语义检索
        semantic = self.vectorstore.similarity_search_with_score(query, k=n)

        # BM25 关键词检索
        q_tokens = _tokenize(query)
        bm25_scores = self.bm25.get_scores(q_tokens) if self.bm25 else []
        bm25_ranked = sorted(enumerate(bm25_scores), key=lambda x: x[1], reverse=True)[:n]

        # RRF 融合 (k=60)
        k = 60
        fused: dict[int, float] = {}
        for rank, (doc, _) in enumerate(semantic):
            idx = self._doc_index(doc)
            if idx is not None:
                fused[idx] = fused.get(idx, 0) + 1.0 / (k + rank + 1)
        for rank, (idx, _) in enumerate(bm25_ranked):
            fused[idx] = fused.get(idx, 0) + 1.0 / (k + rank + 1)

        ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)
        return [self.documents[i] for i, _ in ranked[:top_k]]


# ─── 多流域 RAG ──────────────────────────────────────────────

class MultiBasinRAG:
    def __init__(self):
        self._embeddings = BGEEmbeddings()
        self.basins: dict[str, BasinKnowledgeBase] = {
            bid: BasinKnowledgeBase(bid, bname, self._embeddings)
            for bid, bname in BASIN_NAME_MAP.items()
        }

    def build_all(self, force_rebuild: bool = False) -> None:
        for kb in self.basins.values():
            kb.build_or_load(force_rebuild)

    def search(self, query: str, basin_id: str | None = None, top_k: int = 5) -> list[Document]:
        targets = {basin_id: self.basins[basin_id]} if (basin_id and basin_id in self.basins) else self.basins
        results: list[Document] = []
        for kb in targets.values():
            results.extend(kb.hybrid_search(query, top_k))
        return results[:top_k]

    def search_with_context(self, query: str, basin_id: str | None = None, top_k: int = 5) -> str:
        docs = self.search(query, basin_id, top_k)
        if not docs:
            return ""
        parts = []
        for doc in docs:
            src = doc.metadata.get("source", "未知")
            basin = doc.metadata.get("basin_name", "")
            parts.append(
                f"[来源：{basin} — {src} chunk#{doc.metadata.get('chunk_id', '')}]\n{doc.page_content}"
            )
        return "\n\n---\n\n".join(parts)


_rag_instance: MultiBasinRAG | None = None


def get_rag(force_rebuild: bool = False) -> MultiBasinRAG:
    global _rag_instance
    if _rag_instance is None or force_rebuild:
        _rag_instance = MultiBasinRAG()
        _rag_instance.build_all(force_rebuild)
    return _rag_instance
