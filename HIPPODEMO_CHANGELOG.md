# HippoDEMO Changelog

> 本文档记录 HippoDEMO 从项目调研、PRD 定义、架构设计到 Frontend + Orchestrator 初版实现的完整构建过程。  
> 当前记录日期：2026-05-12。

## 当前结论

HippoDEMO 已经从“多个既有项目的能力组合设想”推进到一个可运行的 macOS SwiftUI 状态栏应用：

- macOS app 以状态栏 Jarvis 形态运行，而不是普通 dashboard。
- Swift 前端已经接入本地 FastAPI Orchestrator。
- Orchestrator 已经支持 mock-first demo 主路径。
- OpenChronicle 已完成 real adapter v1，能够被 Orchestrator 真实启动、停止、暂停、恢复、触发采集、推进 timeline、重建采集索引。
- `Jarvis ON` 会启动 OpenChronicle；`Jarvis OFF` 会触发一次 context capture，并进入 Active Task 候选状态。
- Project_Cortex 的 Skill 沉淀路径被保留为 SOP 生成能力入口。

当前仍然不是最终产品态：

- OpenChronicle 的 writer/reducer/classifier 仍需要配置可用模型 provider，目前默认模型会因为缺少 API key 报 `AuthenticationError`。
- ownscribe、vlmac、cua-driver、basic-memory 还没有全部 real adapter 化。
- UI 已有 Jarvis HUD 方向，但仍可以继续做视觉 polish 和交互细化。

## 初始项目调研

工作目录下最初有多个独立项目，后来新增了 `cua`。我们先逐个梳理了各项目的前后端能力，并确认哪些能力进入主路径，哪些能力只作为后台设置或调试窗口。

### 项目能力定位

| 项目 | 在 HippoDEMO 中的定位 |
|---|---|
| `ai-manus` | 可参考沙盒实时 VNC、Take Over、会话、流式 Chat、文件/工具面板、PlanPanel。 |
| `Project_Cortex` | 主前端不直接使用，但保留 SOP / Skill 生成链路。 |
| `ownscribe` | 会议音频录制、转写、说话人分离、总结与问答核心。 |
| `OpenChronicle` | 上下文感知、AX/截图采集、timeline、session reducer、长期记忆和 MCP 上下文工具。 |
| `vlmac` | 视频 chunk、帧抽样、场景检测、VLM 多模态问答和视频归档。 |
| `basic-memory` | note CRUD、Markdown/frontmatter、搜索、知识图谱和 MCP note preview。 |
| `cua` | 主要 computer use 执行层，重点复用 driver、computer-server、sandbox runtime、ComputerAgent。 |

### 关键判断

- OpenChronicle 自身没有完整 computer use 执行能力，它更偏“观察和记忆”。
- `cua` 的 driver 更适合作为实际 macOS computer use 执行层。
- Project_Cortex 中已经存在 Skill 沉淀：通过按钮标记输入点，再调度 Dify API 生成 `SKILL.md`。
- “邮件”不应作为特有功能，而应抽象为 `Active Task` 的一个实例。
- 软件主体验应像 Jarvis：平时停留在状态栏，只有在可介入时机出现时弹出或提示。

## PRD 与拓扑设计

### PRD

已创建：

- `HIPPODEMO_PRD_REALTIME_PATH.md`

PRD 中确立了以下主路径：

1. 用户从状态栏开启 `Jarvis ON`。
2. 系统进入会议/上下文监听。
3. ownscribe 负责音频会议理解。
4. OpenChronicle 负责当前 App、窗口、URL、可见文本和操作上下文。
5. vlmac 或录屏链路负责视频/画面归档。
6. 会议结束后进入 Active Task 候选。
7. 用户确认后系统把准备好的内容插入当前任务界面。
8. 审核完成后系统识别可复用模式。
9. 用户可以一键沉淀为 Skill。

### 拓扑图

已生成并保存：

- `hippo_demo_topology.jpg`

PRD 中也补入了 Mermaid 拓扑图，表达 Swift 状态栏前端、Orchestrator、OpenChronicle、ownscribe、vlmac、cua-driver、Project_Cortex、basic-memory 的关系。

## Frontend 规划

前端方向从普通 app/dashboard 调整为 macOS 状态栏 Jarvis：

- 主入口是状态栏，不是普通窗口首页。
- 主 popover 只显示当前状态、核心动作和 Active Task。
- Settings / Developer Tools 承载 OpenChronicle、vlmac、basic-memory、cua 等后台能力，不进入主路径。
- 邮件、微信、文档、CRM 等都被视为 Active Task 的目标 surface。
- 状态栏除了录制/Jarvis 控制，还应有 SOP / Skill Capture 标记按钮。

采用 SwiftUI + AppKit 辅助：

- `MenuBarExtra` 作为主入口。
- `Window("Activity Center")` 作为活动中心。
- `Window("Skill Library")` 作为 Skill 产物库。
- `Settings` 作为后台配置窗口。
- `NSApp.setActivationPolicy(.accessory)` 使应用保持状态栏形态。

## Swift macOS App 初版

新增 SwiftPM macOS GUI app：

- `Package.swift`
- `Sources/HippoJarvis/App/HippoJarvisApp.swift`
- `Sources/HippoJarvis/App/AppDelegate.swift`
- `Sources/HippoJarvis/Models/AppModels.swift`
- `Sources/HippoJarvis/Services/OrchestratorClient.swift`
- `Sources/HippoJarvis/Services/OrchestratorLauncher.swift`
- `Sources/HippoJarvis/Stores/AppStateStore.swift`
- `Sources/HippoJarvis/Stores/SkillStore.swift`
- `Sources/HippoJarvis/Components/GlassSurface.swift`
- `Sources/HippoJarvis/Views/MenuBarRootView.swift`
- `Sources/HippoJarvis/Views/ActivityCenterView.swift`
- `Sources/HippoJarvis/Views/SkillLibraryView.swift`
- `Sources/HippoJarvis/Views/SettingsView.swift`
- `Sources/HippoJarvis/Support/AppLocalization.swift`

### 主要前端能力

- 状态栏 `Hippo` menu bar extra。
- `Jarvis ON` / `Jarvis OFF`。
- `Capture Skill` / `Finish Capture`。
- Active Task 卡片和插入确认。
- Activity Center 活动状态和服务信号。
- Skill Library 展示生成的 Skill artifact。
- Settings 管理 Orchestrator 地址、权限提示、服务状态和 OpenChronicle 控制。
- 中英文基础文案切换。

### UI 方向调整

用户反馈“界面有点丑、普通、没有 Jarvis 感”后，主 popover 做了第一轮视觉升级：

- 顶部状态脉冲核心 `StatusPulse`。
- 玻璃材质卡片 `GlassSurface`。
- Jarvis 风格主按钮 `JarvisActionButton`。
- `HIPPO + 状态胶囊`。
- Active Task 的 Ready to Act 卡片。
- 指标胶囊：Skills、Services、Confidence/Mode。
- 圆形工具入口：Activity、Skills、Refresh、Quit。

