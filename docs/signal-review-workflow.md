# Signal Review Workflow — Human-in-the-Loop

本文档说明 Trend Scout Enterprise 的信号人工审核工作流（AI Agent × Human Hybrid Team 核心机制）。

## 1. 状态机

每个信号（`RawItem`）带有 `review_status` 字段，取值如下：

| 状态 | 含义 | 产生方式 |
|------|------|----------|
| `auto` | 未进入审核流（默认） | review 模式关闭时的所有信号 |
| `pending_review` | 等待人工审核 | review 模式开启后，AI 评分低于自动批准阈值 |
| `approved` | 已批准 | 人工 approve / override，或评分达到自动批准阈值 |
| `rejected` | 已拒绝 | 人工 reject |
| `flagged` | 已标记待关注 | 人工 flag |

## 2. 开启审核模式

```bash
export REVIEW_MODE_ENABLED=1
export HUMAN_REVIEW_THRESHOLD=0.4   # 低于此分数进人工队列
export AUTO_APPROVE_THRESHOLD=0.7   # 高于等于此分数自动批准
```

评分在 `[HUMAN_REVIEW_THRESHOLD, AUTO_APPROVE_THRESHOLD)` 区间的信号同样进入 `pending_review`（保守默认）。

关闭时（默认）系统行为与引入审核机制前完全一致，趋势聚合与报告均不受影响。

## 3. 分流逻辑

`services/scoring_service.py` 的 `score_item_with_llm` 在 LLM 评分完成后：

- review 模式关闭 → `review_status` 保持 `auto`
- review 模式开启：
  - `overall_score >= auto_approve_threshold` → `approved`
  - 否则 → `pending_review`，并按 `ReviewAssignment(workspace_id, category)` 自动填写 `assigned_reviewer_id`

## 4. API 端点

以下端点均要求 `X-API-Key` + `X-Workspace-ID`（embed token 只读，不可调用写端点）。

### 查询审核队列

```bash
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  "http://localhost:8000/api/v1/signals/review-queue?assigned_to_me=true&limit=50"
```

支持 `source_id`、`category`、`assigned_to_me`、`limit`、`offset` 过滤。

### 单个审核

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "notes": "high signal"}' \
  "http://localhost:8000/api/v1/signals/<id>/review"
```

`action` ∈ `approve | reject | flag | override`；`override` 必须同时提供 `human_score`（0–1）。

### 批量审核

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"item_ids": ["<id1>", "<id2>"], "action": "approve"}' \
  "http://localhost:8000/api/v1/signals/bulk-review"
```

返回 `{succeeded: [...], failed: [{id, error}]}` 明细。

### 评分反馈（用于模型迭代）

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"human_score": 0.9, "feedback_type": "score_too_low", "notes": "..."}' \
  "http://localhost:8000/api/v1/signals/<id>/feedback"
```

`feedback_type` 建议取值：`score_too_low` / `score_too_high` / `irrelevant` / `misclassified`，会持久化到 `signal_reviews.feedback_type`。

### 按状态过滤信号列表

```bash
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  "http://localhost:8000/api/v1/signals?review_status=rejected"
```

## 5. 趋势聚合适配

`POST /trends/aggregate` 接受 `only_approved: true`，聚合时只统计 `approved` 与 `auto` 状态的信号（`auto` 兼容 review 模式关闭的历史数据）。默认 `false`，行为与之前一致。

## 6. 前端

`Signals` 页面（左侧导航）提供：

- 状态过滤（All / Pending Review / Approved / Rejected / Flagged）
- 行内 Approve / Reject / Flag
- 详情面板：AI 各维度分数、元数据、Override Score、Feedback 表单
- 多选 + 批量 Approve / Reject

## 7. 审核分配

`review_assignments` 表按 `(workspace_id, category)` 指定审核人。分流时自动为 `pending_review` 信号填写 `assigned_reviewer_id`，前端/队列可用 `assigned_to_me=true` 只看分配给自己的任务。

## 8. 审计

所有 review / bulk-review / feedback 操作都会写入 `audit_logs` 表（action 分别为 `signal.review`、`signal.bulk_review`、`signal.feedback`），包含操作人、workspace、目标信号与详情。
