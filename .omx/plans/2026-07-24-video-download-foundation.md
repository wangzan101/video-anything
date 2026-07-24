# video-anything 视频下载地基加固计划

- 日期：2026-07-24
- 状态：APPROVED — independent Critic review passed
- 基线：`main@02f68b5`
- 范围：只加固“URL -> 可验证下载产物”链路；不进入 ASR、摘要、改写等下游功能
- 执行纪律：一次只推进一个阶段；当前阶段的门禁未通过，不进入下一阶段

## 1. 目标与边界

### 1.1 目标

把当前的 happy-path 下载脚本改造成一个可测试、可恢复、不会伪成功的下载子系统：

1. 给定一个公开可访问的单视频 URL，成功时稳定产出真实可解析的 `video.mp4`、`audio.wav`、`info.json` 和 `manifest.json`。
2. 任一必需阶段失败时返回非零退出码，不打印成功目录，不污染已发布结果。
3. 同 URL 重跑默认复用经过重新验证的结果；`--force` 在新结果验证成功前不得破坏旧结果。
4. 下载行为不受用户机器上的 yt-dlp 配置和第三方插件暗中影响。
5. macOS 与明确支持的 Linux OS/arch 组合能够从干净环境完成依赖就位。
6. 平台支持状态由真实冒烟结果决定，而不是由“yt-dlp 可能支持”推断。

### 1.2 非目标

- 不修改 `scripts/transcribe.py` 的 ASR 流程。
- 不实现云 ASR、拆分镜、选题矩阵。
- 不支持播放列表、批量任务、直播、DRM、付费墙或会员内容。
- 本阶段不开发 Kuaishou 自定义 extractor；若 upstream/Generic 路径不能通过门禁，降级文档承诺并单独立项。
- 不做原生 Windows；继续以 WSL 为 Windows 用户的支持路径。
- 不引入新的第三方 Python 包；允许继续使用项目已有的 pytest，运行时代码只用 Python 标准库。
- 不默认做全量视频转码；转码成本和画质策略留作后续显式能力。

## 2. 当前事实基线

| 问题 | 证据 | 影响 |
|---|---|---|
| 主下载失败可能仍返回成功 | `scripts/fetch.sh:18` 只有 `set -uo pipefail`；`scripts/fetch.sh:76-85` 的 yt-dlp 调用无显式检查；`scripts/fetch.sh:106-111` 无条件打印完成与目录 | Agent 会把空目录或半成品交给下游 |
| 容器格式可能被伪装 | `scripts/fetch.sh:87-90` 把任意 `video.*` 直接改名为 `video.mp4` | 文件扩展名与真实容器不一致 |
| 音频失败被吞掉 | `scripts/fetch.sh:99-104` 将 ffmpeg 失败降级为 warning | 文档承诺有 `audio.wav`，实际却可能缺失 |
| 正式目录会被半成品和旧文件污染 | `scripts/fetch.sh:73-85` 先创建最终目录并直接写入 | 重跑结果不可证明来自本次执行 |
| 设计中的复用/覆盖语义未实现 | `docs/superpowers/specs/2026-07-23-video-anything-design.md:83` 要求默认复用、`--force` 覆盖；当前 CLI 仅在 `scripts/fetch.sh:27-29` 接受 URL 和输出根目录 | 行为与设计不一致 |
| yt-dlp Linux 资产选择忽略架构 | `scripts/bootstrap.sh:25-36` 只按 OS 选择；当前 Linux 一律使用 `yt-dlp_linux` | Linux aarch64/musl 可能拿到错误二进制 |
| 下载能力检查不完整 | `scripts/check.sh:45-63` 未检查 ffprobe 和 YouTube JS runtime | “依赖就绪”不等于当前 YouTube 下载能力就绪 |
| 下载层没有自动化测试 | `tests/test_asr_utils.py:1-27` 只覆盖 ASR 纯函数；设计在 `docs/superpowers/specs/2026-07-23-video-anything-design.md:119-123` 要求平台冒烟 | 最高风险路径没有回归保护 |

已通过离线桩复现：

- yt-dlp 下载阶段返回 `42` 时，当前脚本仍打印 `done` 并最终退出 `0`。
- yt-dlp 产出 `video.webm` 时，当前脚本把它改名为 `video.mp4`；ffmpeg 解析失败后仍退出 `0`。

## 3. 目标契约

### 3.1 CLI 兼容性

保留现有入口：

```bash
bash scripts/fetch.sh "<URL>" [OUTPUT_ROOT]
```

新增但不破坏旧调用：

```bash
bash scripts/fetch.sh "<URL>" [OUTPUT_ROOT] [--force]
```

继续支持：

- `VA_HOME`
- `VA_COOKIES_FROM_BROWSER`
- `VA_COOKIES`

### 3.2 成功产物

只有下列必需产物全部通过验证，才允许发布并退出 `0`：

```text
video-out/<extractor>-<id>/
├── video.mp4
├── audio.wav
├── info.json
├── manifest.json
├── thumbnail.*        # 可选
├── sub.*.vtt          # 可选
└── fetch.log          # 脱敏诊断日志
```

验证要求：

- `video.mp4` 非空，ffprobe 能解析，真实容器为 MP4/ISO BMFF，至少包含一个视频流。
- `info.json` 是合法 JSON，且 `id`、`extractor` 与输出身份一致。
- 源视频存在音轨时，`audio.wav` 必须可解析、PCM WAV、16 kHz、单声道；`abs(audio_duration - video_duration)` 必须小于等于 `min(5.0, max(1.0, video_duration * 0.01))` 秒。
- `manifest.json` 的 `schema_version=1`、`status=ready`，记录工具版本、格式、时长、大小和验证结果。
- thumbnail、字幕属于可选资产；缺失不能把核心成功降级为失败，但其下载/转换错误必须写入 manifest warnings。

