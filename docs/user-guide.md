# Trend Scout Enterprise v1.0 用户手册

本文档面向**业务用户（分析师 / 查看者）**与**管理员**，覆盖 Trend Scout Enterprise v1.0 的全部日常使用与运维操作。每个功能点均给出：操作路径（页面 / 按钮）、等价的 API curl 示例、注意事项。

约定：

- API 基础地址以 `http://localhost:8000` 为例，所有业务端点前缀为 `/api/v1`。
- curl 示例中 `$KEY` 为你的 API Key，`$WS` 为工作空间 ID：
  ```bash
  export KEY="tse_xxxxxxxx"
  export WS="<workspace-id>"
  export BASE="http://localhost:8000/api/v1"
  ```
- 绝大多数端点需要请求头 `X-API-Key: $KEY`；写操作还需要 `X-Workspace-ID: $WS`。只读端点在配置了会话或统一鉴权时可省略 `X-Workspace-ID`（此时使用默认工作空间）。
- 交互式 API 文档（Swagger UI）位于 `http://localhost:8000/docs`，可直接在线试调。

---

## 1. 快速上手

### 1.1 登录

**操作路径**：打开前端（本地开发默认 `http://localhost:5173`），进入登录页。两种登录方式：

1. **API Key 登录**（默认方式）：在「API Key」输入框粘贴你的密钥，点击 **Enter with API Key**。登录后自动跳转到 Sources 页面。
2. **Microsoft 登录**：点击 **Login with Microsoft**，跳转到 Microsoft Entra ID 完成 OAuth2 授权后回跳（需管理员先在服务端配置 Entra ID，见 §11）。

**API 等价**：API Key 方式没有"登录接口"，前端只是把 Key 存入浏览器并作为 `X-API-Key` 请求头发送。验证 Key 是否有效：

```bash
curl -H "X-API-Key: $KEY" "$BASE/workspaces"
```

**注意事项**：

- API Key 由管理员在 Team 页面创建（见 §8），**明文只显示一次**，丢失只能重新邀请。
- API Key 存储在浏览器本地，公共电脑上使用完请退出并清理。

### 1.2 工作空间切换

工作空间（Workspace）是数据隔离的基本单位：数据源、信号、趋势、报告、审核队列全部按工作空间隔离。

**操作路径**：页面顶部的**工作空间选择器**（WorkspaceSelector 下拉框）切换当前工作空间。切换后所有页面数据随之刷新。

**API 等价**：

```bash
# 列出我可访问的工作空间
curl -H "X-API-Key: $KEY" "$BASE/workspaces"

# 校验并切换到指定工作空间
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"workspace_id": "'$WS'"}' "$BASE/workspaces/switch"

# 之后所有请求带上 X-Workspace-ID
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/sources"
```

**注意事项**：纯 API 调用没有"会话态"，切换工作空间 = 在后续请求中更换 `X-Workspace-ID` 头的值。

### 1.3 界面导览

左侧导航共 7 个页面：

| 页面 | 用途 |
|------|------|
| **Sources** | 管理数据源（增删改、查看健康状态与修复建议） |
| **Scans** | 手动触发扫描、查看扫描运行历史与失败原因 |
| **Signals** | 浏览信号、审核队列（Approve / Reject / Flag / Override / Feedback）、批量审核 |
| **Reports** | 选择信号生成 PDF / PPTX / Card 报告并下载 |
| **Trends** | 趋势聚合、折线图对比、点击数据点追溯证据链 |
| **Settings** | LLM Provider、评分维度权重、SharePoint Online 连接配置 |
| **Team** | 团队成员邀请（创建 API Key）、角色管理 |

健康检查（无需认证）：

```bash
curl "$BASE/health"   # {"status": "ok", "service": "trend-scout-enterprise"}
```

---

## 2. 配置数据源

系统支持 5 种数据源类型（`source_type`）：`rss`、`arxiv`、`web_search`、`custom_api`、`sharepoint_list`。

**操作路径**：**Sources** 页面 → 右上角 **Add Source** → 在弹出面板中填写：

- **Name**：数据源名称；
- **Type**：上述 5 种类型之一；
- **Config (JSON)**：该类型的配置 JSON（见下文逐项说明）；
- **Category**：业务分类（如 `energy`、`ai`），趋势聚合与审核分配按 category 进行，建议必填。

编辑：点击源卡片上的铅笔图标；删除：点击垃圾桶图标（需确认）。

**API 等价**：

```bash
# 查询支持的扫描器类型
curl -H "X-API-Key: $KEY" "$BASE/sources/scanner-types"

# 创建数据源
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"name": "示例源", "source_type": "rss", "category": "energy", "config": {"url": "https://example.com/feed.xml"}}' \
  "$BASE/sources"

# 更新 / 删除
curl -X PUT  -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" -H "Content-Type: application/json" -d '{"category": "ai"}' "$BASE/sources/<source_id>"
curl -X DELETE -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/sources/<source_id>"
```

**通用注意事项**：

- config 中的敏感字段（如 `api_key`）在服务端**加密存储**，读取时会做脱敏处理。
- 除 `sharepoint_list` 外，所有类型创建时都要求 config 中包含 `url` 字段（服务端强制校验）。
- 扫描器默认不允许访问内网 / 回环地址（SSRF 防护）；仅在开发环境可通过 `SSRF_ALLOW_PRIVATE=true` 放开。

