# 多源发现与版本刷新

发现负责扩大候选池，下载验证负责决定入口能否发布，两者分开验收。

```bash
uv run python -m scripts.discover --sources github winget brew scoop --max-scan 100 --max-output 30
```

默认不指定 `--sources` 时仍仅使用 GitHub，兼容既有命令。每周 Actions 明确启用四源，最多生成 30 条软件配置，开 PR 人工 review，不自动合并。国内商业软件等目录外项目仍可直接编辑 packages YAML 维护；必收录软件同时加入 `config/coverage.json`。

## 来源与预算

- GitHub：按 stars 查询，保存分窗、页码和页内 offset。超过 Search 1000 条结果上限时按星数递归拆分；每轮最多 12 次搜索请求和 `max-scan` 次 release 检查。临时失败的仓库保存元数据，下轮在退避到期后优先重试，重试最多占用 10 个扫描名额。404 无 release 与临时网络故障分开处理。
- WinGet：按字母/数字分区和 publisher tree 扫描，保存 publisher 及软件级 offset。按自然版本排序选择 installer manifest，使用可用的英文 locale 补全名称与官网。树被截断或清单身份冲突时报告失败，不把缺失响应当作空目录。
- Homebrew：读取官方 Cask JSON，按数组游标每轮扫描 `max-scan` 条，跳过禁用条目。架构必须有明确文件名证据；证据不足使用泛 `mac`，不会宣称 universal。
- Scoop：扫描 Main / Extras 的 git tree，避免 contents API 的 1000 文件限制；保存 bucket 与条目游标。保留 64bit、arm64、32bit 或泛 win 的真实证据，不把所有入口标成 x64。

`max-scan` 是每源候选/软件的扫描上限，不是所有 HTTP 请求总数：WinGet 获取 tree、installer 和 locale 会产生额外请求；Homebrew 会读取一次完整官方 JSON 列表。并发和请求重试沿用项目 net 层。没有运行长期吞吐/容量测试，不宣称可无限扩展。

GitHub 同一星数分组本身超过 1000 项时会明确暂停该分窗，需要进一步按创建时间分区；不会静默跳过整个星数分组。该边界及上游 API 可用性不能作为“全部软件已发现”的保证，必收录基准与其他来源仍需持续补全。

## 软件身份与证据

按 GitHub repo、规范化官网路径和带来源的稳定 ID 对齐候选，名称相同不代表同一软件。同名不同来源、不同仓库、同来源多个 ID 或互相冲突的证据进入 `data/discovery-candidates.json`。候选页中的来源证据尚不代表下载已验证。

已知软件目录源可独立提供候选；仅来自 GitHub 的候选继续使用有预算的 WinGet/Scoop 佐证。资产推断同分或 glob 会匹配多个文件时拒绝猜测。

超过本轮输出上限的合格候选保存在状态的 `pending` 队列。已选但尚未合入目录的候选也保留，避免下一轮 PR 覆盖掉前一轮候选；合入 packages 后由稳定 ID、repo、官网去重移出队列。审查拖延会导致队列增长，需要定期处理 PR，而不是只提高扫描预算。

## 持久化与拒绝名单

- `--state-file` 默认 `data/discovery-state.json`：游标、pending、失败与下次重试时间。Actions 使用 cache 跨轮保存，写入采用原子替换；不会提交测试临时数据。
- `--review-file` 默认 `data/discovery-candidates.json`：入选、冲突、无法可靠生成及跳过记录；Actions 上传 30 天 review artifact。
- `config/discovery-rejections.json`：人工长期拒绝名单，可填软件 slug、`owner/repo` 或 `winget:Publisher.App` / `brew:token` / `scoop:extras/name`。该配置是权威名单，移除条目后可重新进入候选。

缓存可能被 GitHub 回收，回收后发现会从初始游标重扫，目录去重仍生效。拒绝名单属于仓库配置，不依赖 cache。单源失败保持其他来源继续；所有来源均失败且无可处理候选时返回非零。

## 持续刷新下载元数据

来自软件目录的候选生成 `package_manifest`，保持稳定身份，而不是把首次发现的某版本 URL 永久固定在 `download_page` 中：

```yaml
- id: sample
  name: Sample
  category: Utilities
  editions: [cn, intl]
  homepage: https://example.com/download
  source_ids:
    brew: sample
  fetcher: package_manifest
  args:
    provider: brew
    package: sample
    platforms:
    - platform: mac
```

provider 可选 `winget`、`brew`、`scoop`；package 分别为 `Publisher.App`、cask token、`main/name` 或 `extras/name`。每次到期同步重新读取对应清单，版本、URL、平台、上游 SHA256 一起更新，不执行 Ruby/PowerShell/安装脚本。

WinGet 先限制架构，再按明确策略优先正式安装器（wix/msi/inno/nullsoft/exe 等）与用户范围；同优先级存在不同下载文件时要求人工消歧，不依赖数组顺序。Brew 不能凭通配符宣称架构，Scoop 多文件安装和无法对应的平台也不会猜测。

source_ids 保存已确认的跨来源映射；自动生成初始下载平台采用可靠的主来源，其他平台是否需要支持由必收录基准和配置明确声明。多个来源的不同版本不会随意拼成同一个发布版本。

## PR 与发布是两道门禁

发现 PR 需 review 软件身份、来源、平台、版本策略、描述和 edition。新条目试抓取仅提供日志，不自动证明网络可用。提交范围仍仅为 packages/shared.yaml，review/state 通过独立产物与 cache 保存。

合并后，发布流水线另行执行真实入口验证和覆盖门禁；403、错误 HTML、未知跨域跳转等不能因为目录存在就被标为验证成功。少量线上元数据样本通过也不能替代全量入口验收。