### 3.3 状态与退出码

| 退出码 | 状态 | 含义 |
|---:|---|---|
| 0 | `READY` | 全部必需产物已验证并发布 |
| 2 | `USAGE_ERROR` | 参数或 URL scheme 不合法 |
| 10 | `DEPENDENCY_ERROR` | Python、yt-dlp、ffmpeg、ffprobe 或所需 runtime 不可用 |
| 20 | `RESOLVE_ERROR` | URL 无法解析、内容不支持或访问条件不足 |
| 30 | `DOWNLOAD_ERROR` | 下载器返回失败或没有生成媒体文件 |
| 40 | `NORMALIZE_ERROR` | 无法得到真实 MP4；不得靠修改扩展名通过 |
| 50 | `MEDIA_ERROR` | 视频/JSON/音轨/audio.wav 验证失败；无音轨归入该状态并给出明确原因 |
| 60 | `PUBLISH_ERROR` | 锁、staging 或发布替换失败 |

输出规则：

- 成功：human log 写 stderr；stdout 只输出一行最终目录路径。
- 失败：stderr 输出阶段、错误摘要、诊断日志路径和可操作建议；stdout 不得输出目录路径。
- 日志和 manifest 不得包含 cookie 内容、浏览器 cookie 数据或带敏感查询参数的原始 URL；仅保存脱敏 URL 或 URL hash。

### 3.4 幂等与发布语义

- 项目内部目录固定为 `OUTPUT_ROOT/.locks/`、`OUTPUT_ROOT/.transactions/`、`OUTPUT_ROOT/.staging/`、`OUTPUT_ROOT/.backups/` 和 `OUTPUT_ROOT/.recovery/`；transaction journal、staging、backup 与 final 必须位于同一 `OUTPUT_ROOT`，保证 rename 不跨文件系统。
- generation staging 使用 `OUTPUT_ROOT/.staging/<extractor>-<id>.<generation>/`；backup 使用 `OUTPUT_ROOT/.backups/<extractor>-<id>.<generation>/`。generation 是每次构建生成的随机 UUID，不复用时间戳或 PID。
- 创建 stage 时先写入 journal `phase=creating`，再创建 stage 并原子写入 immutable `stage/.provenance.json`。provenance 固定包含 `schema_version=1`、artifact key、extractor、id、source URL SHA256、generation、`publish_mode`、journal basename 和 created_at；写完并 fsync stage 目录后才把 journal 更新为 `phase=building`。所有 journal 更新都使用同目录 tmp + replace + fsync。
- 默认重跑：只有 final 中 `manifest.status=ready` 且重新验证必需产物通过，才直接复用；否则非零退出并提示 `--force`，不得借旧文件制造成功。
- `--force`：先在独立 staging 构建并验证新结果；旧 final 在此之前保持不变。
- 首次发布可以用同文件系统 rename 原子完成。
- `--force` 替换使用锁内的“旧目录改名为 backup -> 新 staging 改名为 final -> 成功后清理 backup”；这是可回滚的两步替换，不宣称对无锁并发读者具有跨平台的原子目录交换语义。
- journal 固定为 `OUTPUT_ROOT/.transactions/<extractor>-<id>.<generation>.json`，包含 provenance 全部 identity 字段、stage/backup/recovery 相对路径、`phase=creating|building|stage_ready|backup_move_started|backup_moved|final_move_started|final_moved|committed`，以及 `expected_final_fingerprint`。initial publish 时该 fingerprint 必须为 null；force 时必须是 `{device, inode, manifest_state, manifest_sha256}`，其中 `manifest_state=ready|invalid|missing` 只描述旧 manifest 自身是否为合法 ready JSON，manifest 文件存在时对原始字节计算 SHA256，只有 missing 时 SHA256 才为 null；文件存在但不可读取/哈希时不得开始 force transaction。每次 rename 前先持久化对应 `*_move_started` 并 fsync journal 目录，rename 后再 fsync 被修改的父目录并推进到 `*_moved`；成功复验和处理 backup 后写 `committed`，最后才删除 journal。
- 同一 `<extractor>-<id>` 同时只允许一个写者。锁路径固定为 `OUTPUT_ROOT/.locks/<extractor>-<id>.lock/`，以原子 `mkdir` 获取，`owner.json` 记录 hostname、PID、创建时间和随机 owner token；第二写者不等待，立即退出 `60/PUBLISH_ERROR/artifact_locked`。
- stale lock 只在“hostname 与当前机器一致、PID 已不存在、锁年龄至少 1800 秒”三个条件同时满足时回收；不同主机、owner.json 损坏或 PID 状态不可证明时拒绝回收并退出 `60`。进程仍存在时，无论锁多旧都不得抢占。
- 下载中断产生的 yt-dlp `.part` 文件保留在 staging，用于后续恢复；失败 staging 不得出现在正式目录契约中。
- 本里程碑不按宽泛 TTL 自动清理失败 staging、异常 backup 或 recovery conflict；只在成功 transaction 已被证明完成时删除其 ready backup。其他目录保留并报告精确路径，磁盘清理另立显式、可审计任务。

### 3.5 崩溃恢复决策表

恢复只在成功获取 artifact lock 后执行。归属判定顺序固定如下，不能由实现自行调整：