### 2.1 RSS（`rss`）

订阅 RSS / Atom  feed。

```json
{
  "url": "https://example.com/feed.xml"
}
```

只需填 `url`。系统抓取 feed 并解析每条 entry 的标题、摘要、链接与发布时间。

### 2.2 arXiv（`arxiv`）

按 arXiv 检索式抓取最新论文，按提交日期倒序。

```json
{
  "url": "http://export.arxiv.org/api/query",
  "query": "cat:cs.AI",
  "max_results": 10
}
```

- `query`：arXiv 检索语法（如 `cat:cs.AI`、`all:"small modular reactor"`），缺省 `cat:cs.AI`；
- `max_results`：单次最多抓取条数，缺省 10；
- **`url` 注意事项**：扫描器实际固定调用 `http://export.arxiv.org/api/query`，`query` 只作为请求参数；但服务端创建校验要求 config 必须含 `url` 字段，因此请按示例填上 arXiv API 地址（该值不被扫描器使用）。

### 2.3 Web Search（`web_search`）

通过通用搜索 API 按关键词检索网页。

```json
{
  "url": "https://api.search.example.com/v1/search",
  "query": "hydrogen electrolyzer market",
  "api_key": "sk-search-xxx",
  "max_results": 10
}
```

- `url`：搜索 API 端点（系统以 `GET {url}?q=<query>&limit=<max_results>` 调用，带 `Authorization: Bearer <api_key>`）；
- 返回体需包含 `results` 或 `items` 数组，元素取 `url`/`link`、`title`、`snippet`/`summary` 字段；
- `api_key` 可选，加密存储。

### 2.4 Custom API（`custom_api`）

对接任意返回 JSON 的 REST 接口，是最灵活的类型。

```json
{
  "url": "https://internal.example.com/api/articles",
  "method": "GET",
  "headers": {"X-Tenant": "rd"},
  "api_key": "sk-internal-xxx",
  "body": null,
  "timeout": 30,
  "response_path": "data.items",
  "field_mapping": {
    "url": "link",
    "title": "headline",
    "summary": "abstract",
    "published_at": "pub_date"
  }
}
```

字段详解：

| 字段 | 说明 |
|------|------|
| `url` | API 端点（必填） |
| `method` | HTTP 方法，缺省 `GET`；`POST`/`PUT`/`PATCH` 时以 `body` 作为 JSON 请求体 |
| `headers` | 自定义请求头字典，可选 |
| `api_key` | 可选，自动加为 `Authorization: Bearer` 头，加密存储 |
| `body` | POST/PUT/PATCH 的 JSON 请求体，可选 |
| `timeout` | 超时秒数，缺省 30 |
| `response_path` | **点分路径**，从响应 JSON 根定位到结果数组。例如响应为 `{"data": {"items": [...]}}` 时填 `data.items`；不填表示响应根就是数组（或单个对象） |
| `field_mapping` | 把结果数组元素的字段名映射到信号字段，支持 4 个键：`url`、`title`、`summary`、`published_at`。值是**响应中的字段名**；不映射的键使用同名缺省（如响应里本来就叫 `title` 就不用配） |

`published_at` 支持 ISO 8601 字符串（含 `Z` 后缀）或 Unix 时间戳。

### 2.5 SharePoint 列表（`sharepoint_list`）

扫描 SharePoint Online 列表项（取 `Title`/`Description`/`Link`/`Created` 字段）。

```json
{
  "connection_id": "<sharepoint-connection-id>"
}
```

- 只需填 `connection_id`，指向 **Settings 页面 SharePoint Online 区块**中已建好的连接（见 §9.4）；
- 连接被禁用（`is_enabled=false`）或不存在时扫描报错；
- 不需要也不接受 `url` 字段。

### 2.6 健康状态与 suggested_fix

每个数据源卡片显示健康状态：

- `healthy`（绿）：最近一次扫描成功；
- `unhealthy`（红）：最近一次扫描失败，下方同时显示 `last_failure_reason`（失败原因）与蓝色的 `Fix: ...`（**suggested_fix** 修复建议）；
- `unknown`（灰）：尚未扫描过。

`suggested_fix` 是系统按源类型生成的排障提示（附原始错误），例如：

| 源类型 | 建议含义 |
|--------|----------|
| rss | 检查 feed URL 可达性、是否为合法 XML/Atom、HTTPS 证书与认证头 |
| arxiv | 检查检索式语法与到 export.arxiv.org 的网络连通性 |
| web_search | 检查搜索端点、query 参数与 API Key / 计费状态 |
| custom_api | 检查 URL、method、headers、response_path、field_mapping |
| sharepoint_list | 检查连接是否启用、Graph API 权限、列表 ID / 站点 URL |

**API 等价**：

```bash
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/sources/<source_id>/health"
```

---

## 3. 扫描与监控

### 3.1 手动触发扫描

**操作路径**：**Scans** 页面 → 每个数据源卡片右侧的 **Scan Now** 按钮。触发后扫描进入 Celery 队列异步执行。