## Orchestrator 初版

新增本地 FastAPI Orchestrator：

- `orchestrator/main.py`
- `orchestrator/models.py`
- `orchestrator/store.py`
- `orchestrator/requirements.txt`
- `orchestrator/README.md`
- `orchestrator/adapters/project_cortex.py`

### 初始 API

- `GET /health`
- `GET /state`
- `GET /events`
- `POST /session/jarvis-on`
- `POST /session/jarvis-off`
- `POST /session/pause`
- `POST /session/resume`
- `POST /sop/capture-start`
- `POST /sop/capture-finish`
- `POST /active-task/generate`
- `POST /active-task/{id}/confirm`
- `POST /active-task/{id}/ignore`
- `POST /active-task/{id}/complete`
- `POST /skill/generate`
- `GET /skills`
- `DELETE /skill/{id}`

### 状态模型

前端使用的核心 snapshot：

- `jarvis_state`
- `status_message`
- `current_session`
- `sop_capture`
- `current_task`
- `skills`
- `services`

Orchestrator 内部状态映射到前端状态：

- `intervention_ready -> active_task_candidate`
- `awaiting_review -> task_reviewing`
- SOP capture 状态映射为 `sop_marking` / `sop_generating`

### Mock-first Demo 主路径

已实现可验证 demo flow：

1. `Jarvis ON` 创建 mock meeting session。
2. `Capture Skill` 进入 SOP 标记。
3. `Finish Capture` 生成 Skill artifact。
4. `Jarvis OFF` 生成会议纪要、follow-up draft、action items。
5. Orchestrator 生成 Active Task。
6. 用户确认后进入 `task_reviewing`。
7. 用户标记完成后进入 `pattern_detected`。
8. 用户可触发 `Generate Skill`。

## Project_Cortex Skill 生成

Project_Cortex 没有进入主前端，但保留了 SOP 生成适配器：

- `orchestrator/adapters/project_cortex.py`

当前行为：

- 如果真实 Project_Cortex/Dify 配置可用，则可以接真实 SOP generator。
- 否则走 mock 生成 `SKILL.md` 风格产物。

Skill 产物保存在：

- `orchestrator/data/skills/*.md`
- `orchestrator/data/skills.json`

## OpenChronicle 检查与 real adapter v1

### OpenChronicle 本体检查

在 `OpenChronicle` 目录下建立本地 venv：

- `OpenChronicle/.venv`

验证结果：

- `pytest` 全部通过：`100 passed`
- `openchronicle capture-once` 能写入 `/Users/massif/.openchronicle/capture-buffer/*.json`
- capture 中包含 `ax_tree` 和可见文本。
- `openchronicle start --foreground` 能启动 MCP HTTP 服务。
- MCP endpoint 为 `http://127.0.0.1:8742/mcp`
- 当前 writer/reducer/classifier 因模型配置缺失会报 `AuthenticationError`。

### real adapter v1

新增：

- `orchestrator/adapters/openchronicle.py`

支持命令：

- `status`
- `start`
- `stop`
- `pause`
- `resume`
- `capture-once`
- `rebuild-captures-index`
- `timeline tick`

新增 Orchestrator API：

- `POST /integrations/openchronicle/start`
- `POST /integrations/openchronicle/stop`
- `POST /integrations/openchronicle/pause`
- `POST /integrations/openchronicle/resume`
- `POST /integrations/openchronicle/capture-once`
- `POST /integrations/openchronicle/rebuild-captures-index`
- `POST /integrations/openchronicle/timeline-tick`

服务状态映射：

- `running` / `healthy` -> `online`
- daemon stopped -> `stopped`
- CLI 可用但未运行 -> `available`
- binary 不存在或命令异常 -> `error`

额外处理：

- `/state` 会刷新 OpenChronicle 状态。
- 为避免频繁调用 `openchronicle status`，增加了短 TTL。
- `AuthenticationError` 只写入 detail，不把 capture/daemon 判定为 error。
- `Jarvis ON` 会启动 OpenChronicle。
- `Jarvis OFF` 会触发一次 `capture-once`，失败时保守 fallback 到 `timeline tick`。

### Swift Settings 控制入口

Swift 侧新增 OpenChronicle action：

- `openChronicleStart`
- `openChronicleStop`
- `openChroniclePause`
- `openChronicleResume`
- `openChronicleCaptureOnce`
- `openChronicleRebuildCapturesIndex`
- `openChronicleTimelineTick`

Settings 中新增 `OpenChronicle Controls`：

- Runtime：Start / Stop / Pause / Resume
- Operations：Capture Once / Timeline Tick / Rebuild Captures Index
- 当前 service 状态和 detail

## Build / Run 工作流

新增脚本：

- `script/build_and_run.sh`

脚本职责：

- 构建 `HippoJarvis`。
- 生成 `dist/HippoJarvis.app`。
- 通过 `/usr/bin/open -n` 启动 app bundle。
- 支持 `run`、`--debug`、`--logs`、`--telemetry`、`--verify`。

新增 Codex Run 配置：

- `.codex/environments/environment.toml`

`--verify` 当前会检查：

- `HippoJarvis` 进程启动。
- Orchestrator `/health` 可用。
- app 进程在 health ready 后仍稳定存活。

## 关键问题与修复

### Orchestrator 自启动路径

问题：

- Swift `.app` 启动后，Orchestrator 有时找不到正确项目根目录或工作目录。

修复：

- `OrchestratorLauncher` 使用 `HIPPODEMO_ROOT` 和 `PYTHONPATH` 指向项目根目录。
- Python 进程的 cwd 使用临时目录，避免 bundle 运行路径影响 import。

### `/state` 状态刷新成本

问题：

- OpenChronicle `status` 会触发模型检查，可能耗时并输出 `AuthenticationError`。
- Swift 事件流刷新可能导致状态命令过于频繁。

修复：

- Orchestrator 对 OpenChronicle status 加短 TTL。
- `AuthenticationError` 只作为 detail，不影响 daemon/capture 状态。

### 前端编译稳定性

过程中遇到过 SwiftUI 类型检查和 localization return 报错提示。

当前验证结果：

- `swift build --product HippoJarvis` 已通过。

## 当前验证记录

最近一次完整验证命令：

```bash
python -m compileall orchestrator
swift build --product HippoJarvis
./script/build_and_run.sh --verify
```

结果：

- Python compileall 通过。
- Swift build 通过。
- `HippoJarvis` app bundle 启动成功。
- Orchestrator `/health` ready。
- app 进程稳定存活。

OpenChronicle API smoke 已验证：

```text
state -> OpenChronicle stopped
openchronicle start -> online
openchronicle capture-once -> online, buffer 增加
openchronicle timeline-tick -> online
openchronicle rebuild-captures-index -> online
jarvis-on -> meeting_active, OpenChronicle online
jarvis-off -> active_task_candidate, 触发 capture
openchronicle pause -> capture paused
openchronicle resume -> capture active
openchronicle stop -> stopped
```

