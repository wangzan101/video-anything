# video-anything 视频下载契约

- 日期：2026-07-24
- 状态：Phase 0 冻结契约
- 适用范围：`scripts/fetch.sh` / `scripts/fetch.py` 的下载、校验、发布、恢复语义，以及对外公开文档里与下载相关的承诺
- 非目标：`scripts/transcribe.py`、摘要/改写/playbook、ASR 工作流、下游 agent 工作流

本契约只冻结“URL -> 可验证下载产物”的行为。任何实现都必须以本契约为准；公共文档只能在不超出本契约的前提下做临时状态标注。未验证平台使用 `provisional`/`experimental`，明确不在 v1 范围内的平台可以使用 `unsupported`。

## 1. CLI 契约

保留现有入口：

```bash
bash scripts/fetch.sh "<URL>" [OUTPUT_ROOT]
```

新增但不破坏旧调用：

```bash
bash scripts/fetch.sh "<URL>" [OUTPUT_ROOT] [--force]
```

约束：

- `URL` 必须是单个公开可访问视频 URL。
- `OUTPUT_ROOT` 省略时使用项目默认输出根目录；实现不得把成功结果写到仓库根目录之外的任意隐式位置。
- `--force` 只用于强制重建与可恢复发布，不改变默认入口形状。
- 失败时 stdout 必须为空；成功时 stdout 只允许输出一行最终目录路径。

## 2. 固定环境变量

下载行为只允许通过以下显式环境变量配置：

- `VA_HOME`
- `VA_COOKIES_FROM_BROWSER`
- `VA_COOKIES`
- `VA_YTDLP_JS_RUNTIME=auto|deno|node|none`

约束：

- 不得读取宿主机的 yt-dlp 配置文件作为默认行为来源。
- 不得把浏览器 cookie、cookie 文件内容或敏感查询参数写入 stdout、manifest 或日志正文。
- `VA_YTDLP_JS_RUNTIME` 的非法值必须报 `DEPENDENCY_ERROR`。

## 3. 成功产物

只有当所有必需产物都通过验证并被发布后，调用才允许退出 `0`。

```text
OUTPUT_ROOT/<extractor>-<id>/
├── video.mp4
├── audio.wav
├── info.json
├── manifest.json
├── thumbnail.*        # 可选
├── sub.*.vtt          # 可选
└── fetch.log
```

成功判定：

- `video.mp4` 必须是真实可解析的 MP4 / ISO BMFF，且至少包含一个视频流。
- `audio.wav` 只在源视频存在音轨时才是必需产物，必须可解析为 PCM WAV、16 kHz、单声道。
- `info.json` 必须是合法 JSON，且 `id`、`extractor` 与输出身份一致。
- `manifest.json` 必须是合法 JSON，`schema_version=1`、`status=ready`，并记录工具版本、格式、时长、大小、验证结果和发布元数据。
- `thumbnail.*` 与 `sub.*.vtt` 属于可选资产，缺失不构成核心失败，但其下载/转换错误必须写入 manifest warnings。

时间一致性要求：

- 当源视频含音轨时，`abs(audio_duration - video_duration)` 必须满足 `<= min(5.0, max(1.0, video_duration * 0.01))` 秒。
- 恰好等于阈值通过，超过阈值则失败。

失败条件：

- 无音轨视频必须以明确的 `MEDIA_ERROR/no_audio` 失败，不得伪装成 pipeline-ready。
- `info.json` 缺失或损坏必须失败。
- 视频没有视频流、文件截断或 ffprobe 无法解析必须失败。

## 4. 退出码

| 退出码 | 状态 | 含义 |
|---:|---|---|
| 0 | `READY` | 全部必需产物已验证并发布 |
| 2 | `USAGE_ERROR` | 参数或 URL scheme 不合法 |
| 10 | `DEPENDENCY_ERROR` | Python、yt-dlp、ffmpeg、ffprobe、Deno / Node runtime 或目标宿主不可用 |
| 20 | `RESOLVE_ERROR` | URL 无法解析、内容不支持、直播/播放列表被拒绝或访问条件不足 |
| 30 | `DOWNLOAD_ERROR` | 下载器返回失败或没有生成媒体文件 |
| 40 | `NORMALIZE_ERROR` | 无法得到真实 MP4；不得靠修改扩展名通过 |
| 50 | `MEDIA_ERROR` | 视频 / JSON / 音轨 / `audio.wav` 验证失败 |
| 60 | `PUBLISH_ERROR` | 锁、staging、恢复或发布替换失败 |