1. 按 artifact key 枚举 active journal：`>1` 立即为 `AMBIGUOUS`；`0` 时只允许不存在同 key 的 stage/backup，否则为 `FOREIGN/AMBIGUOUS`；`1` 时继续。
2. 校验 journal schema、相对路径无越界、artifact identity 和 generation；任一失败即 `FOREIGN/AMBIGUOUS`。
3. stage 仍存在时，校验其 `.provenance.json` 与 journal identity 完全一致；stage 已被 rename 而不存在时，只允许 final manifest 的 generation/identity 与 journal 一致且 journal phase 表示 final move 可能已开始。存在其他同 key stage、缺失证明材料或 identity 不匹配即 `FOREIGN/AMBIGUOUS`。
4. 若 journal 指向 backup，重新计算 `{device, inode, manifest_state, manifest_sha256}` 并与 `expected_final_fingerprint` 全字段比较；若 journal 指向现有新 final，则校验 final manifest 的 generation，并把其条件必填的 `replaces_fingerprint` 与 journal expected-final 全字段比较。任一无法证明即 `FOREIGN/AMBIGUOUS`。

`READY` 表示 identity、`manifest.status=ready` 和全部必需产物均复验通过；`OWNED_INVALID` 表示由 journal/fingerprint 证明属于本 transaction，但媒体契约失败；可恢复 backup 由原 final fingerprint 判定，不以其当前媒体是否 ready 判定，因此原 final 即使本来无效也能原样回滚。

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

## 4. 架构决策

### D1. Bash 保持入口，Python 标准库负责 orchestration

方案：`scripts/fetch.sh` 退化为稳定兼容入口，实际状态机放到新建的 `scripts/fetch.py`。

原因：事务目录、结构化 manifest、subprocess 退出码、锁和故障注入在 Bash 3.2 兼容约束下会迅速变脆；项目已经依赖 Python，并已在 `scripts/fetch.sh:64-68` 调用 Python。

拒绝方案：

- 继续把所有逻辑堆在 Bash：diff 较小，但会把已经暴露的错误语义扩散到更多分支。
- 直接嵌入 yt-dlp Python API：会改变当前“独立官方二进制”的依赖模型并引入包版本耦合。

### D2. 公共契约继续提供真实 MP4，但不隐式全量转码

方案：优先选择 H.264/AAC 兼容格式并正确 merge/remux；最终必须由 ffprobe 证明 `video.mp4` 是真实 MP4。无法无损归一化时返回 `NORMALIZE_ERROR`，原始文件只留在 staging 供诊断。

执行决策树：

1. yt-dlp 格式策略优先请求 H.264 视频 + AAC/M4A 音频，并把原始下载写入 staging。
2. ffprobe 读取真实 container、vcodec、acodec 和 streams；文件名不参与格式判断。
3. 若已是 MP4 且 codec 为 H.264 + AAC，则规范化文件名后继续验证。
4. 若 container 不是 MP4、但 streams 为 H.264 + AAC，则只做无损 remux，再次 ffprobe。
5. 若为 VP9、AV1、Opus 或其他不满足默认兼容策略的组合，则退出 `40`；默认不自动全量转码。
6. remux 后仍不满足真实 MP4 + H.264 + AAC，则退出 `40`，保留 failure manifest 和原始 staging。

原因：`SKILL.md:53-57`、`SKILL.md:139-150` 和 README 已将 `video.mp4` 作为公共接口；直接改成 `video.*` 或强迫下游读 manifest 会扩大本次变更范围。

后续扩展：如需要“最高画质原容器”或自动转码，应增加显式模式，而不是偷偷改变默认质量/耗时。

### D3. Manifest 是发布真相，目录存在不是成功

只有 `manifest.status=ready` 且运行时复验通过的 final 才是可消费结果。最小 schema 必须包含：

- `schema_version`、`status`、`error`
- `source.url_redacted`、`source.url_sha256`、`extractor`、`id`
- `source_ext`、`container`、`vcodec`、`acodec`、`normalized`
- yt-dlp/ffmpeg/ffprobe/JS runtime 版本
- video/audio/info 相对路径、大小、格式、codec、duration
- optional assets、warnings、`published_at`
- format policy、`generation`、`publish_mode=initial|force`，以及按 publish mode 约束的 `replaces_fingerprint`

final 中的 manifest 只能是 `status=ready` 且 `error=null`；失败状态写入 staging 的 failure manifest，不能发布到 final。`publish_mode=initial` 时禁止出现 `replaces_fingerprint`；`publish_mode=force` 时该对象条件必填，并且必须逐字段等于 journal 中的 expected-final fingerprint：`device`、`inode`、`manifest_state=ready|invalid|missing`、`manifest_sha256`。旧 manifest 文件存在时 SHA256 必须是其原始字节 hash；只有 `manifest_state=missing` 时才允许为 null。

final 中的 `manifest.json` 与 `fetch.log` 只描述“生成该 artifact 的那次运行”，发布后不可变。默认复用只复验并输出已有路径，不得把 `reused=true` 回写 final；本次是否复用仅写 stderr。`publish_mode=force` 及其 `replaces_fingerprint` 必须记录在新 artifact 的 manifest 中，因为它们属于该 artifact 的生产事实，而不是后续调用遥测。

### D4. yt-dlp 默认隔离宿主配置和插件

