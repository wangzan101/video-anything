# video-anything — 设计文档 (Spec)

- **日期**: 2026-07-23
- **状态**: 已批准设计 + 已并入 code-review(R1–R10),待写实现计划
- **一句话**: 给一个视频链接,拿到关于它的一切(无水印视频 / 音频 / 文案 / 字幕 / 封面 / 元数据)+ agent 做 4 种 AI 加工。跨工具、零 key(默认)、可离线、装上即用。

> **修订记录**: 2026-07-23 并入 Codex 式评审 R1–R10 —— bootstrap 健壮性(兼容 Python / ffmpeg 多源 / 二进制校验)、云 ASR 显式 opt-in、字幕仅信人工字幕、达标线软化、Windows 边界、分阶段发布。

---

## 1. 背景与目标

`yt-dlp` 只下载,不转文案、不理解内容;付费「文案提取」站做到了但闭源收费只给文本。`video-anything` 把这条链**做成开放标准的 Agent Skill(SKILL.md)**闭环:下载 → 本地 ASR → agent 自己做总结/改写/拆分镜/选题。总结层不需要外部模型 key —— 读到 skill 的 agent 本身就是 LLM。

**受众**: 自媒体创作者 + AI/dev,用于二创、竞品拆解、知识库、选题。作者靠它引流、攒 GitHub star。

**为什么现在做**: SKILL.md 已是跨 40+ agent 的开放标准;该闭环在开源/skill 形态下无人做成(`video-to-subtitle-summary-skill` 135★ 只做字幕+摘要、桌面版 `VideoHub` 非 skill、`douyin-mcp` 单平台已归档)。窗口在收窄,需尽快。

## 2. 成功标准 (v1 达标线,可验证)

1. 5 平台(YouTube / B站 / Twitter / 抖音 / 快手)**在 spec 编写时、按 platforms.md 的 cookie 步骤**,各给一个公开链接能产出 `video.mp4 + audio.wav + info.json`。**反爬导致的间歇失效不算不达标,但失效时必须给出可操作的降级提示(见 §9)——「优雅失败」本身是验收点。**(R4)
2. `transcribe.py` 能产出 `transcript.md`(默认本地引擎;引擎可用性由 bootstrap 探测保证,见 §4/§8)。
3. 4 个 playbook 各能产出对应 `summary.md`,且每个 playbook 有一份 references/ 黄金样例锚定质量。(R11)
4. **首次使用零手动安装**:`bootstrap` 自动就位依赖;用户不敲任何 `brew/pip install`。
5. README 照着走 <5 分钟可用;至少在 2 个 agent(Claude Code + 另一个)里能调用。
6. 纯逻辑单元有 pytest 覆盖并通过;每平台有一条冒烟测试;bootstrap 在干净环境(容器/VM)验证过。
7. **不承诺「秒级」**:默认本地路径延迟取决于 Whisper 模型与视频时长;首发话术只在「有字幕源 / tiny / 云」路径下才提速度。(R6)

## 3. 架构 (方案 A:SKILL.md + 脚本)

```
video-anything/
├── SKILL.md                 路由 + 4 个 AI playbook 指令 + 黄金样例引用
├── scripts/
│   ├── bootstrap.sh         首次自动就位依赖(含 OS×arch 探测 + 校验)
│   ├── check.sh             依赖自检(缺则触发 bootstrap)
│   ├── fetch.sh             yt-dlp 下载 → 素材;ffmpeg 抽音频
│   ├── transcribe.py        本地/云 ASR 双引擎 → transcript
│   └── lib/                 可单测的纯函数(vtt 解析、时间戳、路径、平台id)
│       └── asr_utils.py
├── references/
│   ├── install.md           手动安装兜底说明
│   ├── platforms.md         各平台无水印/cookie/反爬/视频号二期
│   └── examples/            4 个 playbook 的黄金样例
└── tests/
    ├── test_asr_utils.py    pytest 纯逻辑
    └── smoke.sh             各平台真链接冒烟(手动/带 flag)
```

选方案 A 的理由:纯文件最跨工具、透明可 fork(利于 star)、顺行业风向、零服务器最轻。放弃 MCP(重、被取代)与单一 CLI 黑盒(难 fork)。

## 4. 依赖策略:自动 bootstrap(核心 UX,也是头号风险区)

**原则**: 用户不手动安装任何东西。skill 首次调用时自我就位到私有目录 `~/.video-anything/`,不污染系统。**bootstrap 是本项目最脆、最需硬化的组件**(R2),按下列硬需求实现:

- **yt-dlp**: 从**官方 GitHub release** 下对应平台单文件二进制(`yt-dlp_macos` / `yt-dlp_linux` / `yt-dlp.exe`,~30MB),**校验官方 SHA256SUMS**(R3)→ `~/.video-anything/bin/`。保留 `yt-dlp -U` 自更新。
- **ffmpeg**(R2): **优先用系统已装 ffmpeg**(多数环境已有,如本机 8.1)→ symlink 进私有 bin;系统没有才按 OS×arch 从第三方源取(mac→evermeet、linux→johnvansickle)。**跟各源的「最新稳定」通道 + 尽力校验**——硬编码 ffmpeg 版本号会像 yt-dlp 占位一样过期 404,且 mac evermeet 无官方 SHA256,故 mac 用「字节数 + 运行时冒烟」尽力校验、linux 用其官方 md5;取不到/校验失败则明确报错提示手动装。ffmpeg 就位单列为高风险项,冒烟必测(回退分支需无-ffmpeg 干净环境验,见 §10)。
- **ASR 引擎**(R1): **不假设 `pip install faster-whisper` 一定成功**(如本机 Python 3.14,ctranslate2 可能无 wheel)。就位顺序:
  1. 探测系统已有 `whisper` / `whisper-cli`(本机 `/opt/homebrew/bin/whisper` 即可用)→ 直接用;
  2. 否则用**钉定的兼容 Python(3.11/3.12)**建私有 venv 装 faster-whisper;
  3. 否则下 whisper.cpp 二进制;
  4. 都不行 → 明确报错并给手动指引。
  引擎可用性探测是硬需求,`check.sh` 必须能报告「本地 ASR 是否真的可用」。
- 所有脚本优先私有 `bin`/`venv`,回退系统版本。
- **诚实边界**: Whisper 模型权重(small ~460MB / tiny ~75MB)首次转录时下载一次,物理上绕不过;用「人工字幕优先 + tiny + 云引擎」缓解。
- macOS:用 `curl` 下载(不带 quarantine 属性),必要时 `xattr -d com.apple.quarantine` + ad-hoc 签名兜底。

## 5. 数据流

```
URL
 → 解析(平台 extractor + id)           [fetch.sh 前置 --print]
 → yt-dlp 下载(视频 + 字幕 + 封面 + info.json)
 → ffmpeg 抽 16k 单声道 audio.wav
 → 有【人工】字幕? ── 是 → 清洗 vtt 为纯文本(跳过 ASR)
                   └ 否/仅自动字幕 → transcribe.py 走 ASR   (R7)
 → transcript.md / .txt
 → agent 按选定 playbook 读 transcript + info → summary.md
```

**字幕优先只信人工字幕**(R7):平台自动生成字幕有行间重复、质量差,不据其跳过 ASR;仅当存在人工上传字幕时才优先复用。

输出目录:`video-out/<平台>-<id>/`。同 URL 重跑:默认复用已存在产物、`--force` 覆盖(避免磁盘无限增长,见 backlog R13)。

## 6. 组件与接口

| 组件 | 输入 | 输出 | 依赖 | 可单测 |
|---|---|---|---|---|
| `bootstrap.sh` | — | 私有 bin/venv 就位 + 校验 | 网络 | 否(干净环境冒烟) |
| `check.sh` | — | 依赖 ✅/❌ + 本地 ASR 是否可用,缺则调 bootstrap | — | 否 |
| `fetch.sh` | URL, out_root | `<平台>-<id>/` 目录 | yt-dlp, ffmpeg | 否(冒烟) |
| `transcribe.py` | 音频, --model, --lang, --engine | transcript.md/.txt | whisper(本地/云) | 部分(纯函数在 lib) |
| `lib/asr_utils.py` | vtt / 时间戳 / url | 结构化 | — | ✅ |
| SKILL.md playbook | transcript + info | summary.md | agent 自身 | 否(黄金样例人工验收) |

## 7. AI 加工层(4 个 playbook,写进 SKILL.md,各配黄金样例)

1. **提炼要点**: 3–7 条 bullet + 一句话主旨
2. **口播稿改写**: 按指定风格(小红书种草 / 知识拆解 / 播客口播)重写
3. **拆分镜**: 按时间戳切成 镜号 / 时间 / 画面 / 口播 表
4. **选题矩阵**: 基于主题衍生 5–10 个选题 + 标题

均为 SKILL.md 内 markdown 指令模板,agent 执行,无外部模型 key。每个配 `references/examples/` 一份黄金样例锚定质量(R11)。

## 8. ASR 双引擎(默认本地,云需显式 opt-in)