## 当前文件结构摘要

核心 HippoDEMO 文件：

- `HIPPODEMO_PRD_REALTIME_PATH.md`
- `HIPPODEMO_CHANGELOG.md`
- `hippo_demo_topology.jpg`
- `Package.swift`
- `Sources/HippoJarvis/**`
- `orchestrator/**`
- `script/build_and_run.sh`
- `.codex/environments/environment.toml`

运行产物：

- `dist/HippoJarvis.app`
- `.runtime/*`
- `orchestrator/data/*`
- `/Users/massif/.openchronicle/*`

## 剩余工作

### P0：模型配置

OpenChronicle 的采集和 daemon 已可用，但长期记忆生成依赖模型 provider。

需要处理：

- 配置 `/Users/massif/.openchronicle/config.toml`
- 提供可用 `OPENAI_API_KEY` 或改成 Ollama / LM Studio / 其他 LiteLLM provider
- 重新验证 writer/reducer/classifier

### P1：UI polish

OpenChronicle real adapter v1 已完成，可以进入 UI 美化阶段。

建议优先级：

1. 状态栏 Popover 做成更强 Jarvis HUD。
2. Activity Center 做成 Signal Timeline。
3. Settings 降级成 Developer Console 风格。
4. Skill Library 做成 Artifact Vault。

### P1：更多 real adapter

下一批可以接实：

- ownscribe：会议录音、转写、总结。
- cua-driver：真实插入、点击、输入、应用控制。
- vlmac：视频/屏幕理解和归档。
- basic-memory：结构化长期知识和 note preview。

### P2：Demo 主路径收口

需要把以下链路从 mock-first 推到真实联动：

1. `Jarvis ON` 同时启动 ownscribe、OpenChronicle、vlmac。
2. 会议结束后汇总 transcript、context timeline、video artifacts。
3. Active Task detector 使用真实 context 判断介入时机。
4. cua-driver 执行插入，但所有外部可见动作仍需用户确认。
5. Pattern detector 将可复用模式沉淀为 Skill。

## 当前状态一句话

HippoDEMO 现在已经具备一个可运行的 macOS Jarvis 外壳、mock-first Active Task 主路径、真实 OpenChronicle 上下文采集适配器，以及可继续接入 ownscribe/cua/vlmac/basic-memory 的 Orchestrator 模式。

---

## 2026-05-12：Jarvis UI Polish v2 与事件历史接口

本轮目标是把前端从“可用控制台”升级为更接近 Jarvis 的 macOS 状态栏助理体验，同时补齐 Activity Center 所需的真实事件历史接口。

### 状态栏 Popover：Jarvis HUD v2

完成内容：

- `MenuBarRootView` 从普通纵向控制面板改为 HUD 布局。
- 顶部加入中心状态核，显示 Jarvis 当前状态和语义状态。
- 中部加入环境信号区，展示 OpenChronicle、ownscribe、cua-driver、vlmac 的服务灯。
- 主动作区只突出一个当前最重要动作：
  - `Jarvis 启动`
  - `Jarvis 停止`
  - `Finish Capture`
  - `Insert`
  - `Generate Skill`
- `Capture Skill` 与 `Jarvis ON/OFF` 继续保持语义独立，不合并。
- 底部工具区改为圆形 icon button：
  - Activity
  - Skills
  - Settings
  - Refresh
  - Language
  - Quit

相关文件：

- `Sources/HippoJarvis/Views/MenuBarRootView.swift`

### Settings：Developer Console

完成内容：

- `SettingsView` 从普通设置表单调整为后台开发者控制台。
- 顶部展示 Orchestrator / Runtime 状态总览。
- 增加紧凑服务矩阵，展示服务状态灯、状态值、最近 detail。
- OpenChronicle 控制区继续保留：
  - Start
  - Stop
  - Pause
  - Resume
  - Capture Once
  - Timeline Tick
  - Rebuild Index
- Settings 仍定位为后台控制台，不进入主路径。

相关文件：

- `Sources/HippoJarvis/Views/SettingsView.swift`

### Activity Center：Signal Timeline

完成内容：

- 新增真实后端事件历史接口：

```text
GET /events/history?limit=50
```

- Orchestrator 返回近期 `OrchestratorEvent` 历史。
- Swift 侧新增 `EventRecord`，并在 `AppStateStore` 中维护 `eventHistory`。
- Activity Center 改为三栏信息结构：
  - Sidebar：Current / Signals / Tasks
  - 主区域：Signal Timeline
  - 右侧详情：当前 signal、task、artifacts、service health
- Timeline 只展示短信息：时间、事件类型、来源、状态。
- 无事件时使用当前 `AppSnapshot` 派生 `Current Signal`，避免空白页。

相关文件：

- `orchestrator/store.py`
- `orchestrator/main.py`
- `Sources/HippoJarvis/Models/AppModels.swift`
- `Sources/HippoJarvis/Services/OrchestratorClient.swift`
- `Sources/HippoJarvis/Stores/AppStateStore.swift`
- `Sources/HippoJarvis/Views/ActivityCenterView.swift`

### Skill Library：Artifact Vault

完成内容：

- `SkillLibraryView` 保留 `NavigationSplitView`，但视觉改为 artifact vault。
- Sidebar 行增加来源类型、创建时间和短 ID。
- Detail 顶部加入 artifact header，展示 Skill 名称、来源 session/task、生成方式、大小。
- 内容区保留纯 SwiftUI `Text` 的 Markdown 预览，不引入新 Markdown 渲染依赖。
- 删除 Skill 的 destructive action 仍保留在详情页右上角。

相关文件：

- `Sources/HippoJarvis/Views/SkillLibraryView.swift`

### 共享组件收口

新增或扩展的共享 UI 组件：

- `HUDSection`
- `ServiceLight`
- `SignalMetric`
- `TimelineRow`
- `ArtifactBadge`
- `StatusVisuals`

这些组件统一承载状态灯、指标卡、timeline row、artifact badge 和颜色映射，避免各页面重复实现。

相关文件：

- `Sources/HippoJarvis/Components/GlassSurface.swift`

### 文案与本地化

新增多组 `AppLocalization` key，覆盖：

- Artifact Vault
- Developer Console
- Environment Signals
- Service Matrix
- Signal Timeline
- Current Signal
- Markdown Preview
- Generated By
- Health
- Integrations

中英文都已补齐，避免在 view 内硬编码中英文长句。

相关文件：

- `Sources/HippoJarvis/Support/AppLocalization.swift`

### Orchestrator 启动链路修复

验证过程中发现 `HippoJarvis` app bundle 启动后，Orchestrator 健康检查偶发无法 ready。

原因：

- 通过 shell 间接启动 uvicorn 时，macOS app 环境下 shell 初始化可能卡在启动脚本或 `path_helper`，导致 uvicorn 实际没有执行。

修复：