- 所有调用显式带 `--ignore-config`。
- 默认设置 `YTDLP_NO_PLUGINS=1`。
- cookie 只通过项目已有显式环境变量进入。
- 重试策略固定为 `--retries 10`、`--fragment-retries 10`、`--extractor-retries 3`、`--file-access-retries 3`、`--socket-timeout 30`；http/fragment/extractor 使用 `exp=1:8` 退避，file_access 使用 `linear=1:3:1`。所有数值都进入 argv contract 测试，禁止 `infinite`。
- Python 外层 timeout 固定为：resolve 120 秒、单次 ffprobe 30 秒、download 和 ffmpeg 各 14400 秒。timeout 统一映射到所属阶段的非零退出码并保留 staging；本里程碑不增加隐藏的无限等待或未经文档化的环境覆盖。
- 显式传 `--no-playlist` 和 `--match-filters !is_live`；另外解析 metadata 时若 `_type=playlist` 或存在多 entries，必须在下载前退出 `20/RESOLVE_ERROR/not_single_video`，因为 `--no-playlist` 本身不能证明输入不是播放列表。
- 使用 yt-dlp 的 `after_move:filepath` 获取后处理后的真实路径，不再用 `ls | head` 猜测。

官方依据：yt-dlp 会加载 portable/home/user/system 配置，并允许插件覆盖 built-in extractor；官方也提供 `--ignore-config`、`after_move:filepath`、重试和 `.part`/continue 机制。实现时以当前官方 README 复核参数：<https://github.com/yt-dlp/yt-dlp/blob/master/README.md>。

### D5. 平台承诺服从证据

- YouTube 在当前 yt-dlp 中需要外部 JS runtime 才有完整支持；实现时按官方 EJS 指南复核：<https://github.com/yt-dlp/yt-dlp/wiki/EJS>。
- yt-dlp 官方 release 对 Linux glibc/musl、x86_64/aarch64 提供不同资产；实现时按官方 release matrix 复核：<https://github.com/yt-dlp/yt-dlp/blob/master/README.md#release-files>。
- 当前官方 supported-sites 列表没有 Kuaishou/Kwai 一等 extractor；是否可用只能由 Generic 路径真实冒烟决定：<https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md>。

这些外部事实具有时效性，每次进入相关实施阶段前必须重新核对官方文档。

### D6. 首个里程碑冻结宿主与 JS runtime 矩阵

- v1 目标宿主只包括：macOS 10.15+ 的 x86_64/arm64，以及 Linux glibc 2.17+ 的 x86_64/aarch64；WSL 仅按其实际 Linux glibc/arch 落入同一矩阵。
- musl、Linux armv7l、原生 Windows 和其他组合在 v1 明确为 unsupported，bootstrap 必须在下载任何二进制前退出 `10/DEPENDENCY_ERROR/unsupported_host`。musl 只有在 yt-dlp、ffmpeg、ffprobe、Deno 四项资产和 clean-bootstrap 都有校验后才能另立计划升级支持等级。
- 新增公开配置 `VA_YTDLP_JS_RUNTIME=auto|deno|node|none`，默认 `auto`。`auto` 只接受 Deno `>=2.3.0`：先找受控 `VA_HOME/bin/deno`，再找合格系统 Deno，仍缺失则 bootstrap 官方 Deno；不会暗中启用系统 Node。
- `deno` 与 `node` 均显式传 `--no-js-runtimes` 后再传唯一的 `--js-runtimes <runtime>:<absolute-path>`。`node` 只有用户显式设置 `VA_YTDLP_JS_RUNTIME=node` 且 Node `>=22.0.0` 时有效；项目不 bootstrap Node。`none` 禁用 JS runtime，通用下载检查可以通过，但 YouTube capability 必须明确失败。
- 非法枚举值、版本过低或显式选择的 runtime 不存在都退出 `10`，不得静默回退到另一 runtime。实施当日若官方最低版本变化，以提高 contract 最低版本并同步测试/文档的显式改动处理，不得只改实现。

## 5. 可测试验收标准

以下条目全部为下载地基完成条件：