规则：

- 任何必需阶段失败都必须返回非零退出码。
- 失败时不得打印成功目录路径。
- 成功时 stderr 可以包含 human log，但 stdout 只允许最终目录路径。

## 5. 固定下载与探测行为

实现必须冻结以下下载器语义：

- 所有 yt-dlp 调用都必须显式带 `--ignore-config`。
- 默认设置 `YTDLP_NO_PLUGINS=1`。
- 必须显式使用 `--no-playlist` 和 `--match-filters !is_live`。
- 若元数据解析表明 `_type=playlist` 或存在多 entries，必须在下载前退出 `20/RESOLVE_ERROR/not_single_video`。
- 必须使用 yt-dlp `after_move:filepath` 作为真实后处理产物路径，不得通过文件名猜测结果。

固定重试与超时：

| 项目 | 固定值 |
|---|---|
| yt-dlp `--retries` | `10` |
| yt-dlp `--fragment-retries` | `10` |
| yt-dlp `--extractor-retries` | `3` |
| yt-dlp `--file-access-retries` | `3` |
| yt-dlp `--socket-timeout` | `30` |
| resolve timeout | `120s` |
| ffprobe timeout | `30s` |
| download timeout | `14400s` |
| ffmpeg timeout | `14400s` |

固定退避策略：

- http / fragment / extractor：`exp=1:8`
- file_access：`linear=1:3:1`

约束：

- 禁止把 retry / timeout 留给宿主配置或环境变量暗中覆盖。
- 禁止使用无限重试或未文档化等待。

## 6. 宿主与 runtime 矩阵

v1 目标宿主只包括：

- macOS 10.15+：`x86_64`、`arm64`
- Linux glibc 2.17+：`x86_64`、`aarch64`
- WSL：按其实际 Linux glibc / arch 落入同一矩阵

明确 unsupported：

- musl
- Linux `armv7l`
- 原生 Windows
- 其他未列出的组合

约束：

- unsupported 宿主必须在下载任何二进制前退出 `10/DEPENDENCY_ERROR/unsupported_host`。
- musl 只有在 yt-dlp、ffmpeg、ffprobe、Deno 四项资产和 clean-bootstrap 都有单独验证后，才能另立支持计划。

JS runtime 约束：

- `VA_YTDLP_JS_RUNTIME=auto` 只接受 Deno `>=2.3.0`；先找受控 `VA_HOME/bin/deno`，再找合格系统 Deno，仍缺失则 bootstrap 官方 Deno。
- `VA_YTDLP_JS_RUNTIME=deno` 与 `node` 都必须先传 `--no-js-runtimes`，再传唯一的 `--js-runtimes <runtime>:<absolute-path>`。
- `VA_YTDLP_JS_RUNTIME=node` 只有在用户显式选择且 Node `>=22.0.0` 时有效；项目不 bootstrap Node。
- `VA_YTDLP_JS_RUNTIME=none` 禁用 JS runtime；通用下载检查可以通过，但 YouTube capability 必须明确失败。
- 非法枚举值、版本过低或显式 runtime 不存在都必须退出 `10`，不得静默回退到另一 runtime。

## 7. 发布与不变性

发布目录、staging、backup、lock、transaction 与 recovery 的固定相对位置：

- `OUTPUT_ROOT/.locks/`
- `OUTPUT_ROOT/.transactions/`
- `OUTPUT_ROOT/.staging/`
- `OUTPUT_ROOT/.backups/`
- `OUTPUT_ROOT/.recovery/`

约束：

- 所有 transactional 目录必须位于同一 `OUTPUT_ROOT`，保证 rename 不跨文件系统。
- `OUTPUT_ROOT/<extractor>-<id>/manifest.json` 只有在 `status=ready` 时才可发布。
- final 中的 `manifest.json` 与 `fetch.log` 只能描述生成该 artifact 的那次运行，发布后不得被复写。
- 默认复用路径不得改写 final 的 `manifest.json`、`fetch.log`、目录 inode 或 mtime。
- 新 artifact 的 `publish_mode` 只可能是 `initial` 或 `force`，不存在 `reuse`。
- `publish_mode=initial` 时必须不包含 `replaces_fingerprint`。
- `publish_mode=force` 时必须包含 `replaces_fingerprint`，且其字段必须逐项匹配 journal 的 expected-final fingerprint。