- `OrchestratorLauncher` 改为直接用 Swift `Process` 启动并持有 uvicorn 子进程。
- 设置明确的 cwd、`PYTHONPATH`、`HIPPODEMO_ROOT`。
- 标准输出和错误写入 `.runtime/orchestrator-app.log`。
- app 存活期间 Orchestrator 进程稳定保持。

相关文件：

- `Sources/HippoJarvis/Services/OrchestratorLauncher.swift`

### 验证记录

通过的验证命令：

```bash
python -m compileall orchestrator
swift build --product HippoJarvis
./script/build_and_run.sh --verify
```

结果：

- Python compileall 通过。
- Swift build 通过。
- `HippoJarvis` app process 启动成功。
- Orchestrator `/health` ready。
- `GET /events/history` 返回数组。
- `Jarvis ON/OFF` 后 history 中出现：
  - `session_started`
  - `active_task_generated`
  - `artifact_ready`
  - `session_stopped`
- OpenChronicle start / capture-once 后 history 中出现：
  - `openchronicle_command`

### 视觉 sanity check

已用实际 app 截图检查：

- 状态栏 Popover：HUD 布局可显示，无明显重叠。
- Activity Center：无事件 fallback 为 `Current Signal`，不会空白。
- Settings：Developer Console 页面可打开，服务矩阵和 OpenChronicle 控制区可见。
- Skill Library：Artifact Vault 可展示已有 `Investor Follow-up Skill`，Markdown 预览正常。

### 当前建议下一步

UI polish v2 已完成。下一步不建议继续纯视觉美化，建议进入 DEMO 主路径接实：

1. ownscribe real adapter：把 `Jarvis ON/OFF` 接到录音、转写、总结。
2. Active Task 生成器 v1：基于会议纪要和当前 surface 生成可插入任务。
3. cua-driver adapter：接入最小可控的 computer use 动作。
4. Intervention timing detector v0：用 OpenChronicle context + surface 规则判断可介入时机。
5. Project_Cortex Skill 闭环：把可复用模式沉淀为 `SKILL.md` 并进入 Artifact Vault。

## 2026-05-12 ownscribe real adapter v1 接入记录

### 接入内容

- 新增 ownscribe real adapter，作为 Jarvis 会议录音、转写、总结链路的真实适配层。
- `Jarvis ON` 时启动 ownscribe 录音流程。
- `Jarvis OFF` 时停止 ownscribe，并 ingest summary、transcript、audio 三类产物。
- 失败时保留 fallback 路径，避免 ownscribe 不可用时阻断 Jarvis 主流程。
- 事件历史补齐 ownscribe 启停、ingest、fallback 等关键事件，便于在 Activity Center 追踪。
- Swift 侧 POST timeout 已拉长，避免停止录音和 ingest 阶段因耗时较长被过早取消。

### 当前状态

- 接入链路已按 real adapter v1 落到 Jarvis ON/OFF 主路径。
- 当前本机环境缺少 ownscribe runtime 依赖，因此 real recording 仍需安装依赖后再做端到端实录验证。

## 2026-05-13 ownscribe adapter review 修复与验证

### 修复内容

- 修复 Orchestrator 事件总线的 backpressure 风险：`EventBus.publish()` 改为非阻塞写入 SSE queue，避免慢订阅者在 `store._lock` 内拖住状态更新。
- 为 `Jarvis OFF` 的 ownscribe stop 增加受控超时：默认 `HIPPODEMO_OWNSCRIBE_STOP_TIMEOUT_SECONDS=45`，随后快速 terminate/kill，避免 demo 结束录制时长时间卡住。
- ownscribe start 增加启动后快速退出检测；如果依赖缺失或进程立刻退出，会进入明确 error 状态并保留 fallback 主路径。
- Swift `OrchestratorClient` 现在会透传 FastAPI `detail` 错误内容，前端不再只显示泛化 HTTP 状态码。
- 修复 `OrchestratorLauncher` 在 Swift error enum 调整后的编译调用点。

### 验证记录

通过的验证命令：

```bash
python -m compileall orchestrator
swift build --product HippoJarvis
./script/build_and_run.sh --verify
```

补充验证：

- `/health` 返回 ok。
- `EventBus.publish()` 在 SSE queue 已满时不会挂起，history 仍能记录最新事件。
- 使用受控缺失依赖场景验证 `Jarvis ON/OFF`：ownscribe 失败会写入 `ownscribe_recording_failed`，并生成 fallback artifacts 与 `active_task_generated`，主流程不会中断。

### 剩余阻塞

- 本机尚未具备完整 ownscribe audio capture runtime：没有可用的 ownscribe `.venv` / `uv` / audio helper，真实麦克风和系统音频采集仍需下一步安装验证。
- ASR 和总结将改走 vLLM OpenAI-compatible 接口，因此 demo 主路径不再要求 WhisperX 或 llama.cpp。

## 2026-05-13 vLLM ASR 路线调整

### 调整内容

- ownscribe adapter 不再直接调用 ownscribe 的 `run_pipeline(config)`，避免默认进入 WhisperX 转写和 local llama.cpp 总结。
- child process 现在只使用 ownscribe 的音频 recorder 产出 `recording.wav`。
- `Jarvis OFF` 后由 Orchestrator 调用 vLLM OpenAI-compatible API：
  - `/v1/audio/transcriptions` 生成 `transcript.md` / `transcript.json`
  - `/v1/chat/completions` 可选生成 `summary.md` / `summary.json`
- 新增环境变量：
  - `HIPPODEMO_VLLM_BASE_URL`
  - `HIPPODEMO_VLLM_ASR_BASE_URL`
  - `HIPPODEMO_VLLM_ASR_MODEL`
  - `HIPPODEMO_VLLM_SUMMARY_BASE_URL`
  - `HIPPODEMO_VLLM_SUMMARY_MODEL`
  - `HIPPODEMO_VLLM_API_KEY`
  - `HIPPODEMO_VLLM_TIMEOUT_SECONDS`
- 如果未显式配置 ASR model，adapter 会尝试从 vLLM `/v1/models` 自动读取第一个 model id。

### 验证记录

通过的验证命令：

```bash
python -m compileall orchestrator
swift build --product HippoJarvis
./script/build_and_run.sh --verify
```

补充验证：

- 使用本地假 vLLM server 验证 `/v1/audio/transcriptions` 和 `/v1/chat/completions` postprocess 路径，能正确写出 transcript 和 summary artifacts。
- `/state` 中 ownscribe service detail 已显示 `asr=vllm`。

## 2026-05-13 ASR provider 抽象

### 调整内容

