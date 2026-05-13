# VLMac

实时视频流 → VLM（视觉语言模型）分析平台。浏览器采集摄像头画面，通过 WebSocket 推流到服务端，结合 Diff Engine 变化检测，由 vLLM 进行智能视觉分析。

## 功能

- **实时视频推流** — 浏览器 MediaRecorder 采集 → WebSocket 二进制推流 → 服务端缓冲
- **智能帧提取** — ffmpeg 场景检测 + 保底采样 + 智能降采样，自动选取关键帧
- **变化监测（Diff Engine）** — 前端 16×9 网格像素对比，实时检测画面变化并标注事件
- **手动对话查询** — 随时发问，VLM 流式回答，支持多轮对话历史
- **定时任务** — 创建多个周期性自动分析任务，共享同一视频流
- **MinIO 持久化** — 查询记录自动保存为 Markdown 文件

## 架构

```
浏览器 getUserMedia → MediaRecorder
  ├── WS Binary → 服务端 video_chunks 缓冲
  ├── Diff Engine → activityEvents → WS → 服务端累积
  ├── 手动查询 → 消费缓冲 → ffmpeg 提取帧 → vLLM 流式回答
  └── 定时任务 → 周期消费缓冲 → ffmpeg 提取帧 → vLLM 分析
```

## 快速开始

### 依赖

- Python 3.10+
- ffmpeg
- [vLLM](https://github.com/vllm-project/vllm) 服务（默认 `localhost:58000`）
- MinIO（默认 `localhost:9000`）

### 安装

```bash
pip install -r requirements.txt
```

### 启动

```bash
python server.py
```

访问 `http://localhost:59092`，授权摄像头后点击「开始推流」即可使用。

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `VLLM_BASE_URL` | `http://localhost:58000` | vLLM 服务地址 |
| `VLLM_MODEL` | `RM-01 VLM` | 模型名称 |
| `MINIO_ENDPOINT` | `localhost:9000` | MinIO 地址 |
| `MINIO_ACCESS_KEY` | `rm01` | MinIO 访问密钥 |
| `MINIO_SECRET_KEY` | `rm01rm01` | MinIO 密钥 |
| `MINIO_BUCKET` | `rm01` | MinIO 存储桶 |

## API 文档

详见 [API.md](API.md)。

## License

MIT