**API 等价**：

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"source_id": "<source_id>"}' "$BASE/scans"
```

返回 `202 Accepted` 与一条 `status=pending` 的扫描记录。

**注意事项**：触发接口限速 **10 次/分钟**；扫描是异步的，返回 pending 不代表已完成。

### 3.2 定时调度（cron）

**操作路径**：当前版本前端未提供调度配置界面，请通过 API 创建（同一 source 重复 POST 会更新已有调度）。

**API 等价**：

```bash
# 创建/更新调度：每天 09:00 UTC
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"source_id": "<source_id>", "cron_expression": "0 9 * * *", "timezone": "UTC", "is_enabled": true}' \
  "$BASE/schedules"

# 列出 / 删除调度
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/schedules"
curl -X DELETE -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/schedules/<schedule_id>"
```

cron 表达式为 5 段式 `分 时 日 月 周`，常用示例：

| 表达式 | 含义 |
|--------|------|
| `0 9 * * *` | 每天 09:00（默认值） |
| `*/30 * * * *` | 每 30 分钟 |
| `0 8 * * 1` | 每周一 08:00 |
| `0 9 1 * *` | 每月 1 日 09:00 |

**注意事项**：`timezone` 缺省 `UTC`，注意与本地时区的换算；调度由 Celery beat 执行，部署时需确保 beat 进程在运行（Docker Compose 栈默认包含）。

### 3.3 扫描状态解读

**Scans** 页面下方「Recent Scan Runs」按时间倒序列出每次运行：

- 状态颜色：`completed`（绿）、`failed`（红）、其他（如 `pending`/`running`，橙色）；
- 统计行：`Collected`（抓取条数）、`New`（新入库条数）、`Analyzed`（完成 LLM 评分条数）、`Failed`（失败条数）；
- 失败时显示红色 `error_log` 明细与蓝色 `Fix:` 建议。

**API 等价**：

```bash
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/scans"
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/scans/<scan_id>"
```

### 3.4 失败排查

1. 看 Scans 页面的 `error_log` 与 `Fix:` 建议；
2. 到 Sources 页面确认该源健康状态与 `last_failure_reason`；
3. 常见问题对照 §12 FAQ（网络不可达、SSRF 拦截、LLM 未配置、SharePoint 连接失效等）；
4. `Analyzed` 为 0 但 `Collected` 正常：通常是 LLM Provider 未配置或调用失败（§9.1、§12）。

---

## 4. 信号审核工作流（Human-in-the-Loop）

### 4.1 开启 review 模式

review 模式由**服务端环境变量**控制（需管理员设置并重启后端）：

```bash
export REVIEW_MODE_ENABLED=1
export HUMAN_REVIEW_THRESHOLD=0.4   # 人工审核分数带下界
export AUTO_APPROVE_THRESHOLD=0.7   # 达到此分数自动批准
```

分流逻辑（LLM 评分完成后）：

- review 模式关闭（默认）：所有信号 `review_status = auto`，不进入审核流；
- review 模式开启：
  - `overall_score >= AUTO_APPROVE_THRESHOLD` → 自动 `approved`；
  - 其余 → `pending_review` 进入人工审核队列，并按 `review_assignments`（按 workspace + category 配置的审核人）自动填写 `assigned_reviewer_id`。

状态机：`auto`（未入审核流）→ `pending_review`（待审）→ `approved` / `rejected` / `flagged`。

**注意事项**：`HUMAN_REVIEW_THRESHOLD` 为保留字段，当前版本分流只看 `AUTO_APPROVE_THRESHOLD`（低于它即进队列，保守默认）。

### 4.2 审核队列使用

**操作路径**：**Signals** 页面 → 顶部 Pivot 选项卡：**All / Pending Review / Approved / Rejected / Flagged**（默认打开 Pending Review）。

- 列表列：Title、Source、Score（overall_score）、Status 徽章、Actions；
- `pending_review` 行内直接显示 **Approve / Reject / Flag** 按钮；
- 点击任意行打开详情面板。

**API 等价**：

```bash
# 审核队列（支持 source_id / category / assigned_to_me / limit / offset）
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  "$BASE/signals/review-queue?assigned_to_me=true&limit=50"
```

`assigned_to_me=true` 只看分配给自己的审核任务。

### 4.3 Approve / Reject / Flag / Override Score

行内操作（无需打开详情）：

- **Approve**：批准，状态 → `approved`；
- **Reject**：拒绝，状态 → `rejected`（不会进入 `only_approved` 的趋势聚合）；
- **Flag**：标记待关注，状态 → `flagged`（保留在视野内但不算批准）。

**Override Score**（改分并批准）：打开详情面板 → 「Override Score」区块 → 填 Human score（0–1）与 Notes → **Submit Override**。提交后状态变为 `approved`，并记录 `human_score`。

**API 等价**：

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"action": "approve", "notes": "high signal"}' \
  "$BASE/signals/<signal_id>/review"

# override 必须带 human_score（0-1）
curl -X POST ... -d '{"action": "override", "human_score": 0.85, "notes": "..."}' \
  "$BASE/signals/<signal_id>/review"
```

`action` ∈ `approve | reject | flag | override`；`override` 缺 `human_score` 会返回 400。

### 4.4 批量审核

**操作路径**：Signals 页面勾选多行 → 列表上方的 **Bulk Approve (n)** / **Bulk Reject (n)**。完成后页面顶部显示成功/失败明细。

**API 等价**：

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"item_ids": ["<id1>", "<id2>"], "action": "approve"}' \
  "$BASE/signals/bulk-review"
