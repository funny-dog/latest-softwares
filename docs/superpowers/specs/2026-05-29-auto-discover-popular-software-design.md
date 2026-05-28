# 设计文档：自动发现热门软件 → 开 PR

- 日期：2026-05-29
- 状态：待 review
- 关联：CLAUDE.md（packages/ 是唯一手动编辑的配置）、AGENTS.md（fetcher 插件机制、Edition 系统、容错设计）

## Context（为什么做）

目前向 `packages/` 添加软件完全靠人工：手写 `id`/`name`/`category`/`editions`/`fetcher`/`args`/`desc_cn`/`desc_en`，其中最费力的是为 `github_release` fetcher 确定资产 `pattern`（如 `rufus-*.exe`）。随着清单已达 456 个，人工跟踪"哪些新热门软件值得收录"既费时又容易遗漏。

本功能引入一条**自动发现管道**：定时从可信源发现热门软件、自动推断 fetcher 配置、生成完整 YAML 条目，并**开 PR 供人工 review**。错误的推断不会直接进主分支——人工是最终质量闸门。

**目标**：用最小新增、最大复用现有架构（fetcher 插件模式、容错设计、CI 约定）的方式，把"添加热门软件"从纯人工变成"机器提议 + 人工审核"。

## Goals / Non-Goals

**Goals**
- 定时（双周）自动发现热门国际软件并开 PR
- 多源交叉验证保证候选可信（GitHub 热度 + winget/Scoop 佐证）
- 只收录能自动推断出 Windows 资产的候选（避免 sync 失败）
- 生成的条目默认 `editions: [cn, intl]`，`desc_en` 取自 repo、`desc_cn` 自动翻译
- 全流程容错：单源/单候选失败不影响其余；永不修改既有条目

**Non-Goals（本期不做）**
- **cn 国内专属软件的自动发现**（国内软件多走官网下载页、难自动推断资产）——保持手工维护，留作未来独立 spec
- 自动合并（始终经人工 review）
- 替换或修改既有 fetcher / 既有条目
- 非 `github_release` 类型的自动发现（chrome/steam 等官方 fetcher 仍手工配）

## 关键决策（来自需求澄清）

| 维度 | 决策 |
|------|------|
| 输出形式 | 定时 GitHub Action → 自动开 PR（不自动合并） |
| 推荐源 | GitHub（热度+资产）+ winget + Scoop（佐证），综合 |
| 质量门槛 | ①能自动推断 Windows 资产 ②多源交叉验证（≥2 源） |
| 触发 | 双周 cron；核心逻辑为可独立运行的 CLI |
| 默认 edition | `[cn, intl]`（共享，写入 shared.yaml） |
| desc_en | 取自 GitHub repo 描述 |
| desc_cn | MyMemory 免 key 翻译，失败降级占位符 |
| star 阈值 | ≥ 5000（排序下限，过滤噪音） |
| 每 PR 上限 | ≤ 10 条候选 |

## 架构

复用 `scripts/fetchers/` 的插件注册表模式，新建并列的 `scripts/discover/` 包。核心是一个可独立运行、可测试的 CLI，GitHub Action 仅定时调用它。

```
scripts/discover/
  __init__.py
  sources/
    __init__.py     # SOURCES 注册表（仿照 fetchers/__init__.py 的 FETCHERS）
    github.py       # GitHub Search API：高星 + 近期 Windows release
    winget.py       # winget-pkgs manifest 索引 → 引用的 owner/repo 集合
    scoop.py        # Scoop main bucket manifest → 引用的 owner/repo 集合
  aggregate.py      # 多源交叉验证 + 按 star 排序 + 截断 ≤10
  dedup.py          # 对照 packages/*.yaml 跳过已存在
  asset_infer.py    # 【最高风险】从 release 资产推断 Windows x64 glob pattern
  categorize.py     # GitHub topics/关键词 → 现有 category
  translate.py      # MyMemory 翻译后端（失败降级占位符）
  generate.py       # 组装成 validate_config 认可的条目
scripts/discover_popular.py   # CLI 入口（亦支持 python -m scripts.discover）
.github/workflows/discover.yml
tests/test_discover_*.py
```

## 数据流

```
双周 cron
  → discover_popular.py
      ① GitHub Search API（带 GITHUB_TOKEN 提升限额）：
          star ≥ 5000 + 近 12 个月有 release + release 含 Windows 资产
          → 候选 { repo, stars, description, topics, release_assets }
      ② winget-pkgs + Scoop main bucket：
          解析 manifest，收集被打包软件引用的上游 owner/repo
          → 佐证集合 corroborated_repos: set[str]
      ③ aggregate：保留满足
            (a) repo ∈ corroborated_repos（即 GitHub + winget/Scoop ≥2 源）
            (b) 资产可推断（见 asset_infer）
          的候选，按 star 降序，截断 ≤10
      ④ dedup：丢弃 packages/*.yaml 中已存在的（按 args.repo / homepage 归一化匹配）
      ⑤ 每个幸存者：infer pattern → categorize → translate desc → generate 条目
      ⑥ 把新条目追加写入 packages/shared.yaml（editions: [cn, intl]）
  → validate_config.py            （必须通过，否则不开 PR）
  → 干跑 python -m scripts.sync --only <新 id>   （确认 fetcher 真能解析）
  → peter-evans/create-pull-request：
        分支 auto/discover-YYYYMMDD
        PR 正文逐条列出：来源、star、置信度、推断的 pattern、是否翻译成功
人工 review → 校对 desc_cn、调整 category/editions（如降级为仅 intl）→ 合并
```

## 组件细节