1. fake yt-dlp 在解析阶段失败：退出 `20`，final 不存在，stdout 为空。
2. fake yt-dlp 解析成功但下载返回 `42`：退出 `30`，不打印 `done`/目录，已有 final 完全不变。
3. fake yt-dlp 只生成 WebM：不能通过改名得到成功；只有真实 remux 并经 ffprobe 验证后才能退出 `0`，否则退出 `40`。
4. ffmpeg 抽音失败：退出 `50`，不发布 final。
5. info 文件缺失或 JSON 损坏：退出 `50`，不发布 final。
6. 视频没有视频流、文件截断或 ffprobe 无法解析：退出 `50`。
7. 有音轨的视频成功后，audio.wav 被验证为 PCM WAV、16 kHz、单声道，且 `abs(audio_duration - video_duration) <= min(5.0, max(1.0, video_duration * 0.01))` 秒；刚好等于该阈值通过，等于“阈值 + 0.01 秒”失败。
8. 无音轨视频得到明确 `MEDIA_ERROR/no_audio`，不伪装为 pipeline-ready。
9. final 已存在且 manifest/产物有效：默认重跑不调用下载器，目录 inode/mtime 不变化，退出 `0` 并输出同一路径。
10. final 已存在但 manifest 或产物无效：默认重跑非零；只有 `--force` 才构建新结果。
11. `--force` 新下载或验证失败：旧 final 内容和 manifest 完全不变。
12. `--force` 成功：新 final 为完整结果，不残留 backup；两个 rename 边界的瞬时磁盘状态允许 final 暂时缺失，但 next-run recovery 后必须收敛为调用前 final 或完整新 final，且永不把混合目录当作 READY。
13. 两个相同 URL 并发执行：第一个持锁期间，第二个不等待并退出 `60/artifact_locked`；final 不出现混合产物。锁回收分别覆盖 PID 存活、PID 消失但未满 1800 秒、同 host 且 PID 消失并已满 1800 秒、不同 host 四种情况。
14. 宿主 yt-dlp config 含改变输出目录/格式的选项时，项目结果不受影响。
15. 宿主安装覆盖 built-in 的 yt-dlp plugin 时，默认执行不加载该 plugin。
16. cookie 文件路径和 `cookies-from-browser` 参数能够透传，但 stdout、fetch.log、manifest 中没有 cookie 内容。
17. URL 不是 `http://`/`https://`、URL 是播放列表或直播时，得到明确非零退出和非目标提示。
18. macOS 10.15+ x86_64/arm64 与 Linux glibc 2.17+ x86_64/aarch64 映射到正确 yt-dlp/Deno/ffmpeg/ffprobe 资产；musl 和其他组合在下载二进制前退出 `10/unsupported_host`。
19. YouTube runtime 能力由 `check.sh` 明确报告；`VA_YTDLP_JS_RUNTIME` 的 `auto|deno|node|none` 四种值和非法值都有表驱动测试，Node 只有显式选择且版本 `>=22.0.0` 时才启用。
20. `python -m pytest -q`、所有 shell `bash -n`、`git diff --check` 全部通过。
21. 每个标为 `supported` 的平台都满足“两条公开 fixture × 各连续 3 次 READY”；标为 `experimental` 的平台至少有一次 READY，并且所有失败都有可操作诊断。
22. README、README.en、SKILL 和 platforms 文档的支持等级与本次冒烟报告一致。
23. 第 3.5 节 journal 预检查和恢复表每一行都有目录 fixture，包括 initial rename 后 journal 未删、两个 force rename 边界和 backup cleanup 前崩溃；恢复函数连续运行两次时第二次无目录变化，所有 FOREIGN/AMBIGUOUS 情况退出 `60` 且不移动或删除冲突目录。
24. final 的复用路径不改写 `manifest.json`、`fetch.log` 或 final 目录 inode/mtime；新 artifact 的 `publish_mode` 只可能是 `initial` 或 `force`，不存在 `reuse` manifest。initial manifest 禁止 `replaces_fingerprint`；force manifest 必须包含与 journal expected-final 逐字段相同的 `{device,inode,manifest_state,manifest_sha256}`，并断言只有 manifest_state=missing 时 SHA256 为 null。

## 6. 分阶段实施

### Phase 0：冻结契约并先写失败测试

目标：先证明当前缺陷，并锁定新行为；此阶段不重写下载实现。

计划文件：

- 新建 `docs/superpowers/specs/2026-07-24-video-download-contract.md`
- 新建 `tests/test_fetch_contract.py`
- 视复用需要新建 `tests/support/fake_tools.py`
- 临时校准 `README.md`、`README.en.md`、`SKILL.md`、`references/platforms.md` 的平台状态

任务：

1. 把本计划第 3 节转换成仓库内正式 contract spec。
2. 建立临时 PATH fake yt-dlp/ffmpeg/ffprobe 测试工具，不访问网络。
3. 先覆盖四个已证实缺陷：下载非零退出、WebM 冒充 MP4、ffmpeg 失败、旧 final 污染；再补解析失败、坏 JSON、无视频流、stdout 成功协议、cookie 脱敏、锁和恢复目录 fixture。
4. 把目标测试按责任分组：`phase1_capability` 对应验收 18-19；`phase2_core` 对应 1-8、14-17；`phase3_publish` 对应 9-13、23-24。验收 20 由 `phase4_ci` 验证清单负责，不用 xfail 表示；验收 21 是 `phase5_smoke` 外网门禁，验收 22 是 `phase6_docs` 文档一致性门禁，两者都不进入离线 pytest xfail 清单。
5. Phase 0 允许尚未实现的离线目标测试使用 strict xfail，reason 格式固定为 `owned by <group> (A<acceptance-id>)`，例如 `owned by phase3_publish (A12)`；xfail 清单必须记录 `pytest test id / group marker / acceptance id / removal phase` 四列。XPASS 必须使测试失败。进入责任阶段时先移除该组 xfail，再以全绿作为门禁。禁止无 owner 的 xfail、普通 skip 或把原始红测作为阶段终点提交。
6. 在真实 smoke 完成前，把 YouTube、Douyin、Kuaishou 等尚未通过新门禁的状态统一标为 provisional/experimental，并说明“等待下载地基验证”；不得在实施期间继续沿用无证据的“稳定/一等支持”表述。

阶段门禁：

- 失败用例能稳定复现现状，并能区分“当前错误行为”和“目标行为”；每个 strict xfail 都能由清单唯一映射到 group、验收号和移除阶段。
- 测试完全离线、单次总耗时目标小于 5 秒。
- 未修改 ASR 实现、摘要/改写步骤或 `SKILL.md` 的下游 Agent 工作流；允许且只允许修改 `SKILL.md` 的下载契约、安装前置条件和平台支持等级，以避免实施期间继续公开错误承诺。

### Phase 1：补齐下载依赖能力矩阵

依赖：Phase 0 已完成。

计划修改：

- `scripts/bootstrap.sh`
- `scripts/bootstrap_ffmpeg.sh`
- `scripts/check.sh`
- `references/install.md`
- 下载依赖相关契约测试

任务：

