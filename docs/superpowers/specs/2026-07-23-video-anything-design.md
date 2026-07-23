# video-anything — 设计文档 (Spec)

- **日期**: 2026-07-23
- **状态**: 已批准设计,待写实现计划
- **一句话**: 给一个视频链接,拿到关于它的一切(无水印视频 / 音频 / 文案 / 字幕 / 封面 / 元数据)+ agent 做 4 种 AI 加工。跨工具、零 key(默认)、可离线、装上即用。

---

## 1. 背景与目标

`yt-dlp` 只下载,不转文案、不理解内容;付费「文案提取」站做到了但闭源收费只给文本。`video-anything` 把这条链**做成开放标准的 Agent Skill(SKILL.md)**闭环:下载 → 本地 ASR → agent 自己做总结/改写/拆分镜/选题。总结层不需要外部模型 key —— 读到 skill 的 agent 本身就是 LLM。

**受众**: 自媒体创作者 + AI/dev,用于二创、竞品拆解、知识库、选题。作者靠它引流、攒 GitHub star。

**为什么现在做**: SKILL.md 已是跨 40+ agent 的开放标准(一次写处处调用);该细分闭环在开源/skill 形态下无人做成(`video-to-subtitle-summary-skill` 135★ 只做字幕+摘要、桌面版 `VideoHub` 非 skill、`douyin-mcp` 单平台已归档)。窗口在收窄,需尽快。

## 2. 成功标准 (v1 达标线,可验证)

1. 5 个平台(YouTube / B站 / Twitter / 抖音 / 快手)各给一个公开链接,`fetch.sh` 都能产出 `video.mp4 + audio.wav + info.json`。
2. `transcribe.py` 能产出 `transcript.md`(默认本地引擎)。
3. 4 个 playbook(提炼要点 / 口播改写 / 拆分镜 / 选题矩阵)各能产出对应 `summary.md`。
4. **首次使用零手动安装**:`bootstrap` 自动就位依赖;用户不敲任何 `brew/pip install`。
5. README 照着走 <5 分钟可用;至少在 2 个 agent(Claude Code + 另一个)里能调用。
6. 纯逻辑单元有 pytest 覆盖并通过;每平台有一条冒烟测试。

## 3. 架构 (方案 A:SKILL.md + 脚本)

```
video-anything/
├── SKILL.md                 路由 + 4 个 AI playbook 指令
├── scripts/
│   ├── bootstrap.sh         首次自动就位依赖(yt-dlp/ffmpeg/whisper)
│   ├── check.sh             依赖自检(缺则触发 bootstrap)
│   ├── fetch.sh             yt-dlp 下载 → 素材;ffmpeg 抽音频
│   ├── transcribe.py        本地/云 ASR 双引擎 → transcript
│   └── lib/                 可单测的纯函数(vtt 解析、时间戳、路径命名)
│       └── asr_utils.py
├── references/
│   ├── install.md           手动安装兜底说明
│   └── platforms.md         各平台无水印/cookie/反爬/视频号二期
└── tests/
    ├── test_asr_utils.py    pytest 纯逻辑
    └── smoke.sh             各平台真链接冒烟(手动/带 flag)
```

选方案 A 的理由:纯文件最跨工具(40+ agent 直接吃)、透明可 fork(利于 star)、顺行业风向(CLI+SKILL 正取代 MCP)、零服务器最轻。放弃 MCP(重、被取代)与单一 CLI 黑盒(难 fork)。

## 4. 依赖策略:自动 bootstrap(核心 UX)

**原则**: 用户不手动安装任何东西。skill 首次调用时自我就位到私有目录 `~/.video-anything/`,不污染系统。

- `yt-dlp`: 下官方单文件二进制(~30MB)→ `~/.video-anything/bin/`
- `ffmpeg`: 下静态单文件(~40MB,按平台/arch 选)→ `~/.video-anything/bin/`
- `faster-whisper`: 建私有 venv `~/.video-anything/venv/` 并 pip 安装
- 所有脚本优先用私有 `bin`/`venv`,回退系统已装版本
- **诚实边界**: Whisper 模型权重(small ~460MB / tiny ~75MB)首次转录时下载一次,物理上绕不过;用「字幕优先 + 可选 tiny 模型 + 云引擎」缓解
- macOS 未签名二进制:用 `curl` 下载(不带 quarantine 属性),避免 Gatekeeper 拦截;必要时 `xattr -d com.apple.quarantine`

