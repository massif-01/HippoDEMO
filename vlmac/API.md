# VLMac API 文档

**服务端口**: `59092`  
**Base URL**: `http://<host>:59092`

## 架构概览

双通道架构：

- **浏览器推流**（主要）：浏览器 MediaRecorder → WebSocket 二进制推流 → 服务端缓冲 → ffmpeg 提取帧 → VLM 分析
- **Headless 采集**（次要）：服务端 ffmpeg 直接从 V4L2 设备采集 → 定时 VLM 分析（无需浏览器）

浏览器推流模式下，前端 Diff Engine（16×9 网格像素对比）检测画面变化，变化事件通过 WS 实时同步到服务端，辅助帧提取和场景标注。

```
浏览器 getUserMedia → MediaRecorder
  ├── WS Binary → 服务端 video_chunks 缓冲
  ├── Diff Engine → activityEvents → WS activity_event → 服务端 server_activity_events
  ├── 手动查询: sendQuery → WS query → 消费缓冲 → VLM
  └── 定时任务: WS create_task → 服务端周期消费缓冲 → VLM
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VLLM_BASE_URL` | `http://localhost:58000` | vLLM 服务地址 |
| `VLLM_MODEL` | `RM-01 VLM` | vLLM 模型名称 |
| `HIPPODEMO_VLMAC_STORAGE` | `basic-memory-local` | 存储后端 |
| `HIPPODEMO_BASIC_MEMORY_PROJECT_DIR` | 必填 | Basic Memory `hippo` project 目录 |

---

## 1. WebSocket（主要接口）

### `ws://<host>:59092/ws`

双向通道，传输二进制视频流 + JSON 控制消息。

### 客户端 → 服务端

#### 二进制消息

| 内容 | 说明 |
|------|------|
| MediaRecorder chunk (bytes) | 视频流数据。WebM 格式首块须以 EBML 头 `1a45dfa3` 开头，否则丢弃 |

#### JSON 消息

| type | 字段 | 说明 |
|------|------|------|
| `set_mime` | `mime` | 设置视频 MIME（如 `video/webm`），清空视频缓冲和活动事件 |
| `query` | `text`, `system_prompt`, `id`, `scene_threshold`, `min_interval`, `activity_events: [{t, type, intensity, ratio, desc}]`, `no_history` | 手动查询：消费当前视频缓冲 → 提取帧 → VLM 流式回答 |
| `activity_event` | `event: {t, type, intensity, ratio, desc}` | Diff Engine 检测到的单个变化事件，累积供定时任务使用 |
| `clear_history` | — | 清除对话历史 + 视频缓冲 + 活动事件 |
| `reset_stream` | — | 仅清空视频缓冲 |
| `create_task` | `interval`, `prompt`, `system_prompt`, `scene_threshold`, `min_interval` | 创建 WS 定时任务（共享当前 WS 的视频缓冲） |
| `delete_task` | `task_id` | 删除指定 WS 定时任务 |
| `list_tasks` | — | 列出当前 WS 连接的所有定时任务 |
| `ping` | — | 心跳 |

### 服务端 → 客户端

| type | 字段 | 触发 |
|------|------|------|
| `stream_status` | `chunks`, `size_kb`, `duration` | 每次接收二进制视频块后 |
| `stream_reset` | — | 缓冲被消费或主动清空后 |
| `start` | `id`, `frames_used`, `total_extracted`, `video_duration`, `activity_events` | 手动查询开始 VLM 分析 |
| `token` | `id`, `text` | VLM 流式返回 token |
| `done` | `id` | 查询完成 |
| `error` | `id`(可选), `text` | 错误信息 |
| `history_cleared` | — | clear_history 响应 |
| `pong` | — | ping 响应 |
| `task_created` | `task_id`, `interval`, `prompt` | create_task 响应 |
| `task_deleted` | `task_id` | delete_task 响应 |
| `task_list` | `tasks: [{task_id, interval, prompt, running}]` | list_tasks 响应 |
| `task_start` | `task_id`, `id`, `frames_used`, `video_duration`, `activity_events` | 定时任务开始查询 |
| `task_result` | `task_id`, `id`, `query_count` | 定时任务查询完成 |
| `task_error` | `task_id`, `text` | 定时任务出错 |

---

## 2. REST API — 设备管理

### `GET /api/devices`

列出所有可用的 UVC/V4L2 视频采集设备。

```json
{
  "devices": [
    {"name": "USB Camera", "path": "/dev/video0"}
  ]
}
```

---

## 3. REST API — Headless 任务管理