```

返回 `{"succeeded": [...], "failed": [{"id": ..., "error": ...}]}`，部分失败不影响其他条目。

### 4.5 反馈提交（Feedback）

用于模型迭代：告诉系统 AI 评分哪里不对。

**操作路径**：详情面板 → 「Feedback」区块 → 填 Human score（0–1）、选择 Feedback type、填 Notes → **Submit Feedback**。

`feedback_type` 各值含义：

| 值 | 含义 |
|----|------|
| `score_too_low` | AI 打分偏低（前端选项之一） |
| `score_too_high` | AI 打分偏高 |
| `irrelevant` | 该信号与业务无关 |
| `misclassified` | 分类错误（API 可用，前端暂无此选项） |

**API 等价**：

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"human_score": 0.9, "feedback_type": "score_too_low", "notes": "..."}' \
  "$BASE/signals/<signal_id>/feedback"
```

**注意事项**：feedback 不改变 `review_status`，只更新 `human_score` 并写入一条 `status=feedback` 的审核记录。

### 4.6 审核分配（管理员）

`review_assignments` 表按 `(workspace_id, category)` 指定审核人。分流产生 `pending_review` 信号时，系统按数据源的 category 自动填入 `assigned_reviewer_id`；审核人用 `assigned_to_me=true` 过滤自己的队列，详情面板也会显示 Assigned reviewer。

**注意事项**：v1.0 的分配记录通过数据库/API 层维护（暂无专门的前端配置界面）；未配置分配时信号仍会进队列，只是 `assigned_reviewer_id` 为空，所有人可见。

### 4.7 审计

所有 review / bulk-review / feedback 操作都写入 `audit_logs`（action 分别为 `signal.review`、`signal.bulk_review`、`signal.feedback`），见 §11.3。

---

## 5. 信号浏览与检索

### 5.1 按分数 / 状态过滤

**操作路径**：Signals 页面 Pivot 按状态过滤（见 §4.2）。按分数过滤请用 API：

```bash
# overall_score >= 0.6，分页 limit/offset
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  "$BASE/signals?min_score=0.6&review_status=approved&limit=100&offset=0"

# 单条详情（含 5 个维度分数、human_score、metadata）
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/signals/<signal_id>"
```

详情面板展示：URL（可点击打开原文）、Source、采集时间、AI 摘要、**Scores** 区块（Overall + 5 个维度 + Human score）、原始 metadata。

### 5.2 语义搜索

需管理员开启 `VECTOR_SEARCH_ENABLED=true`（§11.1），并配置默认 LLM Provider。

**API 等价**：

```bash
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  "$BASE/signals/semantic-search?q=small+modular+reactor&limit=20"
```

将查询文本做 embedding，与库内信号向量做余弦相似度排序，返回 top-K 及相似度分值。

### 5.3 相似信号发现

```bash
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  "$BASE/signals/<signal_id>/similar?limit=10"
```

返回与该信号最相似的其他信号（排除自身），按相似度降序。适合找同主题信号、人工去重。

**注意事项**：

- 功能开关关闭 → 503；信号尚无 embedding → 404（提示先开开关跑一次扫描）；
- 存量信号没有 embedding 时用回填命令补齐（§11.4）；
- v1.0 前端未提供语义搜索输入框，需通过 API 调用。

### 5.4 手动重新分析

对选中信号重新触发 LLM 分析：

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"item_ids": ["<id1>", "<id2>"]}' "$BASE/signals/analyze"
```

---

## 6. 趋势分析

### 6.1 聚合操作与粒度选择

**操作路径**：**Trends** 页面 → 顶部控制区选择 **Category / Topic / Granularity / Start / End** → 点击 **Aggregate**（触发聚合）→ 再点 **Load Series**（加载折线图，Aggregate 成功后页面会自动加载一次）。

- **Granularity**：`day` / `week`（默认）/ `month`，即时间分桶粒度；
- 聚合把每个（category, topic, 时间桶）内信号的 `overall_score` 求平均，生成趋势点并保存 top 证据（缺省每桶 5 条，可通过 API 的 `top_evidence_count` 调到 1–20）。

**API 等价**：

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"category": "energy", "granularity": "week", "start_date": "2026-01-01", "end_date": "2026-07-01", "only_approved": true}' \
  "$BASE/trends/aggregate"
```

### 6.2 图表解读

- 折线图 Y 轴为平均分（0–1），X 轴为时间桶；多条线对应不同 topic / category 对比；
- 选择 Topic 后只画该 topic；不选时画整体序列；API 还支持 `compare_topics` 多主题对比：

```bash
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  "$BASE/trends/series?category=energy&compare_topics=smr&compare_topics=hydrogen&granularity=week"
```

- 辅助接口：列出有趋势数据的分类与主题：

```bash
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/trends/categories"
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/trends/topics?category=energy"
```

### 6.3 点击数据点查看证据链

**操作路径**：点击折线图任意数据点 → 右侧弹出 **Evidence** 面板，显示该趋势点的 Category、信号条数、平均分，以及证据表（Rank、证据标题【可点击打开原文】、Source、Score、Rationale【LLM 评分理由】）。

每个趋势点都可追溯到原始信号与 LLM 评分理由，这是审计与汇报时的关键能力。

**API 等价**：

