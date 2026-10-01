# Router / Nikki 集成

本目录用于把本项目最终的小型节点池接入 OpenWrt Nikki。

## 节点文件位置

Windows 本地 mihomo 测试完成后，由 `run_local_filter.ps1 -Publish` 发布到：

- `output/nikki-general.yaml`：普通池，默认最多 12 个
- `output/nikki-chatgpt.yaml`：GPT 专用池，默认最多 8 个

这两个文件进入 GitHub `main` 后，通过 jsDelivr CDN 提供给路由器：

- 普通池：`https://cdn.jsdelivr.net/gh/jeffwang9527/nikki-auto-filter@main/output/nikki-general.yaml`
- GPT 池：`https://cdn.jsdelivr.net/gh/jeffwang9527/nikki-auto-filter@main/output/nikki-chatgpt.yaml`

## 路由器自动下载

推荐使用 Mihomo 的 `proxy-providers`，而不是在 OpenWrt 上额外写一个轮询下载脚本。

`router/nikki-mixin.yaml` 定义两个 provider：

- `NIKKI-GENERAL` → 普通节点池
- `NIKKI-GPT` → GPT 专用节点池

两个 provider 的刷新周期均为 4 小时；节点健康检查为 5 分钟。

Nikki 官方项目当前支持 Profile Mixin、远程 subscription、以及 Scheduled Restart；Nikki 的运行流程会在启动/重载前将 subscription profile 与 mixin 合并后再启动 mihomo。参见 OpenWrt-nikki 项目说明及其 `nikki.init` 实现。

## 第一次安装

把 `apply_nikki_mixin.sh` 上传到路由器执行：

```sh
sh /tmp/apply_nikki_mixin.sh
```

脚本只改 Nikki 的 mixin 文件开关，不替换你现有的基础 profile/rules。

## 一个需要保留的边界

当前 mixin 已经把：

- `chatgpt.com`
- `openai.com`
- `oaistatic.com`
- `oaiusercontent.com`

导向 GPT 专用池。

普通流量仍由你现有的 Nikki 基础规则决定；这样不会因为本项目接入而把原来的国内直连、Apple、Telegram、Emby 等规则整体覆盖掉。

若希望“所有未命中现有规则的默认流量”也强制改走本项目普通池，需要根据你路由器现有的 profile/rule 结构，把现有默认组接到 `NIKKI-普通池`；不要直接用一个新的 `MATCH,NIKKI-普通池` 覆盖整个规则尾部，否则会改变现有分流逻辑。

## 更新链路

```
GitHub 云端（每 4h）
  ↓
普通候选 ≤100 + GPT候选 ≤72
  ↓
Windows 本地 mihomo
  ↓
普通 ≤12 + GPT ≤8
  ↓
Publish 到 main
  ↓
jsDelivr CDN
  ↓
Nikki proxy-providers 每 4h 拉取
  ↓
provider health-check 每 5m
```
