# 平台专属处理

按需读取。大多数平台 `yt-dlp` 直接就能下,先试 `scripts/fetch.sh`,失效再查这里。

> 以下状态是 Phase 0 临时校准,等待新的 download foundation smoke 通过后再升级。

## 通用排错

1. 先升级:`yt-dlp -U`(平台反爬变化频繁,90% 的失效靠升级解决)。
2. 短链先展开(抖音/快手分享链是短链,yt-dlp 一般能自动跟随;若不行手动 `curl -sIL <短链>` 取 Location)。
3. 登录/地区限制 → 加 cookie:
   ```bash
   export VA_COOKIES_FROM_BROWSER=chrome    # 从浏览器读 cookie
   # 或
   export VA_COOKIES=/path/to/cookies.txt   # Netscape 格式 cookies 文件
   ```

## 各平台

### YouTube — provisional
yt-dlp 原生,无特殊处理。会员/付费内容不下(红线)。

### Bilibili B站 — provisional
- **412 风控**:海外 IP 必须带 cookie(`VA_COOKIES_FROM_BROWSER=chrome`),国内 IP 一般不受影响。
- 大会员专享清晰度不下(红线)。合集用单集 URL。

### Twitter / X — provisional
yt-dlp 原生。受保护账号需 cookie。

### 抖音 Douyin — provisional
- 经 yt-dlp 官方 extractor 拿到的一般是**无水印源**。
- 分享文案里的短链(`v.douyin.com/xxx`)直接传即可,yt-dlp 会跟随跳转。
- 偶发需要 cookie(部分内容风控)。

### 快手 Kuaishou — experimental
- 反爬较强,失效先升级 yt-dlp;必要时带 cookie。
- 若 yt-dlp extractor 失效,记录 issue,考虑接专用解析(二期)。

### 视频号(微信)— unsupported
- **封闭生态**:yt-dlp 不支持,视频流加密、绑定微信客户端,常规手段拿不到直链。
- 可行路线(均较重,列为二期评估):
  - 微信客户端抓包(mitmproxy + 对应解密),仅本机自用;
  - 第三方解析服务(稳定性/合规存疑,不纳入核心);
- **v0.1 不承诺视频号**,README 里如实标注,避免用户预期落空。

### 其他站点 — experimental
yt-dlp 支持 1800+ 站点,直接把 URL 丢给 `fetch.sh` 试。支持列表:`yt-dlp --list-extractors`。

## 无水印说明
「无水印」不是一个开关,而是取决于该平台 extractor 返回的源地址。抖音/快手经官方 API extractor 通常即无水印;若拿到带水印源,查 yt-dlp 对应 extractor 的 issue 或升级版本。