```bash
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  "$BASE/trends/points/<trend_point_id>/evidence"
```

### 6.4 only_approved 选项

`POST /trends/aggregate` 的 `only_approved: true` 表示聚合时只统计 `approved` 与 `auto` 状态的信号（`auto` 兼容 review 模式关闭时的历史数据），`pending_review` / `rejected` / `flagged` 不计入。缺省 `false`，统计全部已评分信号。

**注意事项**：前端 Aggregate 按钮未暴露该选项，需走 API；开启 review 模式后建议用 `only_approved=true` 产出"已确认"趋势。

### 6.5 TrendAnalystAgent（可选）

设置 `TREND_ANALYST_ENABLED=true` 后，聚合时每个时间桶会额外调用 TrendAnalystAgent（LLM）生成高管摘要，写入趋势点的 `summary` 字段。会增加 LLM 调用量，按需开启。

---

## 7. 报告生成

### 7.1 三种格式与生成流程

**操作路径**：**Reports** 页面 →

1. 「Select Signals」列表勾选要纳入报告的信号（显示标题与分数）；
2. 填 **Report Title**（可空）；
3. 选择格式按钮：**PDF** / **PPTX** / **Card**（HTML 卡片报告）；
4. 点击 **Generate PDF/PPTX/CARD Report**（未勾选信号时按钮禁用）。

报告在后台异步生成（Celery），期间下方「Generated Reports」中该条状态为 `generating`，完成后变为 `completed`。

**API 等价**：

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"title": "Q3 能源趋势", "report_type": "pdf", "item_ids": ["<id1>", "<id2>"]}' \
  "$BASE/reports"
```

`report_type` ∈ `pdf | pptx | card`。创建接口限速 10 次/分钟；`item_ids` 中任何不属于当前工作空间的 ID 会导致整体 400。

### 7.2 LLM 摘要

生成报告时，若配置了默认 LLM Provider，系统会对选中信号自动调用 LLM 生成趋势摘要（`summary_text`）并写入报告。LLM 不可用时不阻断生成，仅摘要为空。

### 7.3 下载

**操作路径**：报告状态为 `completed` 后，该行出现 **Download PDF / Download PPTX / Open Card** 按钮。

**API 等价**：

```bash
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/reports"
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/reports/<report_id>/download"
```

未完成（非 `completed` 或无文件）时下载接口返回 400。

### 7.4 上传到 SharePoint（可选）

已配置 SharePoint 连接（§9.4）后，可把生成的报告文件上传到 SharePoint 文档库：

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"report_id": "<report_id>", "connection_id": "<connection_id>"}' \
  "$BASE/sharepoint/upload"
```

---

## 8. 团队管理

### 8.1 邀请成员

**操作路径**：**Team** 页面 → 填 **Name**、选择 **Role**（Admin / Analyst / Viewer）→ **Invite Member**。页面顶部绿色区域显示**新 API Key 明文——立即复制，只显示一次**。成员列表显示 Name / Role / Key Prefix / Created。

**API 等价**：

```bash
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"name": "张三", "role": "analyst", "workspace_id": "'$WS'"}' \
  "$BASE/team/members"

curl -H "X-API-Key: $KEY" "$BASE/team/members"
```

**注意事项**：邀请接口限速 5 次/分钟；仅 admin 可邀请；Key 以 bcrypt 哈希存储，服务端无法找回明文，丢失只能重新邀请。

### 8.2 角色权限表

| 能力 | admin | analyst | viewer |
|------|:-----:|:-------:|:------:|
| 浏览源 / 信号 / 趋势 / 报告（只读端点） | ✓ | ✓ | ✓ |
| 创建/编辑/删除数据源、触发扫描、审核信号、生成报告、改设置（写操作） | ✓ | ✓ | — |
| 邀请成员、查看成员列表、创建工作空间 | ✓ | — | — |
| Embed Token 创建 / 轮换 / 撤销 | ✓ | — | — |

（写权限 = `admin` 或 `analyst`；管理操作仅 `admin`。）

### 8.3 Embed Token（SharePoint 嵌入场景）

Embed Token 是**短期、只读**令牌，供 SPFx Web Part / 嵌入组件访问趋势数据，通过 `X-Embed-Token` 请求头使用，**不具备任何写权限**。

**API 等价**（仅 admin）：

```bash
# 创建（明文仅此一次返回）
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"name": "SharePoint Web Part", "ttl_days": 30}' \
  "$BASE/workspaces/$WS/embed-token"

# 列出 / 查看当前有效 token
curl -H "X-API-Key: $KEY" "$BASE/workspaces/$WS/embed-tokens"
curl -H "X-API-Key: $KEY" "$BASE/workspaces/$WS/embed-token/current"

# 轮换（旧 token 立即撤销，签发新 token）
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"ttl_days": 30}' \
  "$BASE/workspaces/$WS/embed-tokens/<token_id>/rotate"

# 撤销
curl -X POST -H "X-API-Key: $KEY" \
  "$BASE/workspaces/$WS/embed-tokens/<token_id>/revoke"
```

**注意事项**：

- `ttl_days` 1–365，缺省 30；到期自动失效；
- 嵌入端调用：`curl -H "X-Embed-Token: <token>" -H "X-Workspace-ID: $WS" ...`；
- 建议按部署环境各建一个 token，泄露时单独轮换/撤销，互不影响；
- 所有创建/轮换/撤销操作均写审计日志。