- 将 ownscribe adapter 的 ASR 路径从 vLLM 专名抽象为 remote ASR provider。
- 默认 provider 为 `openai-compatible`；`vllm` 只是兼容 alias。
- 新增通用配置变量：
  - `HIPPODEMO_ASR_PROVIDER`
  - `HIPPODEMO_ASR_BASE_URL`
  - `HIPPODEMO_ASR_MODEL`
  - `HIPPODEMO_ASR_API_KEY`
  - `HIPPODEMO_ASR_LANGUAGE`
  - `HIPPODEMO_ASR_RESPONSE_FORMAT`
  - `HIPPODEMO_SUMMARY_PROVIDER`
  - `HIPPODEMO_SUMMARY_BASE_URL`
  - `HIPPODEMO_SUMMARY_MODEL`
  - `HIPPODEMO_SUMMARY_API_KEY`
  - `HIPPODEMO_OPENAI_COMPATIBLE_BASE_URL`
  - `HIPPODEMO_OPENAI_COMPATIBLE_API_KEY`
  - `HIPPODEMO_HTTP_TIMEOUT_SECONDS`
- 保留 `HIPPODEMO_VLLM_*` 作为向后兼容变量。
- ASR response parser 兼容 `text`、`transcript`、`result.text`、`result.transcript`、`segments[].text`、`segments[].sentence`。
- PRD 已补 Remote ASR Provider 章节，明确三方 API 平台优先走 OpenAI-compatible 协议。

### 验证记录

- `python -m compileall orchestrator` 通过。
- `swift build --product HippoJarvis` 通过。
- `./script/build_and_run.sh --verify` 通过。
- 使用无网络 monkeypatch smoke 验证：
  - `openai-compatible` provider 分发正常。
  - ASR 和 summary 可以使用独立 API key。
  - 自动 `/v1/models` 获取 model 正常。
  - 第三方常见 `result.transcript` 返回格式能生成 transcript artifact。
- `/state` 中 ownscribe service detail 已显示 `asr_provider=openai-compatible`。

## 2026-05-13 ownscribe audio helper 与真实 ASR 实录验证

### 调整内容

- 构建 `ownscribe-audio` helper 到 `ownscribe/bin/ownscribe-audio`。
- 将 helper 添加到 macOS `录屏与系统录音` 权限列表，并补充到 `仅系统录音` 列表。
- 给 helper 增加 `--display` 模式，直接捕获第一个显示器，避免后台 Jarvis 路径依赖 ScreenCaptureKit 内容选择器。
- ownscribe Python recorder 支持通过 `OWNSCRIBE_AUDIO_DISPLAY=1` 传递 `--display`。
- Orchestrator ownscribe adapter 默认设置 `OWNSCRIBE_AUDIO_DISPLAY=1`。
- Orchestrator 在 ASR 上传前自动用 `afconvert` 转成 16kHz mono Int16 WAV，降低三方 ASR 请求体积。
- 修复 adapter 子进程启动方式：从 `start_new_session=True` 改为同一登录 session 内的新 process group，避免 ScreenCaptureKit 在 detached session 内拿不到 display。

### 验证记录

- `python -m compileall orchestrator ownscribe/src/ownscribe/audio/coreaudio.py` 通过。
- `swift build --product HippoJarvis` 通过。
- `./script/build_and_run.sh --verify` 通过。
- SiliconFlow `TeleAI/TeleSpeechASR` 的 OpenAI-compatible `/v1/audio/transcriptions` 已验证可用，返回结构为 `{ "text": "..." }`。
- 使用本地 `say` 生成测试语音，并转成 16kHz mono WAV 后，adapter 可生成 `transcript.md`。
- `ownscribe-audio capture --display` 可捕获系统播放音频，最终 peak 非 0。
- adapter 级真实 smoke 通过：
  - start 成功进入 recording。
  - 播放本地测试音。
  - stop 后生成 `recording.wav` 与 `transcript.md`。
- Orchestrator 主路径验证通过：
  - `POST /session/jarvis-on` 启动真实 ownscribe recording。
  - 播放本地测试音。
  - `POST /session/jarvis-off` 停止录音、转码、调用 TeleSpeechASR。
  - 生成 `meeting_transcript` artifact、`audio_recording` artifact 和 Active Task。

### 注意

- 本轮使用的是测试 ASR key，只作为环境变量参与验证，没有写入仓库、PRD 或 changelog。
- 录音开始前 3 秒如果没有播放声音，helper 仍可能输出一次 silence warning；只要最终 peak 非 0 且 transcript 生成成功，不影响 demo 主链路。

## 2026-05-13 会议纪要 Summary Prompt 模板接入

### 调整内容

- 新增 `orchestrator/prompts/meeting_summary_zh.md`，作为默认会议纪要 system prompt。
- prompt 采用高密度、结构化、三层金字塔输出策略，并要求事实锚定、宁缺毋滥、用户标记优先。
- ownscribe adapter 的 summary 阶段默认读取该模板。
- `HIPPODEMO_SUMMARY_SYSTEM_PROMPT` 和 `HIPPODEMO_VLLM_SUMMARY_SYSTEM_PROMPT` 仍保留为最高优先级覆盖项。
- 默认 user prompt 改为只传入会议转写文本，避免把格式要求分散在多处。

### 验证记录

- 无网络 monkeypatch smoke 通过：summary 请求中的 system message 已包含 `你是会议纪要专家`、`三层金字塔`、`宁缺毋滥` 等模板关键约束。

## 2026-05-13 真实系统音频 + ASR + Summary 端到端验证

### 验证配置

- ASR：OpenAI-compatible `/v1/audio/transcriptions`，model 为 `TeleAI/TeleSpeechASR`。
- Summary：OpenAI-compatible `/v1/chat/completions`，model 为 `Qwen/Qwen2.5-7B-Instruct`。
- Orchestrator 临时端口：`127.0.0.1:8791`。
- 测试 key 只通过环境变量参与运行，未写入仓库文件。

### 验证记录

- 第一轮测试在用户播放视频时执行，系统音频混音被 ownscribe 一并捕获，ASR transcript 混入视频声音；该结果确认当前 display capture 捕获的是系统混音，而不是单一应用音频。
- 暂停外部视频声音后复跑第二轮，session 为 `session_4d4863952d95`。
- `POST /session/jarvis-on` 后 ownscribe 进入 `recording`。
- 播放本地中文会议音频后调用 `POST /session/jarvis-off`，后处理完成并返回 `200`。
- 生成文件：
  - `orchestrator/data/ownscribe/session_4d4863952d95/recording.wav`
  - `orchestrator/data/ownscribe/session_4d4863952d95/recording.asr.wav`
  - `orchestrator/data/ownscribe/session_4d4863952d95/transcript.md`
  - `orchestrator/data/ownscribe/session_4d4863952d95/summary.md`
- Orchestrator ingest artifact：
  - `meeting_transcript`: `orchestrator/data/artifacts/artifact_ec7b36f8353d_meeting_transcript.md`
  - `meeting_minutes`: `orchestrator/data/artifacts/artifact_6246e6cfe1e2_meeting_minutes.md`
  - `audio_recording`: `orchestrator/data/artifacts/artifact_ded1955699b5_audio_recording.md`
- `/events/history` 出现 `session_started`、`ownscribe_recording_started`、`artifact_ready`、`ownscribe_recording_stopped`、`ownscribe_artifacts_ingested`、`active_task_generated`、`session_stopped`。