`replaces_fingerprint` / expected-final fingerprint 结构：

- `device`
- `inode`
- `manifest_state=ready|invalid|missing`
- `manifest_sha256`

规则：

- 旧 manifest 文件存在时，`manifest_sha256` 必须是其原始字节 SHA256。
- 只有 `manifest_state=missing` 时，`manifest_sha256` 才允许为 `null`。
- 文件存在但不可读取或不可哈希时，不得开始 force transaction。

## 8. Journal、provenance 与 recovery

### 8.1 事务日志

journal 路径固定为：

```text
OUTPUT_ROOT/.transactions/<extractor>-<id>.<generation>.json
```

约束：

- `generation` 必须是每次构建生成的随机 UUID，不得复用时间戳或 PID。
- journal 必须记录完整 identity 字段、stage / backup / recovery 相对路径，以及 phase 迁移状态。
- journal 更新必须使用同目录 tmp + replace + fsync。

允许的 `phase`：

- `creating`
- `building`
- `stage_ready`
- `backup_move_started`
- `backup_moved`
- `final_move_started`
- `final_moved`
- `committed`

### 8.2 Stage provenance

stage 创建后必须原子写入不可变的 `stage/.provenance.json`。

最少字段：

- `schema_version=1`
- artifact key
- `extractor`
- `id`
- source URL SHA256
- `generation`
- `publish_mode`
- journal basename
- `created_at`

约束：

- provenance 写完并 fsync stage 目录后，journal 才能进入 `building`。
- provenance 与 journal identity 必须一致。

### 8.3 Locking

同一 `<extractor>-<id>` 同时只允许一个写者。

锁路径固定为：

```text
OUTPUT_ROOT/.locks/<extractor>-<id>.lock/
```

约束：

- 锁必须通过原子 `mkdir` 获取。
- `owner.json` 必须记录 hostname、PID、创建时间和随机 owner token。
- 第二写者不得等待，必须立即退出 `60/PUBLISH_ERROR/artifact_locked`。
- stale lock 只能在“hostname 与当前机器一致、PID 已不存在、锁年龄至少 1800 秒”三个条件同时满足时回收。
- 不同主机、owner.json 损坏或 PID 状态不可证明时必须拒绝回收并退出 `60`。

### 8.4 Recovery

恢复只在成功获取 artifact lock 后执行，且必须幂等。

固定判定顺序：

1. 按 artifact key 枚举 active journal。`>1` 立即为 `AMBIGUOUS`；`0` 时只有在同 key stage / backup 也不存在时才允许继续，否则为 `FOREIGN/AMBIGUOUS`。
2. 校验 journal schema、相对路径无越界、artifact identity 和 generation；任一失败即 `FOREIGN/AMBIGUOUS`。
3. 校验 stage 的 `.provenance.json` 与 journal identity 完全一致。stage 已被 rename 而不存在时，只允许 final manifest 的 generation / identity 与 journal 一致且 journal phase 表示 final move 可能已开始。
4. 若 journal 指向 backup，重新计算 expected-final fingerprint 并全字段比较；若 journal 指向现有新 final，则校验 final manifest 的 generation，并把其 `replaces_fingerprint` 与 journal expected-final 全字段比较。

动作约束：

- `READY` 表示 identity、`manifest.status=ready` 和全部必需产物均复验通过。
- `OWNED_INVALID` 表示由 journal / fingerprint 证明属于本 transaction，但媒体契约失败。
- `FOREIGN/AMBIGUOUS` 必须退出 `60`，且不得移动或删除任何冲突目录或 journal。
- 任何恢复函数对同一磁盘快照连续调用两次，第二次不得再改变目录状态。

### 8.5 恢复决策表

恢复只在成功获取 artifact lock 后执行。归属判定顺序固定如下，不能由实现自行调整：