---

## 9. 系统设置

### 9.1 LLM Provider 配置

**操作路径**：**Settings** 页面 → 「LLM Provider」区块 → 修改 **Base URL / Model / Temperature / Max Tokens** → **Save LLM Settings**。

字段说明：

| 字段 | 说明 |
|------|------|
| `base_url` | OpenAI 兼容端点（如 `https://api.openai.com/v1` 或自建 vLLM/Ollama 网关） |
| `model` | 模型名（缺省 `gpt-4o-mini`） |
| `temperature` | 采样温度（0–1，缺省 0.7） |
| `max_tokens` | 单次最大输出 token 数（缺省 4096） |
| `api_key` | 仅 API 可更新；服务端加密存储，任何读取接口都不返回明文 |

**API 等价**：

```bash
# 查看 / 更新默认 provider
curl -H "X-API-Key: $KEY" "$BASE/settings/llm"
curl -X PUT -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini", "temperature": 0.3, "max_tokens": 4096, "api_key": "sk-..."}' \
  "$BASE/settings/llm"

# 多 provider 管理（is_default=true 的把其他 provider 自动改为非默认）
curl -H "X-API-Key: $KEY" "$BASE/settings/llm/providers"
curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"name": "primary", "base_url": "...", "model": "...", "api_key": "sk-...", "is_default": true}' \
  "$BASE/settings/llm/providers"
```

**注意事项**：评分、embedding、报告摘要都走 `is_default=true` 的 provider；未配置时相关功能返回 503。

### 9.2 Fallback Provider 链

主 provider 失败时按 `priority` 顺序切换到 fallback provider（embedding 调用同样生效）。

**API 等价**：

```bash
# 查看整体策略（主 + 有序 fallback 列表）
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/settings/llm/fallbacks-strategy"

# 新增 fallback（priority 越小越先尝试；is_enabled 控制启停）
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"name": "backup", "base_url": "...", "model": "...", "api_key": "sk-...", "priority": 1, "is_enabled": true, "timeout_seconds": 30, "max_retries": 2}' \
  "$BASE/settings/llm/fallbacks"

# 更新 / 删除
curl -X PUT    ... -d '{"is_enabled": false}' "$BASE/settings/llm/fallbacks/<provider_id>"
curl -X DELETE -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/settings/llm/fallbacks/<provider_id>"

# 健康检查（发一条最小 chat completion，返回状态与延迟）
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  "$BASE/settings/llm/fallbacks/<provider_id>/health"
```

**注意事项**：fallback 链为空即不启用故障切换；健康检查结果会写入健康日志，便于巡检。

### 9.3 评分维度权重配置

**操作路径**：**Settings** 页面 → 「Scoring Weights」区块 → 勾选启用维度、调整权重 → **Save Scoring Settings**。

默认 5 个维度（总体分 = 各维度加权平均）：

| 维度 | 默认权重 | 含义 |
|------|---------:|------|
| `signal_strength` | 0.25 | 信号强度 |
| `cross_domain_impact` | 0.20 | 跨领域影响 |
| `investment_velocity` | 0.20 | 投资增速 |
| `technical_feasibility` | 0.20 | 技术可行性 |
| `strategic_fit` | 0.15 | 战略契合度 |

**注意事项**：**启用维度的权重之和必须等于 1.0**，否则保存返回 400；权重按工作空间独立保存。

**API 等价**：

```bash
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/settings/scoring"
curl -X PUT -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{"dimensions": [{"name": "signal_strength", "weight": 0.3, "enabled": true}, ...]}' \
  "$BASE/settings/scoring"
```

### 9.4 SharePoint Online 连接

**操作路径**：**Settings** 页面 → 「SharePoint Online」区块 → 填 **Name / Site URL / List ID / Drive ID / Tenant ID / Client ID / Client Secret** → **Add Connection**。已有连接支持 **Edit / Health / Delete**。

- 该连接同时被 `sharepoint_list` 扫描器（§2.5）和报告上传（§7.4）使用；
- 凭据为 Entra ID 应用注册（client credentials），需授予对应 Graph API 权限（Sites.Read 等）；
- Client Secret 加密存储；**Health** 按钮即时验证连通性。

**API 等价**：

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" -H "Content-Type: application/json" \
  -d '{"name": "corp-sp", "site_url": "https://contoso.sharepoint.com/sites/rd", "list_id": "...", "drive_id": "...", "tenant_id": "...", "client_id": "...", "client_secret": "..."}' \
  "$BASE/sharepoint/connections"
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/sharepoint/connections/<id>/health"
```

---

## 10. 通知配置

扫描完成/失败时向 Email（SMTP）或 Microsoft Teams 推送通知。当前通过 API 配置（前端无界面）。

### 10.1 Email（SMTP）

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_type": "email",
    "name": "值班邮箱",
    "config": {
      "smtp_host": "smtp.example.com",
      "smtp_port": 587,
      "username": "bot@example.com",
      "password": "app-password",
      "to_address": "oncall@example.com"
    },
    "on_scan_success": false,
    "on_scan_failure": true
  }' "$BASE/notifications/channels"
```

config 字段：`smtp_host`（缺省 smtp.gmail.com）、`smtp_port`（缺省 587，STARTTLS）、`username` / `password`（可空则免认证）、`to_address`。**config 整体加密存储。**