### 结论

- 真实链路已跑通：系统音频捕获 -> 16kHz WAV 转码 -> TeleSpeechASR 转写 -> summary prompt -> chat completion -> `meeting_minutes` artifact。
- 当前风险：display/system audio capture 会录入所有系统声音；正式 demo 前需要保持其他应用静音，或后续升级为按应用/会议软件定向捕获。

## 2026-05-13 ownscribe 音频源抽象

### 调整内容

- Orchestrator ownscribe adapter 新增音频源配置：
  - `HIPPODEMO_OWNSCRIBE_AUDIO_SOURCE=system`
  - `HIPPODEMO_OWNSCRIBE_AUDIO_SOURCE=mic`
  - `HIPPODEMO_OWNSCRIBE_AUDIO_SOURCE=both`
- 新增 `HIPPODEMO_OWNSCRIBE_MIC_DEVICE`，用于指定系统麦克风设备；为空时使用默认输入设备。
- `system` 保持当前默认行为：通过 CoreAudio display capture 录系统/会议软件声音。
- `mic` 走 Swift helper `--mic-only`，只录现场麦克风，适合线下实时会议。
- `both` 走 Swift helper `--mic`，将系统声与麦克风混合到同一 `recording.wav`，适合线上会议同时保留远端参会者和本机发言。
- ownscribe service detail 现在会暴露 `audio_source` 和 `mic_device`，方便前端 Settings/Developer Console 显示当前录音模式。

### 验证记录

- `python -m compileall orchestrator` 通过。
- `bash ownscribe/swift/build.sh` 通过，已重新构建 `ownscribe/bin/ownscribe-audio`。
- `swift build --product HippoJarvis` 通过。
- adapter 私有配置方法 smoke 通过：默认音频源为 `system`，可通过环境变量切换到 `mic` 或 `both`。
- `ownscribe-audio --help` 已显示 `--mic-only`。
- helper 命令构造 smoke 通过：
  - `mic` 只传 `--mic-only`，不会传 `--display`。
  - `both` 同时传 `--display --mic`。
- `ownscribe-audio list-devices` 在 macOS 权限上下文下可看到 `MacBook Air麦克风` 默认输入设备。

### 注意

- 麦克风录制需要 macOS 麦克风权限；正式 demo 前需要给运行 Orchestrator/ownscribe helper 的进程授予麦克风权限。
- 本轮没有把麦克风音频上传 ASR；短录探针用于本地 WAV 验证，但当前还需要完成麦克风权限/优雅停止路径验证。
- `both` 会混入房间环境声；正式远程 demo 如果只想录会议软件声音，应继续使用 `system`。

## 2026-05-13 录音时间戳对齐与 mic-only 验证

### 调整内容

- ownscribe adapter 子进程新增 `recording_timeline.json`。
- timeline 记录：
  - `recording_started_at`
  - `recording_start_requested_at`
  - `recording_stop_requested_at`
  - `recording_stopped_at`
  - epoch seconds
  - monotonic seconds
  - `wall_duration_seconds`
  - `monotonic_duration_seconds`
  - `audio_file.duration_seconds`
  - `audio_source`
  - `mic_device`
- 明确 offset 对齐公式：`wall_time = recording_started_at + audio_offset_seconds`。
- Orchestrator `ownscribe_artifacts()` 会 ingest `recording_timeline.json` 为 `recording_timeline` artifact。
- `/state` 的 artifact payload 现在暴露 `created_at` 与 `metadata`，便于 Swift 前端展示 timeline / source_path。

### 验证记录

- `python -m compileall orchestrator ownscribe/src/ownscribe/audio/coreaudio.py` 通过。
- `swift build --product HippoJarvis` 通过。
- 临时 Orchestrator 使用 `HIPPODEMO_OWNSCRIBE_AUDIO_SOURCE=mic` 跑通 mic-only 实录。
- 验证 session：`session_516832bdc929`。
- 生成文件：
  - `orchestrator/data/ownscribe/session_516832bdc929/recording.wav`
  - `orchestrator/data/ownscribe/session_516832bdc929/recording.asr.wav`
  - `orchestrator/data/ownscribe/session_516832bdc929/transcript.md`
  - `orchestrator/data/ownscribe/session_516832bdc929/summary.md`
  - `orchestrator/data/ownscribe/session_516832bdc929/recording_timeline.json`
- `recording_timeline.json` 样本：
  - `audio_source=mic`
  - `recording_started_at=2026-05-13T19:45:33.404618+08:00`
  - `recording_stopped_at=2026-05-13T19:46:30.907898+08:00`
  - `wall_duration_seconds=57.50343871116638`
  - `audio_file.duration_seconds=57.2`
- Orchestrator 返回 artifact 包含：
  - `meeting_transcript`
  - `meeting_minutes`
  - `audio_recording`
  - `recording_timeline`
- `/events/history` 出现 `session_started`、`ownscribe_recording_started`、多条 `artifact_ready`、`ownscribe_recording_stopped`、`ownscribe_artifacts_ingested`、`active_task_generated`、`session_stopped`。

### 注意

- 当前 `recording_started_at` 取自 recorder start 返回后的 wall-clock 时间，足够用于 demo 和分钟级/秒级会议对齐；如果后续需要逐词级严格同步，应让 Swift helper 输出 first audio buffer host time 与 wall-clock anchor。

## 2026-05-13 ownscribe 配置 API 与前端控制台

### 调整内容

- 新增 Orchestrator 接口：
  - `GET /integrations/ownscribe/config`
  - `POST /integrations/ownscribe/config`
  - `GET /integrations/ownscribe/audio-devices`
  - `GET /integrations/ownscribe/preflight?network=false`
- 新增 `orchestrator/data/ownscribe_config.json` 作为 ownscribe 非密配置落盘位置。
- 配置项包括：
  - `audio_source`: `system` / `mic` / `both`
  - `mic_device`
  - `audio_display`
- preflight 默认只做本地检查；只有显式 `network=true` 才探测 `/v1/models`。
- API 不返回 ASR/Summary API key，避免密钥进入 `/state`、事件历史或 changelog。
- Swift 新增 ownscribe 配置、设备、preflight、recording timeline 相关 Codable 模型，并补 `Sendable` 以满足 Swift 6 并发检查。
- `OrchestratorClient` 新增 ownscribe config/devices/preflight 调用。
- `AppStateStore` 新增 `ownscribeConfig`、`ownscribeDevices`、`ownscribePreflight` 状态与更新方法。
- `SettingsView` 新增 Audio Capture 控制区：
  - ownscribe service light
  - `System Audio / Mic Only / System + Mic` 三段选择
  - 麦克风设备选择
  - 本地刷新与 preflight 按钮
  - preflight checks 矩阵
- `ActivityCenterView` 新增 Recording Timeline 结构化展示：
  - 音频源
  - 开始/结束时间
  - wall duration
  - audio duration
  - data format
  - 对齐公式