## 5. 数据流

```
URL
 → 解析(平台 extractor + id)           [fetch.sh 前置 --print]
 → yt-dlp 下载(视频 + 字幕 + 封面 + info.json)
 → ffmpeg 抽 16k 单声道 audio.wav
 → 有平台字幕? ── 是 → 清洗 vtt 为纯文本(跳过 ASR)
                └ 否 → transcribe.py(默认本地 Whisper)
 → transcript.md / .txt
 → agent 按选定 playbook 读 transcript + info → summary.md
```

输出目录:`video-out/<平台>-<id>/` 含 `video.mp4 / audio.wav / info.json / thumbnail.* / *.vtt / transcript.md / transcript.txt / summary.md`。

## 6. 组件与接口

| 组件 | 输入 | 输出 | 依赖 | 可单测 |
|---|---|---|---|---|
| `bootstrap.sh` | — | 私有 bin/venv 就位 | 网络 | 否(冒烟) |
| `check.sh` | — | 依赖 ✅/❌,缺则调 bootstrap | — | 否 |
| `fetch.sh` | URL, out_root | `<平台>-<id>/` 目录 | yt-dlp, ffmpeg | 否(冒烟) |
| `transcribe.py` | 音频路径, --model, --lang, --engine | transcript.md/.txt | whisper(本地/云) | 部分(纯函数抽到 lib) |
| `lib/asr_utils.py` | vtt / 时间戳 / url | 结构化 | — | ✅ |
| SKILL.md playbook | transcript + info | summary.md | agent 自身 | 否(人工验收) |

## 7. AI 加工层(4 个 playbook,写进 SKILL.md)

1. **提炼要点**: 3–7 条 bullet + 一句话主旨
2. **口播稿改写**: 按指定风格(小红书种草 / 知识拆解 / 播客口播)重写
3. **拆分镜**: 按时间戳切成 镜号 / 时间 / 画面 / 口播 表
4. **选题矩阵**: 基于主题衍生 5–10 个选题 + 标题

均为 SKILL.md 内的 markdown 指令模板,由 agent 执行,无外部模型 key。

## 8. ASR 双引擎(默认本地)

`transcribe.py` 引擎选择级联:
1. `--engine cloud` 或检测到 `GROQ_API_KEY` → 云(Groq Whisper API,秒级、无大下载)
2. 否则本地 `faster-whisper`(私有 venv,自动就位)
3. 否则系统 `whisper` / `whisper-cli`(降级)
4. 都无 → 明确报错 + bootstrap 提示

叠加「字幕优先」:第 5 节数据流里有平台字幕就跳过 ASR。默认本地保「零 key」卖点,有 key 者自动升级体验。

## 9. 错误处理与维护税对冲

- 分级不 silent fail:依赖缺失(check/bootstrap)、解析失败(提示 `yt-dlp -U` + cookie)、下载失败(平台专属提示指向 platforms.md)、ASR 引擎缺失(降级链)、无语音(明确告知)。
- **维护税对冲(全 5 平台一等公民的代价)**:失败自动建议/尝试升级 yt-dlp;cookie 逃生舱 `VA_COOKIES_FROM_BROWSER` / `VA_COOKIES`;每平台一条冒烟测试;错误信息可操作。

## 10. 测试策略(TDD,诚实划分)

- **可单测(pytest,测试先行)**: `lib/asr_utils.py` —— 时间戳格式化、VTT→md 解析、平台+id 推导、输出路径命名。用 fixture,不碰网络。
- **不可单测 → 冒烟**: `fetch.sh` / `bootstrap.sh` 是网络+二进制编排,`tests/smoke.sh` 拿各平台短公开链接跑,手动或带 flag 触发,不进默认 CI。
- 明确记录覆盖边界,不假装全覆盖。

## 11. 非目标 (YAGNI,v1 不做)

- ❌ 视频号(微信)—— Tier-3 二期,README 明标
- ❌ 批量 / 播放列表 —— 二期;脚本按单链接设计但不阻断后续加循环
- ❌ MCP 形态
- ❌ 云 ASR 作为默认(留 env 逃生舱)
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