### 10.2 Teams Webhook

```bash
curl -X POST -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" \
  -H "Content-Type: application/json" \
  -d '{
    "channel_type": "teams_webhook",
    "name": "RD 频道",
    "config": {"webhook_url": "https://contoso.webhook.office.com/..."},
    "on_scan_success": true,
    "on_scan_failure": true
  }' "$BASE/notifications/channels"
```

以 Adaptive Card 形式推送。`webhook_url` 在 Teams 频道的「连接器 / Workflows」中生成。

### 10.3 管理与排障

```bash
# 列出 / 删除渠道
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/notifications/channels"
curl -X DELETE -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/notifications/channels/<channel_id>"

# 发送日志（最近 100 条，含 status 与 error_message）
curl -H "X-API-Key: $KEY" -H "X-Workspace-ID: $WS" "$BASE/notifications/logs"
```

**注意事项**：`on_scan_success` 缺省 false、`on_scan_failure` 缺省 true（即默认只报失败）；通知是 best-effort，发送失败不影响扫描本身，失败原因看 logs。

---

## 11. 管理员运维

### 11.1 环境变量速查

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DATABASE_URL` | `sqlite:///./trend_scout.db` | 数据库连接（支持 PostgreSQL） |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis 连接 |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | 同上 | Celery broker / result backend |
| `SECRET_KEY` | —（**必填**） | 加密/签名密钥；非测试环境缺失或为默认值时**拒绝启动** |
| `ENCRYPTION_SALT` | —（**必填**） | Base64 盐值，用于 Fernet 密钥派生（源 config、通知 config、LLM key 加密） |
| `TESTING` | `false` | 测试模式，**生产严禁开启** |
| `CORS_ORIGINS` | `http://localhost:5173` | CORS 白名单（逗号分隔） |
| `SSRF_ALLOW_PRIVATE` | `false` | 允许扫描器访问内网/回环地址（仅开发用） |
| `REVIEW_MODE_ENABLED` | `false` | 开启信号人工审核流（§4） |
| `HUMAN_REVIEW_THRESHOLD` | `0.4` | 人工审核分数带下界（保留字段，当前分流只看下行） |
| `AUTO_APPROVE_THRESHOLD` | `0.7` | review 模式下达到此分自动批准 |
| `ANOMALY_DETECTION_ENABLED` | `false` | 异常检测（仅 review 模式开启时生效） |
| `ANOMALY_ZSCORE_THRESHOLD` | `2.5` | 异常检测 z-score 阈值 |
| `VECTOR_SEARCH_ENABLED` | `false` | 语义检索开关（§5.2） |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | embedding 模型名 |
| `TREND_ANALYST_ENABLED` | `false` | 趋势聚合时调用 TrendAnalystAgent 生成高管摘要 |
| `LLM_DEFAULT_BASE_URL` / `LLM_DEFAULT_MODEL` | OpenAI / `gpt-4o-mini` | 未配置 DB provider 时的兜底 |
| `JWT_ALGORITHM` | `HS256` | 建议生产改 `RS256`（§11.5） |
| `JWT_EXPIRATION_MINUTES` | `60` | JWT 有效期 |
| `JWT_PRIVATE_KEY_PEM` / `JWT_PUBLIC_KEYS_PEM` / `JWT_KEY_ID` | 空 / 空 / `default` | RS256 密钥材料 |
| `FRAME_OPTIONS` / `HSTS_ENABLED` | `DENY` / `false` | 安全头（HTTPS 部署建议开 HSTS） |
| `ENTRA_DUMMY_MODE` | `false` | Microsoft 登录的本地模拟模式（仅开发） |
| `OUTPUT_DIR` | `./outputs` | 报告输出目录 |

生成密钥：

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export ENCRYPTION_SALT="$(python -c 'import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(16)).decode())')"
```

### 11.2 PostgreSQL 迁移

```bash
cd backend
alembic upgrade head                       # 在目标库建表
tse migrate-sqlite-to-postgres \
  --sqlite-path trend_scout.db \
  --postgres-url postgresql://user:pass@host:5432/trendscout \
  --dry-run                                # 先预演