1. 按 D6 固定并测试 v1 矩阵：macOS 10.15+ x86_64/arm64；Linux glibc 2.17+ x86_64/aarch64；musl 与其他组合明确 unsupported 并在网络请求前早失败。WSL 按实际 Linux glibc/arch 处理。
2. yt-dlp 资产解析同时考虑 OS、arch、libc，继续校验官方 SHA256。
3. ffmpeg 能力升级为 ffmpeg + ffprobe 成对就位；系统路径和静态 fallback 都必须验证二者可运行。
4. 实现 `VA_YTDLP_JS_RUNTIME=auto|deno|node|none`：默认 auto 只选择/安装 Deno `>=2.3.0`；Node `>=22.0.0` 只在显式选择时启用；非法值和低版本均失败。所有 runtime 都按 D6 显式传绝对路径，最低版本在实施当日再次对照官方 EJS 文档。
5. `check.sh` 分开报告“通用下载 ready”和“YouTube challenge runtime ready”，不能只显示模糊总绿灯。
6. 记录实际工具版本，fetch 阶段写入 manifest；fetch 期间禁止隐式自更新。

阶段门禁：

- 表驱动测试证明每个支持组合选择正确资产，musl/未知组合不会发出二进制网络请求；`phase1_capability` 组不再有 xfail。
- 系统已有 ffmpeg/ffprobe 与完全缺失两条 bootstrap 路径均有验证。
- 当前 macOS 开发机能明确报告系统 Node 版本；fake version 表证明只有显式 `VA_YTDLP_JS_RUNTIME=node` 且版本合格时才生成 Node runtime 参数。
- 干净 Linux glibc x86_64 环境完成 bootstrap smoke。

### Phase 2：建立显式状态机与完整核心验证

依赖：Phase 1 能提供 yt-dlp、ffmpeg、ffprobe 和 runtime capability。

计划修改：

- 新建 `scripts/fetch.py`
- 将 `scripts/fetch.sh` 缩减为兼容入口
- 视纯函数规模新建 `scripts/lib/fetch_utils.py`
- 新建 `tests/test_fetch_utils.py`
- 扩展 `tests/test_fetch_contract.py`
- 增加小型合成媒体 fixture

任务：

1. Python CLI 解析现有参数和 `--force`，校验 URL scheme、依赖和输出根目录。
2. 所有外部命令使用 argv list + `subprocess`，不得经 `shell=True` 拼接 URL/cookie 参数。
3. 建立明确阶段：resolve、download、normalize、validate、publish；每一阶段映射到固定退出码。
4. Phase 2 即实现 D4 的固定 argv：config/plugin 隔离、单视频/非直播判定、精确 retry/timeout、runtime 选择和显式 cookie 入口；不得把参数数值留给 Phase 4。
5. 每次构建先进入唯一 generation staging；使用 yt-dlp `after_move:filepath` 获取真实媒体路径，不再通过文件名猜测产物。Phase 2 只允许 initial publish；遇到任何已有 final 时先退出 `60`，复用/force 由 Phase 3 接管。
6. 实现并单测 ffprobe JSON 解析、真实 MP4/H.264/AAC 决策树、必要 remux、视频流/音轨/duration 检查、info.json identity 校验、PCM WAV 生成与第 3.2 节时长容差。
7. 在 staging 最后写入 immutable `manifest.json.tmp`，fsync/replace 为 `manifest.json`；只有核心验证全部通过才允许 initial `stage -> final`。
8. 捕获完整脱敏诊断到 producing run 的 fetch.log，同时向 stderr 输出简洁错误；去掉 `--no-warnings` 式关键诊断抑制。成功 stdout 只输出 final，失败 stdout 为空。
9. thumbnail/subtitle 保持可选，warnings 结构化进入 manifest；无音轨按已冻结契约返回 `50/no_audio`。

阶段门禁：

- 验收 1-8、14-17 全部通过，`phase2_core` 组不再有 xfail；`phase3_publish` 仍可保留 Phase 0 登记的 strict xfail。
- fake 工具记录表明 argv、cookie、runtime、格式、retry 和 timeout 均与 D4/D6 完全一致。
- 合成短 MP4+音频 fixture 在真实 ffmpeg/ffprobe 下通过；WebM、截断文件、坏 JSON、无视频流、无音轨均得到固定退出码。
- manifest schema 有纯函数单测；所有路径为 final 内相对路径且不泄露凭据。
- 任一 subprocess 非零都不会落入后续成功路径。

### Phase 3：实现 staging、锁、复用与可回滚发布

依赖：Phase 2 状态机稳定。

计划修改：

- `scripts/fetch.py`
- `scripts/lib/fetch_utils.py`（如 Phase 2 已创建）
- `tests/test_fetch_contract.py`

任务：

1. resolve 出 `<extractor>-<id>` 后，以原子 mkdir 获取第 3.4 节固定路径的 per-artifact 写锁；第二写者立即失败，不实现等待分支。
2. 延续 Phase 2 的 UUID generation staging，保持 yt-dlp `.part` 可恢复；每个 stage 必须有 source identity 和 transaction metadata，多个候选一律进入冲突分支。
3. 默认复用前必须读取 manifest 并重新验证必需产物。
4. 默认复用不得修改 final 中的 manifest、fetch.log 或任何 mtime；无 `--force` 遇到 invalid final 时失败并保留现场。
5. 普通 `--force` 在没有 active journal 时创建新的 generation staging；只有恢复表命中“唯一 owned stage 且 provenance/fingerprint 指向当前 final”时才允许续用旧 stage。新结果 ready 前不改旧 final。
6. force 替换严格执行“持久化 transaction -> final rename 到唯一 backup -> fsync parent -> stage rename 到 final -> fsync parent -> 复验 final -> 清理或隔离 backup”，并在两个 rename 前后提供故障注入点。
7. stale lock 严格实现 same-host + dead-PID + age>=1800 秒三条件；四种锁验收场景的决策和日志必须固定。
8. 每次获取锁后先执行第 3.5 节恢复表；每行都用目录 fixture 覆盖，恢复函数连续执行两次时第二次无变化。
9. 成功 transaction 只删除可证明属于该 transaction 的 ready backup；owned-invalid 原状态移入 `.recovery/`，FOREIGN/AMBIGUOUS 永不自动移动或删除。