### 验证记录

- `python -m compileall orchestrator ownscribe/src/ownscribe/audio/coreaudio.py` 通过。
- FastAPI `TestClient` smoke 通过：
  - `GET /integrations/ownscribe/config`
  - `GET /integrations/ownscribe/audio-devices`
  - `GET /integrations/ownscribe/preflight`
  - `POST /integrations/ownscribe/config` 切换 `mic` 后再切回 `system`
- `rg` 检查确认测试 API key 没有写入 `ownscribe_config.json`、`state.json` 或 session JSON。
- `swift build --product HippoJarvis` 通过。
- `./script/build_and_run.sh --verify` 通过，app 进程与 Orchestrator health 均正常。
- 运行中的 `127.0.0.1:8787` 验证：
  - `GET /integrations/ownscribe/config` 返回 `audio_source=system`。
  - `GET /integrations/ownscribe/preflight` 返回本地检查结果，并显示 2 个输入设备可见。
  - app-managed Orchestrator 当前未配置 ASR/Summary model，因此 preflight 正确标记 `asr_model` 与 `summary_model` 为未配置。

### 注意

- 当前配置 API 只管理非密运行配置；ASR/Summary provider key 仍应通过环境变量或后续安全配置入口提供。

## 2026-05-13 ownscribe Runtime Provider 本地配置

### 调整内容

- 将 ownscribe ASR/Summary provider 配置扩展到 `POST /integrations/ownscribe/config`：
  - `asr_provider`
  - `asr_base_url`
  - `asr_model`
  - `asr_api_key`
  - `summary_provider`
  - `summary_base_url`
  - `summary_model`
  - `summary_api_key`
- 密钥不进 macOS Keychain，也不写入 `orchestrator/data/` 业务状态目录；本机运行时密钥落在 ignored 的 `.runtime/ownscribe-provider.json`。
- `GET /integrations/ownscribe/config` 与 `/preflight` 只返回：
  - provider/base URL/model
  - `asr_api_key_configured`
  - `summary_api_key_configured`
  - 不返回 raw key 或 Bearer header。
- ownscribe adapter 调用 OpenAI-compatible ASR/Summary 时优先读取 `.runtime` provider 配置，再回退到环境变量。
- HTTP/provider 错误详情增加 secret redaction，避免 provider 回显内容进入 `ServiceStatus.detail`、Swift `lastError` 或 `summary.error.txt`。
- Swift Settings 的 Audio Capture 控制台增加 Runtime Provider 配置：
  - ASR Base URL / ASR Model / ASR API Key
  - Summary Base URL / Summary Model / Summary API Key
  - key 状态只显示 configured/missing。

### 当前本机配置

- ASR provider: OpenAI-compatible
- ASR base URL: `https://api.siliconflow.cn/v1`
- ASR model: `TeleAI/TeleSpeechASR`
- ASR key: 已写入 `.runtime/ownscribe-provider.json`，未写入源码、PRD、changelog、`orchestrator/data` 或 Keychain。
- Summary provider 入口已具备，但 summary model/key 仍未配置，等待指定模型后再接入。

### 验证记录

- `python -m compileall orchestrator` 通过。
- FastAPI `TestClient` redaction 回归通过：
  - 临时写入测试 ASR/Summary key。
  - 验证 `/integrations/ownscribe/config`、`/integrations/ownscribe/preflight`、`/state`、`/events/history` 不包含 raw key 或 Bearer header。
  - 清理测试 key。
- `swift build --product HippoJarvis` 通过。
- `./script/build_and_run.sh --verify` 通过。
- 运行中的 `127.0.0.1:8787` 验证：
  - `/integrations/ownscribe/config` 返回 `asr_api_key_configured=true`，且不回显 key。
  - `/integrations/ownscribe/preflight?network=true` 可见 SiliconFlow `/v1/models`，ASR endpoint 检查通过。
  - Summary model 未配置，因此整体 preflight 仍为 `ok=false`，这是预期状态。

## 2026-05-13 cua-driver 最小真实执行层

### 调整内容

- 新增 `orchestrator/adapters/cua_driver.py`：
  - 自动寻找 `HIPPODEMO_CUA_DRIVER_BINARY`、`cua/libs/cua-driver/.build/debug/cua-driver`、release/app bundle 或 PATH 中的 `cua-driver`。
  - `status()` 检查 binary、daemon 和 `list_apps` 可用性。
  - `insert_text()` 默认要求 `cua-driver serve` daemon 已运行；没有 daemon 时不直接向前台应用打字，返回可解释失败。
  - 支持 `HIPPODEMO_CUA_TARGET_BUNDLE_ID` / `HIPPODEMO_CUA_TARGET_APP` 指定目标 app。
  - 默认拒绝 Terminal / iTerm / Ghostty / Warp 等高风险活动目标。
- Orchestrator 新增：
  - `GET /integrations/cua/status`
  - `/state` 会刷新 `cua-driver` 服务灯。
  - `/active-task/{task_id}/confirm` 不再把所有 action 标成 `inserted_mock`；会解析 `insert_draft` action，调用 cua adapter，成功标记 `inserted`，失败标记 `insert_failed`。
- 新增事件：
  - `cua_insert_requested`
  - `cua_insert_completed`
  - `cua_insert_failed`
- Swift `ProposedAction` 新增 `status` 字段；Activity Center action 行展示 action status。
- PRD 已同步：cua-driver 从 mock placeholder 更新为 real adapter v0，但微信/邮件专用插入仍未完成。

### 验证记录

- `swift build --product cua-driver` 在 `cua/libs/cua-driver` 通过，生成 `.build/debug/cua-driver`。
- `cua-driver call list_apps --compact` 通过，可枚举本机应用。
- FastAPI `TestClient` 使用 fake CUA result 验证 Active Task confirm 路径通过：
  - 生成 `cua_insert_requested`
  - 生成 `cua_insert_completed`
  - action status 变为 `inserted`
  - task state 进入 `task_reviewing`
- `./scripts/build-app.sh debug` 通过，生成 `.build/CuaDriver.app`，bundle identifier 为 `com.trycua.driver`。
- 直接运行 `.build/CuaDriver.app/Contents/MacOS/cua-driver serve --no-relaunch` 可启动真实 daemon：
  - socket: `~/Library/Caches/cua-driver/cua-driver.sock`
  - Orchestrator `GET /integrations/cua/status` 返回 `online`
- TextEdit 低风险真实插入 smoke 通过：
  - 打开 `/private/tmp/hippo_cua_smoke.txt`
  - 使用 Hippo Orchestrator CUA adapter 指定 `HIPPODEMO_CUA_TARGET_BUNDLE_ID=com.apple.TextEdit`
  - 插入文本 `Hippo CUA smoke 2026-05-13 真实插入验证`
  - 通过读取 TextEdit 文档确认文本已落入目标文档

### 注意