`transcribe.py` 引擎选择:
1. **仅当 `--engine cloud`(或配置显式开启)** → 云(Groq Whisper API)。**不因 `GROQ_API_KEY` 存在就隐式走云**——避免把用户视频静默外发(R5)。云路径需**音频大小检测 + 超限分片**(Groq ~25MB 限制)(R8)。
2. 否则本地引擎(按 §4 就位顺序:系统 whisper → faster-whisper venv → whisper.cpp)。
3. 都不可用 → 明确报错 + bootstrap 指引。

默认本地保「零 key」卖点;云为显式加速选项。叠加「人工字幕优先」减少 ASR 触发。

## 9. 错误处理与维护税对冲

- 分级不 silent fail:依赖缺失(check/bootstrap)、解析失败(提示 `yt-dlp -U` + cookie)、下载失败(平台专属提示指向 platforms.md)、ASR 引擎缺失(降级链)、无语音(明确告知)。
- **维护税对冲(全 5 平台一等公民的代价)**:失败自动建议/尝试升级 yt-dlp;cookie 逃生舱 `VA_COOKIES_FROM_BROWSER` / `VA_COOKIES`;每平台一条冒烟;错误信息可操作。**「优雅失败」是达标线之一(§2.1),不是可选项。**

## 10. 测试策略(TDD,诚实划分)

- **可单测(pytest,测试先行)**: `lib/asr_utils.py` —— 时间戳格式化、VTT→md 解析、平台+id 推导、输出路径命名、人工/自动字幕判别。fixture,不碰网络。
- **不可单测 → 冒烟**: `fetch.sh` / `bootstrap.sh` 网络+二进制编排。`tests/smoke.sh` 各平台短公开链接跑,手动/带 flag,不进默认 CI。**bootstrap 额外在干净容器/VM 验证**(它是头号风险)。
- fixture 链接会腐烂:冒烟失败先判「是链接失效还是代码 bug」(R12)。

## 11. 非目标 (YAGNI,v1 不做)

- ❌ 视频号(微信)—— Tier-3 二期,README 明标
- ❌ 批量 / 播放列表 —— 二期;脚本按单链接设计但不阻断后续加循环
- ❌ MCP 形态
- ❌ 云 ASR 作为默认(留显式 opt-in)
- ❌ **Windows 原生**:v1 要求 WSL / git-bash 跑 bash 脚本;原生 PowerShell 路径列二期(R9)
- ❌ DRM / 付费墙 / 大会员内容 —— 红线,永不做

## 12. 平台支持矩阵

| 平台 | v1 状态 | 备注 |
|---|---|---|
| YouTube | ✅ 一等 | yt-dlp 原生 |
| Bilibili | ✅ 一等 | 海外 IP 可能需 cookie(412) |
| Twitter/X | ✅ 一等 | yt-dlp 原生 |
| 抖音 | ✅ 一等 | 通常无水印;短链自动跟随 |
| 快手 | ✅ 一等 | 反爬,失效先升级;冒烟守护 |
| 视频号 | ⛔ 二期 | 封闭生态,需客户端抓包 |
| 其他 1800+ | ➕ | yt-dlp 支持即支持 |

## 13. 边界与合规

仅公开可访问内容。不绕过 DRM / 付费墙 / 大会员。定位:创作者 / 研究 / 个人存档。License: MIT。

## 14. 分阶段发布 (R10 — 保持全量 scope,但排序出早期可发里程碑)

维持「5 平台一等公民 + 4 playbook + 双引擎」的完整 scope,但实现计划按此排序,任一里程碑均可选择对外发布:

- **M1 · 核心闭环(可发)**: bootstrap(yt-dlp+ffmpeg+ASR 就位)+ fetch + transcribe + 1 个 playbook(提炼要点),打通 Tier-1(YouTube/B站/Twitter)。→ 已可发「下载+文案+总结」最小可用。
- **M2 · 自媒体主盘**: 抖音无水印 + 快手 + 口播改写 playbook + 人工字幕优先。→ 覆盖核心受众,首发主力。
- **M3 · 差异化补全**: 拆分镜 + 选题矩阵 playbook + 云引擎 opt-in + 黄金样例。
- **M4 · 硬化**: 各平台冒烟 + 干净 VM 验证 bootstrap + 维护税对冲完善 + 跨 agent 验证。

窗口紧就在 M2 后发,M3/M4 快速跟;不紧就 M4 后一次发全量。

## Backlog(次要,记录在案)

- R11 已并入 §2/§7(黄金样例)。
- R12 已并入 §10(fixture 腐烂提示)。
- R13 幂等/磁盘清理:§5 已定「默认复用 + --force 覆盖」;定期清理策略留二期。
