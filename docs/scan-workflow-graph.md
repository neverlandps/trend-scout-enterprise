# Scan Workflow Graph (LangGraph)

P2 阶段 3 将原先内联在 `workers/scan_worker.py` 中的线性扫描流水线重构为显式的
LangGraph `StateGraph`，位于 `backend/src/trend_scout_enterprise/workflows/scan_graph.py`。

## 工作流结构

```
START -> load_context --(errors 非空)--> finalize --> END          # fail 路径
                |
                +--> collect --(无信号)--> finalize --> END         # 空跑
                        |
                        +--> persist -> score -> embed -> finalize
                                                          |
                                              (status != failed) +--> notify --> END
```

### State（`ScanState`, TypedDict）

| 字段 | 含义 |
|---|---|
| `scan_run_id` | 扫描运行 ID（输入） |
| `source_id` / `workspace_id` | 由 `load_context` 填充 |
| `signals` | 采集到的 `RawSignal` 列表 |
| `new_item_ids` | 去重后新入库的 `RawItem` ID |
| `analyzed` / `failed_analysis` | LLM 评分统计 |
| `errors` | 累积错误（条目处理、分析失败等） |
| `status` | `pending` / `running` / `completed` / `completed_with_errors` / `failed` |

### 节点

每个节点是纯函数（接收 state、返回部分 state 更新），并在节点内自行获取/关闭
SQLAlchemy session（沿用原 worker 的 `_get_db` 模式），session 不跨节点。

1. **load_context** — 加载 `ScanRun` 与 `Source`，置 `running`；记录不存在则写
   `errors` 并路由到 `finalize`（fail 路径，不重试）。
2. **collect** — 解密 source config、`get_scanner`、`asyncio.run(scanner.scan())`。
   scanner 异常直接抛出，由 Celery 层标记 failed 并重试。
3. **persist** — 按 URL 去重写入 `RawItem`，产出 `new_item_ids`。
4. **score** — 复用 `analysis_service.analyze_signals_batch` 做 LLM 评分；review
   阈值分流仍在 `scoring_service._apply_review_routing` 内完成（低置信度置
   `review_status="pending_review"`）。LLM 未配置时跳过。
5. **embed** — `vector_search_enabled` 时生成 embedding（best-effort，失败不阻断）。
6. **finalize** — 更新 source 健康度与 scan_run 统计/状态
   （`completed` / `completed_with_errors` / `failed`）。
7. **notify** — `NotificationService` 通知（best-effort）；failed 的运行不通知，
   与原行为一致。

### 条件路由

- `load_context` 后：`errors` 非空 → `finalize`；否则 → `collect`
- `collect` 后：无信号或失败 → `finalize`；否则 → `persist`
- `score` 后固定走 `embed → finalize`；`finalize` 后仅非 failed 才 → `notify`

入口为 `run_scan_workflow(scan_run_id) -> dict`，单次 `graph.invoke()` 跑完全程，
返回与原 `run_scan` 任务兼容的结果 dict。

## 与 Celery 的关系

`workers/scan_worker.py` 的 `run_scan` 任务现在是薄壳：调用
`run_scan_workflow(scan_run_id)`，保留任务签名、`max_retries=3` 重试策略与失败
处理（scan_run 标记 `failed`、source 健康度更新、`self.retry`）。Celery 的
eager/testing 行为不变。图编排的是单次扫描的内部步骤；调度、排队、重试仍由
Celery 负责，二者职责分层。

## 后续演进：interrupt/resume

第一版刻意不做图内挂起：人工审核继续走数据库状态机（`RawItem.review_status`），
graph 单趟跑完，与 Celery fire-and-forget 模型无冲突。后续引入 interrupt/resume
的路径：

1. 为 graph 配置 checkpointer（如 Postgres saver），以 `scan_run_id` 作为
   thread id，使状态可持久化、可恢复。
2. 在 `score` 之后插入 `interrupt` 节点（或条件挂起点），将待审批次挂起；
   人工审核 API 通过 `Command(resume=...)` 唤醒对应 thread。
3. Celery 任务需区分"跑到挂起点正常结束"与"异常失败"，避免对挂起的运行误重试。
4. 该基础之上可进一步把 `score`/`collect` 拆分为多 Agent 协作节点。