- `open -n -g <本地 .build/CuaDriver.app> --args serve` 本轮没有稳定拉起 daemon；前台 bundle binary 可以启动。后续需要补一个 Hippo 管理的 daemon launcher。
- `check_permissions {"prompt":false}` 在 direct CLI 路径出现 Swift continuation leak 并卡住，暂不作为自动 preflight 阻塞项。
- 真实插入已经可达，但仍只验证了 TextEdit 受控目标；微信/邮件等用户真实 surface 需要等 Intervention Detector 和目标 surface 选择策略完成后再开放。
- 下一步应该做 Intervention Detector v0 或 TextEdit/Notes 低风险目标 surface 检测，然后再扩展微信/邮件。

## 2026-05-13 Intervention Detector v0 与安全 target surface

### 调整内容

- cua-driver adapter 增加 `target_surface()` preflight：
  - 检查 binary、daemon、运行中 app、当前窗口和 AX editable text element。
  - 默认只放行 TextEdit editable document。
  - 微信、邮件、浏览器、Terminal / iTerm / Ghostty、Codex / ChatGPT 等目标默认拒绝。
  - 支持 `HIPPODEMO_CUA_SAFE_BUNDLE_IDS` 作为后续经过验证的低风险 bundle allowlist。
- Orchestrator 新增：
  - `GET /integrations/cua/target-surface`
  - `POST /intervention/detect`
  - `intervention_signal_detected`
  - `intervention_signal_waiting`
- Active Task 生成时会同步当前 target surface：
  - safe 时 action status 标记为 `target_ready`
  - unsafe 时 action status 标记为 `waiting_for_target`
- `/active-task/{task_id}/confirm` 现在会先通过 target surface guard；unsafe 时不调用真实输入。
- Swift 前端新增 `CuaTargetSurface` 状态：
  - Popover Active Task 卡片展示目标 app/window 和 guard 原因。
  - Activity Center 展示同一 target surface 状态。
  - target surface unsafe 时禁用 `Insert` 按钮。
- PRD 已同步：Intervention Detector v0 和 target surface preflight 从后续目标移入当前 MVP 范围。

### 验证记录

- `python -m compileall orchestrator` 通过。
- 当前前台为 Safari 时，`GET /integrations/cua/target-surface` 返回 `safe=false`，reason 为 Safari 被 v0 guard 拦截。
- 指定 `HIPPODEMO_CUA_TARGET_BUNDLE_ID=com.apple.TextEdit` 时，target preflight 返回：
  - `safe=true`
  - `mode=textedit`
  - `element_role=AXTextArea`
  - `window_title=hippo_cua_smoke.txt`
- `swift build --product HippoJarvis` 通过。
- `./script/build_and_run.sh --verify` 通过。

### 注意

- 这不是微信/邮件专用插入；它是 CUA 执行前的安全 gate。
- 当前不会自动弹出独立 Intervention HUD；只在 Popover / Activity Center 中展示 Active Task 和 target surface。
- 后续扩展微信/邮件前，需要为每类 surface 增加专用识别、内容边界和二次确认。

## 2026-05-13 低风险编辑器 target surface 扩展

### 调整内容

- cua-driver target policy 内置低风险编辑器 allowlist：
  - TextEdit: `com.apple.TextEdit`
  - CotEditor: `com.coteditor.CotEditor`
  - Notes: `com.apple.Notes`
- 低风险编辑器仍必须通过真实 preflight：
  - app 正在运行
  - 有当前 Space 的 on-screen window
  - AX tree 中存在 editable text element
- editable element 选择策略从“第一条命中”改为按角色优先：
  - `AXTextArea`
  - `AXTextField`
  - `AXComboBox`
- 插入时会复用 preflight 得到的 `window_id` 和 `element_index`，减少只按 pid 向当前焦点打字的误投风险。
- Swift UI 的 target mode 展示从单纯 `Safe / Guarded` 扩展为具体模式：
  - `TextEdit`
  - `Low Risk Editor`
  - `Notes`
  - `Allowlisted Editor`

### 验证记录

- `python -m compileall orchestrator` 通过。
- 指定 `HIPPODEMO_CUA_TARGET_BUNDLE_ID=com.apple.TextEdit` 时，preflight 仍返回 `safe=true`、`element_role=AXTextArea`。
- 指定 `HIPPODEMO_CUA_TARGET_BUNDLE_ID=com.coteditor.CotEditor` 但本机 CotEditor 未运行时，preflight 返回 `safe=false`，不会误放行。
- 运行中的 Orchestrator `/integrations/cua/target-surface` 在没有安全前台目标时返回 `safe=false`，提示聚焦 TextEdit / CotEditor / Notes。
- `swift build --product HippoJarvis` 通过。
- `./script/build_and_run.sh --verify` 通过。

## 2026-05-13 cua-driver daemon launcher

### 调整内容

- Orchestrator 新增 cua-driver 管理接口：
  - `POST /integrations/cua/start`
  - `POST /integrations/cua/stop`
  - `POST /integrations/cua/restart`
- `cua_driver.py` 的启动策略改为：
  - 若检测到本地 `.build/CuaDriver.app` bundle，优先调用 `/usr/bin/open -n -g <CuaDriver.app> --args serve`。
  - 这样 daemon 通过 LaunchServices 启动，macOS TCC 权限归属到 `com.trycua.driver`，不再依赖 HippoJarvis / uvicorn 子进程直接持有 Accessibility + Screen Recording 权限。
  - 只有没有 app bundle 时才 fallback 到 direct binary `serve --no-relaunch`。
- `stop` / `restart` 增加 daemon 状态轮询，避免 socket 和 lock 尚未释放时立刻重启。
- Settings Developer Console 和 Dashboard 增加 CUA Driver 控制区：
  - Start
  - Stop
  - Restart
  - 当前 service status / detail
- Orchestrator 事件历史新增 `cua_driver_command`，记录 start / stop / restart 结果。
- PRD 已同步：CUA 控制接口从“建议手动启动 CuaDriver.app”更新为 Orchestrator 可管理 daemon。

### 验证记录

- `python -m compileall orchestrator` 通过。
- `swift build --product HippoJarvis` 通过。
- `./script/build_and_run.sh --verify` 通过。
- `POST /integrations/cua/restart` 通过：
  - 返回 `cua-driver` status `online`
  - detail 显示 `LaunchServices bundle=/Users/massif/Desktop/HippoDEMO/cua/libs/cua-driver/.build/CuaDriver.app`
  - daemon pid: `60709`
- `GET /integrations/cua/status` 返回 `online`。
- `GET /events/history?limit=8` 可见 `cua_driver_command` / `restart` 事件。

### 注意

- 旧记录中“`open -n -g <本地 .build/CuaDriver.app> --args serve` 本轮没有稳定拉起 daemon”的结论已被本节取代；当前 Orchestrator 启动路径已经验证可用。
- CUA launcher 解决的是 daemon 生命周期管理，不代表微信/邮件等外部可见 surface 已经开放；插入仍受 target surface preflight 和用户确认约束。