> 服务端 V4L2 直接采集的后台任务，不依赖浏览器推流。需要服务器有摄像头设备。

### `GET /api/tasks`

列出所有 Headless 任务。

```json
{
  "tasks": [{
    "task_id": "abc12345",
    "running": true,
    "device": "/dev/video0",
    "resolution": "1920x1080",
    "interval": 30,
    "scene_threshold": 0.05,
    "min_interval": 3.0,
    "bitrate": "1M",
    "timer_prompt": "请描述当前画面中的内容和变化。",
    "system_prompt": "...",
    "results_count": 5,
    "query_count": 5,
    "created_at": "2026-04-14T08:00:00+00:00",
    "session_filename": "task_abc12345.md"
  }]
}
```

### `GET /api/tasks/{task_id}`

获取指定任务详情。

### `POST /api/tasks`

创建并启动 Headless 任务。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `device` | string | `""` (自动选首个设备) | V4L2 设备路径 |
| `resolution` | string | `"1920x1080"` | 采集分辨率 |
| `interval` | int | `30` | 查询间隔（秒），5–3600 |
| `scene_threshold` | float | `0.05` | 场景灵敏度，0.01–1.0 |
| `min_interval` | float | `3.0` | 保底采样间隔（秒），0.5–60.0 |
| `bitrate` | string | `"1M"` | 视频编码码率 |
| `timer_prompt` | string | `"请描述当前画面中的内容和变化。"` | 提示词 |
| `system_prompt` | string | `""` | 系统提示词 |

### `DELETE /api/tasks/{task_id}`

停止并删除任务。

### `GET /api/tasks/{task_id}/results`

获取任务结果（`?limit=10`）。

---

## 4. REST API — 兼容接口

| 接口 | 行为 |
|------|------|
| `GET /api/status` | 任务总览（运行数、任务摘要） |
| `POST /api/start` | 等同 `POST /api/tasks` |
| `POST /api/stop` | 停止所有任务 |
| `GET /api/results` | 所有任务合并结果（`?limit=10`） |

---

## 5. REST API — Basic Memory 本地存储

### `GET /api/storage/status`

返回当前 storage backend、Basic Memory project path、rolling context 路径。

### `GET /api/storage/list`

列出本地 storage 文件（`?kind=video_summary|video_chunk|rolling_context&limit=50`）。

### `GET /api/storage/read`

读取 `hippo/context/...` 下的文本文件。二进制 chunk 目录不可通过该接口读取。

### `GET /api/storage/stats`

返回文本 storage 统计。

### 兼容接口

### `GET /api/minio/list`

兼容旧前端，实际映射到本地 `/api/storage/list`。

### `GET /api/minio/read`

兼容旧前端，实际映射到本地 `/api/storage/read`。

### `GET /api/minio/stats`

兼容旧前端，实际映射到本地 `/api/storage/stats`。

---

## 6. 存储文件说明

| 文件模式 | 写入方式 | 说明 |
|----------|----------|------|
| `hippo/context/video/rolling_context.md` | **追加** | 人类可读滚动视频上下文 |
| `hippo/context/video/rolling_context.jsonl` | **追加** | 结构化滚动上下文，每行含 `system_time_iso` 和 `epoch_ms` |
| `hippo/context/video/summaries/{source_id}/{timestamp}.md` | 新建 | 单次 VLM 分析 Markdown |
| `hippo/context/video/summaries/{source_id}/{timestamp}.json` | 新建 | 单次 VLM 分析结构化数据 |
| `hippo/context/video/chunks/{source_id}/{timestamp}.webm` | 新建 | 原始 evidence chunk，不进入 Basic Memory note |
| `hippo/context/video/chunks/{source_id}/manifest.jsonl` | **追加** | chunk 索引 |

---

## 7. 快速开始

```bash
# 准备本地 runtime（内含 vlmac Python 依赖和 ffmpeg）
bash ../script/bootstrap_vlmac_runtime.sh

# 启动服务
python server.py

# 打开 WebUI（浏览器推流模式）
# 访问 http://localhost:59092

# --- 以下为 Headless 模式（需要服务器有摄像头） ---

# 查看设备
curl http://localhost:59092/api/devices

# 创建 Headless 任务
curl -X POST http://localhost:59092/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"device": "/dev/video0", "interval": 30, "timer_prompt": "描述画面变化"}'

# 查看任务结果
curl http://localhost:59092/api/tasks/abc12345/results

# 停止任务
curl -X DELETE http://localhost:59092/api/tasks/abc12345

# 读取滚动上下文
curl "http://localhost:59092/api/storage/read?path=hippo/context/video/rolling_context.md"
```