阶段门禁：

- 验收 9-13、23-24 全部自动化通过，`phase3_publish` 组不再有 xfail；所有本地 contract test 已无 xfail/skip。
- 在 download、normalize、validate、initial publish、两个 force rename 边界和 backup cleanup 前分别终止进程；允许第一、第二次 force rename 之间出现 `final` 暂缺但 backup 可恢复，next-run recovery 后 final 必须收敛为调用前版本或完整新版本，且从不发布混合目录。
- 默认复用路径不访问网络。

### Phase 4：本地集成与默认 CI 收口

依赖：Phase 3 的事务边界和恢复表完成。

计划修改：

- `scripts/fetch.py`
- `scripts/lib/fetch_utils.py`
- `tests/test_fetch_utils.py`
- `tests/test_fetch_contract.py`
- 小型本地媒体/目录 fixture
- 新建 `.github/workflows/ci.yml`

任务：

1. 确认 Phase 0 留下的所有本地 xfail/skip 均已在责任阶段删除；contract、validator、capability 和 publish/recovery 测试全部正常执行，发现任何残留即阻塞本阶段。
2. 用真实 ffmpeg/ffprobe 覆盖：H.264/AAC MP4 直通、H.264/AAC 非 MP4 无损 remux、VP9/Opus 拒绝、截断文件、无视频流、无音轨、audio duration 容差两侧边界。
3. 以独立子进程终止模拟 download/normalize/validate、两个 rename 边界和 backup cleanup 前崩溃；next-run 结果逐行匹配第 3.5 节恢复表。
4. 默认 CI 分 macOS 与 Linux glibc x86_64 运行 offline contract、纯函数单测、真实媒体 local integration、shell syntax 和 diff 检查；aarch64 capability 由表驱动测试覆盖，clean bootstrap 仍在 release gate 验证真实资产。
5. 测试失败输出必须包含 fake argv、退出码、目录树、manifest/transaction 摘要和 ffprobe 摘要，但继续执行 cookie/URL 脱敏断言。

阶段门禁：

- 验收 1-20、23-24 由“本地测试 + macOS/Linux 默认 CI + capability 表驱动证据”组合证明；验收 18 的 aarch64 资产选择在此阶段只要求表驱动证明，四个目标 host 的真实 clean-bootstrap 留在 Phase 5/6 release gate。测试收集结果中没有 xfail、xpass 或 skip。
- macOS 与 Linux 默认 CI 全绿；offline contract 单次总耗时小于 10 秒，每个 OS 的 local integration 总耗时小于 60 秒。
- 每个恢复表 fixture 连续恢复两次，第二次目录树、inode 和 manifest hash 均不变化。

### Phase 5：真实平台冒烟

依赖：Phase 4 本地闭环稳定。

计划修改：

- 新建 `tests/smoke.sh`
- 新建平台 URL 清单/示例配置（不含私密 cookie）
- 更新 release 验证说明

测试分层：

1. Offline contract：fake 工具，默认 CI，覆盖所有失败和事务语义。
2. Local integration：合成短视频 + 真实 ffmpeg/ffprobe，默认 CI。
3. Platform smoke：YouTube、Bilibili、Twitter/X、Douyin、Kuaishou 分平台独立运行；手动/nightly/pre-release，不进入每次 PR 默认 CI。
4. Clean bootstrap：系统已有工具与完全缺失两条路径；定期或 release gate。

每个平台 smoke 必须记录：

- 平台、fixture ID/URL hash
- yt-dlp、ffmpeg、JS runtime 版本
- 成功产物验证摘要
- 失败阶段及 `link_rot / auth_or_antibot / upstream_extractor / project_regression` 分类

对外支持等级统一按以下证据判定：

- `supported`：至少两条不同的公开短视频 fixture，各连续 3 次得到 `READY`，并且不依赖未声明的本机配置；需要 YouTube runtime 等前置能力时，bootstrap/check 已自动满足并明确记录。
- `experimental`：至少一次得到 `READY`，但存在已知间歇失败、公共内容必须依赖 cookie、只命中 Generic extractor，或尚未达到 `supported` 的重复性要求。
- `unsupported`：当前 release 没有任何可验证的 `READY` 路径，或只能依赖不纳入项目的第三方解析服务/自定义私有插件。

任何平台等级只对记录的 yt-dlp 版本、测试日期和环境成立；后续 upstream 变化由新 smoke 报告更新，不把历史一次成功永久当作支持证明。

平台门禁：

- YouTube 必须在已启用受支持 JS runtime 的环境通过。
- Bilibili、Twitter/X 至少各有公开 URL 成功路径；需要 cookie 的路径单独标记，不与公开路径混淆。
- Douyin 必须覆盖短链与 fresh-cookie 提示。
- Kuaishou 只有真实路径通过时才能标为“可用”；失败则降级为“实验性/未承诺”，另立 adapter 调研计划。
- fixture 腐烂不得直接判为代码回归；先替换 fixture 并复测。

### Phase 6：文档校准与发布门禁

依赖：Phase 5 产生真实证据。

计划修改：

- `README.md`
- `README.en.md`
- `SKILL.md`
- `references/platforms.md`
- `references/install.md`
- `docs/superpowers/specs/2026-07-23-video-anything-design.md`
- `docs/superpowers/plans/2026-07-23-video-anything.md`

任务：

