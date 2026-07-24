# Vector Search（语义检索）

Trend Scout Enterprise 的语义检索能力：为采集到的信号（RawItem）生成 embedding 向量，支持相似信号发现与语义搜索，为后续去重聚类和 RAG 增强打基础。

## 方案概述

第一版**不引入 pgvector**，采用方言无关方案：

- embedding 向量以 JSON float 列表存储在 `signal_embeddings` 表（SQLite / PostgreSQL 均可）；
- 余弦相似度用纯 Python 计算（`services/embedding_service.py` 的 `cosine_similarity` / `top_k_similar`）；
- embedding 来源复用现有 LLM Provider 配置，调用 OpenAI 兼容的 `POST {base_url}/embeddings` 端点，并沿用 LlmService 的 fallback provider chain。

### 性能边界与 pgvector 演进路径

纯 Python 全表扫描在**万级以下信号量**时性能可接受（每次检索 O(N×D)，N 为向量数、D 为维度）。当单 workspace 信号量超过数万、或检索延迟成为瓶颈时，演进路径为：

1. PostgreSQL 上启用 pgvector，将 `embedding` 列迁移为 `vector(D)` 类型并建 ANN 索引（IVFFlat / HNSW）；
2. `top_k_similar` 替换为 `ORDER BY embedding <=> :query LIMIT k` 的 SQL 查询；
3. API 层（`SimilarSignalOut` / `SemanticSearchOut`）保持不变，调用方无感。

代码中相关位置均有注释标注该演进点。

## 配置

环境变量（`core/config.py`）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `VECTOR_SEARCH_ENABLED` | `false` | 功能开关。关闭时扫描不生成 embedding，检索 API 返回 503 |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | 传给 `/embeddings` 端点的模型名 |

embedding 使用默认 LLM Provider（`llm_providers.is_default = true`）的 `base_url` / API key，fallback provider chain 同样生效。无需为 embedding 单独配置 endpoint。

数据表通过 alembic migration `006_signal_embeddings` 创建（防御式：表已存在则跳过）。

## 扫描流程集成

`workers/scan_worker.py` 在 LLM 评分完成后，若 `VECTOR_SEARCH_ENABLED=true` 且 LLM service 可用，会对本次新采集的信号调用 `EmbeddingService.generate_for_items` 生成 embedding。embedding 失败**不会阻断扫描**，仅记录 structlog warning（`scan_embedding_failed`）。重复扫描不会重复生成（已有 embedding 的信号跳过，幂等）。

embedding 输入文本为 `title + "\n" + summary`，截断至 8000 字符；每 API 请求最多批量 32 条。

## API

两个端点均为只读，沿用统一认证（API key 或会话），结果限定在当前 workspace 内。

### 相似信号

```bash
curl -H "X-API-Key: $KEY" \
  "http://localhost:8000/api/v1/signals/{signal_id}/similar?limit=10"
```

返回与该信号余弦相似度最高的其他信号（排除自身），按相似度降序：

```json
[
  {"signal": {"id": "...", "title": "...", "...": "..."}, "similarity": 0.83}
]
```

- 信号无 embedding → `404`（提示先开启开关运行扫描）；
- 开关关闭 → `503`。

### 语义搜索

```bash
curl -H "X-API-Key: $KEY" \
  "http://localhost:8000/api/v1/signals/semantic-search?q=small+modular+reactor&limit=20"
```

将 query 文本做 embedding 后与库内向量计算相似度，返回 top-K：

```json
{
  "query": "small modular reactor",
  "results": [
    {"signal": {"id": "...", "title": "...", "...": "..."}, "similarity": 0.79}
  ]
}
```

- query 为空 → `400`；开关关闭 → `503`；未配置默认 LLM Provider → `503`。

## 测试

`backend/tests/test_vector_search.py` 覆盖：余弦相似度正确性、`embed_texts` 成功路径与 32 条批量切分、`generate_for_items` 幂等、similar 端点排序/排除自身/404/503、semantic-search top-K、跨 workspace 隔离。