### sources/（插件，仿 FETCHERS）
- `SOURCES` 字典注册三个源；每个源模块导出统一签名函数。
- `github.py`：调用 GitHub Search API（`q=stars:>=5000 ...`，按 stars 排序，分页）。对每个候选拉取 latest release 的资产列表。**用 `GITHUB_TOKEN` 认证**以提升 search 限额（未认证 10 req/min）。
- `winget.py` / `scoop.py`：拉取 manifest 索引，解析出每个包引用的上游 `owner/repo`（winget 的 `InstallerUrl`/`PackageUrl`、Scoop 的 `homepage`/`checkver`），归一化为 `owner/repo` 集合。**作用是佐证而非排名**（这两个源不公开下载量）。

### asset_infer.py（最高风险）
给定 release 资产文件名列表，识别 Windows x64 安装包并生成 glob：
- **命中关键词**：`win`/`windows`/`x64`/`amd64`/`setup`/`installer`/`.exe`/`.msi`
- **排除关键词**：`arm`/`arm64`/`aarch64`/`linux`/`mac`/`macos`/`darwin`/`android`/`.deb`/`.rpm`/`.dmg`/`.AppImage`
- **生成 pattern**：把文件名中的版本号子串（语义化版本 / 日期）替换为 `*`，如 `Foo-1.2.3-x64.exe` → `Foo-*-x64.exe`
- **拒绝策略**：零命中或多个互相冲突的候选且无法择优 → 拒绝该软件（质量门槛①，宁缺毋滥）

### dedup.py
复用 `scripts/config_loader.load_packages_config()` 读现有目录，构建已存在集合：归一化的 `args.repo`（小写）、`homepage` host。候选命中任一 → 跳过。复用 `validate_config.validate_cross_file_uniqueness` 的 id 唯一性思路防止生成重复 id。

### categorize.py
GitHub topics + 描述关键词 → 映射到现有 category 集合（实际取值）：
`Developer Tools` / `System Utilities` / `Utilities` / `Productivity` / `Media Players` / `Network & Proxy` / `Gaming` / `AI Tools` / `Messaging` / `Browsers` / `Security & Privacy` / `Cloud & DevOps` / `Operating Systems` / `Download Tools`。
无把握 → 默认 `Utilities`，留 review 调整。

### translate.py（MyMemory）
`translate(text: str, source="en", target="zh-CN") -> str`，调用 `https://api.mymemory.translated.net/get`。
- 失败（HTTP 错误 / 限额 / 空响应）→ 返回占位符 `"TODO: 待人工补充中文描述"`，候选仍保留。
- 设计成可替换后端（未来可换 DeepL）：内部走一个 `Translator` 协议，默认实现是 MyMemory。

### generate.py
组装 `validate_config` 认可的条目，字段顺序对齐现有 YAML：
```yaml
- id: <slugify(name)>          # 小写字母/数字/连字符，保证唯一
  name: <repo name 或 显示名>
  category: <categorize 结果>
  editions: [cn, intl]
  homepage: https://github.com/<owner>/<repo>
  fetcher: github_release
  args:
    repo: <owner>/<repo>
    assets:
    - platform: win-x64
      pattern: <asset_infer 结果>
  desc_cn: <翻译结果或占位符>
  desc_en: <repo 描述>
```

## 错误处理（对齐项目容错风格）
- **源级隔离**：单源失败（GitHub 限流 / winget 拉取失败）→ 记录并用剩余源继续。注意：源减少会使"≥2 源"门槛更难满足，可能本期发现 0 个，属可接受。**所有源都失败 → 退出码 1**（CI 可见），不开 PR。
- **候选级隔离**：asset 推断失败 → 跳过该候选；翻译失败 → 占位符。
- **永不修改既有条目**，只追加；dedup 保证幂等（重复运行不产生重复）。
- 结构化日志沿用 `print()` + UTF-8 reconfigure 约定（与 sync.py 一致）。

## 触发 / Workflow
- `.github/workflows/discover.yml`：`cron` 双周一次 + `workflow_dispatch`（支持手动触发）。
- 步骤：setup-python → install deps → 运行 CLI → validate_config → 干跑 sync 校验新 id → 用 `peter-evans/create-pull-request` 开 PR。
- 与现有 `sync.yml` 的数据提交（`stefanzweifel/git-auto-commit-action`）区别：发现管道**开 PR**而非直接 commit，因为需要人工 review。

## 测试（沿用 monkeypatch + 每模块独立 CI step）
- `test_discover_asset_infer`：各种资产名列表 → 期望 pattern 或拒绝（**最厚的测试**）。
- `test_discover_dedup`：构造既有 catalog → 正确跳过。
- `test_discover_aggregate`：多源交叉 + star 排序 + 截断逻辑。
- `test_discover_categorize`：topics/关键词 → category。
- `test_discover_translate`：mock MyMemory 成功响应 + 失败 → 占位符。
- `test_discover_generate`：**黄金测试**——生成条目喂给 `validate_config(...)` 必须返回空错误列表。
- 集成测试：用假 API 响应 fixture 跑全链路 → 断言产出合法 YAML 且 validate_config 通过。
- 新测试模块按现有约定加进 `.github/actions/python-lint-test/action.yml`（每模块一个 step）。

## 参数汇总
- cron 周期：双周
- star 阈值：≥ 5000（排序下限）
- 每 PR 候选上限：≤ 10
- release 活跃度窗口：近 12 个月有 release

## 未来工作（不在本期）
- **cn 国内专属软件自动发现**：需调研可信国内源（如 Gitee trending、国内镜像站），且资产推断策略不同（多为官网下载页 / fixed-URL fetcher）。作为独立 spec。
- 翻译后端可选升级为 DeepL（已预留 `Translator` 抽象）。
- 收录候选的 license 过滤（本期未列为硬门槛）。