1. 文档只承诺已经通过对应 smoke/clean-bootstrap 门禁的能力。
2. 更新输出目录，加入 manifest、严格成功语义、reuse/force、staging 恢复说明。
3. 说明 MP4 为兼容优先策略，默认不做昂贵全量转码。
4. 修正 YouTube runtime、Linux 支持矩阵、Douyin cookie 现状和 Kuaishou support tier。
5. 更新旧设计/计划中的完成状态，避免历史计划继续显示全部未完成。
6. 保持合规边界：只处理公开内容，不绕过 DRM/付费墙。

最终发布门禁：

- 全部 offline/local 测试在 macOS 与 Linux CI 通过。
- 支持矩阵中的 clean bootstrap 路径有可追溯报告。
- 所有对外平台状态与最近一次 smoke 报告一致。
- `bash -n scripts/*.sh`、`python -m pytest -q`、`git diff --check` 通过。
- 真实失败场景不会返回 `0`、不会打印成功路径、不会改变旧 final。

## 7. 风险与缓解

| 风险 | 缓解 |
|---|---|
| 平台反爬与 extractor 高频变化 | 外网 smoke 与离线 contract 分层；记录精确工具版本；平台失败不自动归因于项目代码 |
| 兼容优先 MP4 可能损失最高画质 | 默认明确为兼容策略；不隐式转码；后续用显式 native/high-quality 模式扩展 |
| `--force` 目录替换在各 OS 上并非真正原子交换 | 同文件系统 staging + 单写者锁 + backup/rollback；文档不夸大并发读保证 |
| stale lock 判断错误 | 只在同 host、PID 不存在、年龄至少 1800 秒三条件同时满足时回收；其他情况退出 `60` |
| staging 和旧 backup 占用磁盘 | 本里程碑不自动按 TTL 清理失败现场；成功 transaction 只清理 fingerprint 匹配的 ready backup，其余报告精确路径并保留 |
| bootstrap 第三方二进制供应链 | 官方 release、校验和、临时文件、校验后原子替换；版本和来源写入日志 |
| cookie/URL 敏感信息泄漏 | argv list、日志脱敏、manifest 只存 hash；测试断言日志不存在测试 secret |
| 外网 fixture 腐烂导致假红 | 分类为 link_rot；每个平台独立运行并允许替换 fixture 后复测 |
| Python orchestrator 变更范围较大 | 保留 shell CLI；先锁定契约；分阶段提交；不同时修改 ASR/Agent 层 |

## 8. 验证命令与证据

每个实现阶段至少运行：

```bash
python -m pytest -q
bash -n scripts/bootstrap.sh
bash -n scripts/bootstrap_ffmpeg.sh
bash -n scripts/check.sh
bash -n scripts/fetch.sh
git diff --check
git status --short
```

Phase 5/6 额外运行：

```bash
bash tests/smoke.sh --platform youtube
bash tests/smoke.sh --platform bilibili
bash tests/smoke.sh --platform twitter
bash tests/smoke.sh --platform douyin
bash tests/smoke.sh --platform kuaishou
```

clean bootstrap 必须使用全新的、明确的 `VA_HOME`，记录 OS/arch/libc 和工具版本。执行时用 `mktemp -d` 创建受控目录，禁止把清理目标写成 `$HOME`、`~` 或 workspace root。

## 9. 建议提交边界

每个阶段独立提交并遵守 Lore commit protocol：

1. `Make download failures observable before changing pipeline behavior`
2. `Make download capabilities explicit across supported hosts`
3. `Publish only artifacts that pass the complete media contract`
4. `Make repeated downloads safe and recoverable`
5. `Prove media and recovery contracts in default CI`
6. `Make platform support claims evidence-backed`

每次提交至少包含 `Confidence`、`Scope-risk`、`Tested` 和 `Not-tested` trailers；任何未执行的外网/干净环境验证必须如实写入 `Not-tested`。

## 10. 后续执行顺序

后续每次工作默认从最早未完成阶段开始：

1. Phase 0：契约 + 红测
2. Phase 1：依赖能力矩阵
3. Phase 2：显式状态机 + 完整核心验证
4. Phase 3：事务与幂等
5. Phase 4：本地集成 + 默认 CI
6. Phase 5：CI + 平台 smoke
7. Phase 6：文档与发布门禁

不得为了尽快跑真实平台而跳过 Phase 0-4；否则只能证明某个链接“这次碰巧下成功”，不能证明下载地基可靠。

## 11. 2026-07-24 评审修订记录

- 撤销旧 `APPROVED` 状态，等待本版本独立复审。
- 把完整媒体、info 和 manifest 验证前移到 Phase 2；Phase 3 只在验证器已经存在后实现复用、锁和发布事务，Phase 4 改为真实工具集成与默认 CI 收口。
- 将 Phase 0 目标测试按 Phase 1/2/3 owner 分组，使用有 owner 的 strict xfail 维持阶段绿线，并规定各责任阶段移除时间。
- 增加 lock/transaction/stage/backup/recovery 固定路径、立即失败的第二写者策略、1800 秒 stale-lock 三条件及完整恢复决策表。
- 冻结 v1 宿主矩阵、musl 非支持结论、`VA_YTDLP_JS_RUNTIME` 枚举、重试次数、退避、各 subprocess timeout 和音频时长容差。
- 将不可变 artifact manifest 与后续 reuse 调用分离；复用不再改写 final，manifest 只记录 artifact 的 initial/force 生产事实。
- 明确 Phase 0 对 `SKILL.md` 的允许修改边界：只校准下载契约、安装前置和平台等级，不修改下游 Agent 工作流。
- 最终独立 Critic 复审结论：`APPROVED`；恢复状态机与测试阶段专项复核均无剩余阻塞项。