tse migrate-sqlite-to-postgres --sqlite-path trend_scout.db   # 正式迁移（--postgres-url 缺省读 DATABASE_URL）
```

迁移完成后把 `DATABASE_URL` 指向 PostgreSQL 并重启。详细评估见 `docs/postgresql-migration-assessment.md`。

### 11.3 审计日志查询

所有敏感操作（审核、批量审核、反馈、设置变更、成员邀请、Embed Token 操作、工作空间创建）写入 `audit_logs` 表，字段：`actor_id` / `actor_type`（api_key / jwt / system）/ `action` / `workspace_id` / `resource_type` / `resource_id` / `detail` / 时间戳。v1.0 未提供查询 API，直接查库：

```sql
SELECT created_at, actor_id, action, resource_id, detail
FROM audit_logs
WHERE workspace_id = '<ws>' AND action LIKE 'signal.%'
ORDER BY created_at DESC LIMIT 100;
```

常见 action：`signal.review`、`signal.bulk_review`、`signal.feedback`、`settings.llm.update`、`settings.scoring.update`、`team.member.create`、`embed_token.create/revoke/rotate`、`workspace.create`。

### 11.4 Embedding 回填

开启 `VECTOR_SEARCH_ENABLED` 后，存量信号没有 embedding，用 CLI 回填（幂等，已有 embedding 的跳过）：

```bash
cd backend
tse backfill-embeddings --dry-run                      # 先看有多少待回填
tse backfill-embeddings --workspace-id <ws>            # 限定工作空间
tse backfill-embeddings --batch-size 32                # 每批 32 条（缺省）
```

前置条件：`VECTOR_SEARCH_ENABLED=true` 且已配置默认 LLM Provider，否则命令直接报错退出。

### 11.5 JWT 密钥轮换（RS256）

```bash
# 1. 生成新密钥对
python scripts/generate_jwt_keys.py --kid key-2026-08
# 2. 新私钥设为 JWT_PRIVATE_KEY_PEM，JWT_KEY_ID=key-2026-08
# 3. 新公钥追加进 JWT_PUBLIC_KEYS_PEM（JSON: kid -> 公钥 PEM），保留旧 kid
# 4. 等 JWT_EXPIRATION_MINUTES 过后，旧 token 全部过期，再移除旧公钥
```

`JWT_PUBLIC_KEYS_PEM` 是多 kid 结构，正是为平滑轮换设计：新旧公钥并存期间，旧签名 token 仍可验证。

---

## 12. 常见问题 FAQ

**Q1：扫描失败，Sources 页面显示 unhealthy。**
看源卡片上的 `last_failure_reason` 和蓝色 `Fix:` 建议（§2.6）。按类型排查：RSS 检查 URL 与证书；arXiv 检查检索式与到 export.arxiv.org 的网络；web_search 检查 API Key 与计费；custom_api 检查 `response_path`/`field_mapping` 是否与实际响应结构一致；sharepoint_list 检查连接是否启用及 Graph 权限。若目标在内网，确认是否被 SSRF 防护拦截（仅开发环境可用 `SSRF_ALLOW_PRIVATE=true` 放开）。

**Q2：`Collected` 有数据但 `Analyzed` 为 0 / 信号没有分数。**
LLM 调用失败。检查：Settings → LLM Provider 是否已配置且 `is_default`；`base_url`/`model`/`api_key` 是否正确；用 fallback 健康检查端点（§9.2）实测连通性；配置了 fallback 链时主 provider 故障会自动切换。未配置默认 provider 时相关接口返回 503 "No default LLM provider configured"。

**Q3：语义搜索 / 相似信号返回 503 或 404。**
- 503 "Vector search is disabled"：管理员设置 `VECTOR_SEARCH_ENABLED=true` 并重启；
- 503 "No default LLM provider configured"：先配 LLM Provider；
- 404 "Signal has no embedding"：该信号是开关开启前采集的，运行 `tse backfill-embeddings`（§11.4）；
- 注意 embedding 生成失败不会阻断扫描，只记 warning，所以新扫描也可能有个别信号缺 embedding。

**Q4：review 模式不生效，信号全是 `auto`。**
- 确认 `REVIEW_MODE_ENABLED=1` 已设置且**重启了后端和 Celery worker**（worker 进程也要读到该环境变量）；
- 该开关只影响开启后**新扫描**的信号，历史信号保持 `auto`；
- 分数达到 `AUTO_APPROVE_THRESHOLD`（缺省 0.7）的信号会自动 `approved`，不会进队列——队列空不代表模式没开，先看 Approved 页。

**Q5：审核队列里看不到分配给我的任务。**
确认 `review_assignments` 是否为你的 category 配置了分配；未配置分配的信号 `assigned_reviewer_id` 为空，`assigned_to_me=true` 会过滤掉它们。管理员补充分配记录后，新产生的 `pending_review` 信号才会自动指派。

**Q6：创建数据源报 400 "Config 'url' is required"。**
除 `sharepoint_list` 外所有类型都必须含 `url` 字段——包括 arXiv（虽然扫描器不用它，按 §2.2 示例填上即可）。`sharepoint_list` 则必须填 `connection_id`。

**Q7：保存评分权重报 400。**
启用维度的权重之和必须恰好等于 1.0（如 0.3+0.2+0.2+0.2+0.1），调整后重试。

**Q8：触发扫描/生成报告返回 429。**
触发扫描与创建报告均限速 10 次/分钟，邀请成员限速 5 次/分钟。稍等重试；批量操作优先用批量接口（如 bulk-review）。

**Q9：报告一直 `generating` 或下载报 400。**
确认 Celery worker 进程在运行、Redis 可达；无 Redis/Celery 环境报告任务不会执行。LLM 摘要失败不会阻断报告，只缺摘要。

**Q10：Teams / Email 通知没收到。**
查 `GET /notifications/channels` 确认渠道已建且 `on_scan_failure`/`on_scan_success` 符合预期；查 `GET /notifications/logs` 看每次发送的 status 与 error_message（SMTP 认证失败、webhook URL 失效等都在这里）。

---

## 附：相关文档

- `docs/signal-review-workflow.md` — 审核工作流技术细节
- `docs/vector-search.md` — 语义检索方案与 pgvector 演进路径
- `docs/security-hardening.md` — 安全加固说明
- `docs/postgresql-migration-assessment.md` — PostgreSQL 迁移评估
- `README.md` — 部署与快速开始