| journal | final | stage | backup | 确定动作 |
|---|---|---|---|---|
| `0` | `READY` | 无 | 无 | 正常默认复用；显式 `--force` 创建新 journal 和 generation stage |
| `0` | 缺失 | 无 | 无 | 正常首次运行：创建 `publish_mode=initial` 的新 journal 和 generation stage |
| `1, creating` | 与 expected-final fingerprint 一致或原本缺失 | 无 | 无 | 证明尚未开始构建；删除该空 transaction journal，再按本次调用从正常状态开始 |
| `1, initial, final_move_started|final_moved|committed` | generation 与 journal 一致且 `READY` | 无 | 无 | 覆盖“initial rename 已发生但 phase/journal 未收尾”：复验 final，成功后写 committed、删除 journal 并返回 READY；复验失败则保留 final/journal 并退出 `60` |
| `1, force, final_move_started|final_moved|committed` | 新 generation `READY` | 无 | fingerprint 匹配，或已按 journal 处理且 final 的 `replaces_fingerprint` 逐字段匹配 | 认定第二次 rename 已完成；复验 final。仍有原 backup 时，ready backup 删除、owned-invalid backup 移入 journal 指定的 `.recovery/`；随后写 committed、删除 journal 并返回 READY |
| `1, force, backup_move_started|backup_moved|final_move_started` | 缺失 | 任意唯一 owned stage | fingerprint 匹配、可恢复 | 第一动作始终是 `backup -> final` 并 fsync，恢复调用前状态；随后把 journal phase 原子回退到与 stage 实际状态一致的 `building` 或 `stage_ready`。普通调用复用/报告恢复后的 final 并保留 stage+journal；显式 `--force` 可继续该唯一 transaction |
| `1, initial, stage_ready|final_move_started` | 缺失 | `READY` | 无 | 写入或保持 `final_move_started`，执行 `stage -> final`、fsync、推进 final_moved 并复验；成功后写 committed、删除 journal 并返回 READY |
| `1, initial, building` | 缺失 | partial | 无 | source identity 与本次请求一致时续传；不一致即退出 `60` |
| `1, force, building|stage_ready|backup_move_started` | 与 expected-final fingerprint 一致 | partial 或 `READY` | 无 | 若 phase 为 backup_move_started，先回退为 stage_ready，证明第一次 rename 尚未发生。普通调用保持 stage/journal 不变并复用 ready final；显式 `--force` 才允许续传/继续这一个恢复 transaction。没有 active journal 时的普通 `--force` 必须创建新 generation |
| `1` | 新 generation `OWNED_INVALID` | 无 | fingerprint 匹配、可恢复 | 把失败的新 final 移入 `.recovery/`，恢复 backup，复验其 fingerprint，删除 journal 并退出 `60` |
| `0` | `OWNED_INVALID` | 无 | 无 | 默认退出 `60`；显式 `--force` 创建新 journal/stage，并把 invalid final 作为 expected-final fingerprint 纳入正常 force transaction；成功后旧 invalid backup 移入 `.recovery/` |
| 任意不满足以上条件 | 任意 | 任意 | 任意 | 不移动、不删除目录或 journal，退出 `60` 并列出冲突路径，要求人工检查 |

恢复函数必须幂等：对同一磁盘快照连续调用两次，第二次不得再改变目录状态。表中每一行都必须有离线目录 fixture；initial publish、两个 force rename 边界和 backup cleanup 前都必须各有进程终止后的 next-run 测试。

## 9. 日志与敏感信息

约束：

- `stderr` 可以写 human log、阶段摘要和错误原因。
- `stdout` 只允许成功时的最终目录路径。
- `fetch.log`、journal 和 manifest 都不得包含 cookie 内容、浏览器 cookie 数据或原始敏感查询参数。
- 允许保留脱敏 URL、URL hash、工具版本、退出码和可操作诊断信息。

## 10. 对外文档约束

公开 README、README.en、SKILL.md 和 `references/platforms.md` 的未验证平台状态只能标注为 `provisional` 或 `experimental`；明确不在 v1 范围内的平台可以标注 `unsupported`。只有新 smoke 通过并形成可追溯证据，才能升级为 `supported`。

任何文档如果引用“supported / stable / solid / 一等”之类表述，都必须由最新 smoke 结果支撑；在 Phase 0 期间不得继续沿用旧口径。
