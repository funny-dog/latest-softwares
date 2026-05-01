# latest-softwares 工程化改进设计规范

## 概述

本设计规范定义了 latest-softwares 项目的 6 项工程化改进，目标是在不破坏现有"小而美"特性的前提下，使项目在规模达到 1000+ 软件时仍能可靠维护。

## 当前状态

### 项目规模
- **软件数量**：428 个（intl 343 个 + cn 52 个 + shared 33 个）
- **packages.yaml**：7218 行 / 226KB
- **生产依赖**：4 个（fastapi、PyYAML、requests、Jinja2）
- **开发依赖**：2 个（ruff、pytest）

### 现有基础设施
- **CI/CD**：3 个 workflow 文件（sync.yml、deploy-only.yml、sync-metrics.yml）
- **代码质量**：ruff check + ruff format（仅 CI 检查）
- **测试**：pytest 覆盖 12 个测试模块
- **前端**：app.js 14.3K + vendor ~470KB，无构建管道

### 已识别的工程化短板
1. 无类型检查，fetcher 返回值偏离契约只能在运行时发现
2. 依赖手工 pin，无自动化升级与安全告警
3. 错误日志仅为 print()，失败率突增无法被 CI 自动发现
4. 提交前缺少自动 lint 拦截
5. 前端无 minification、无版本哈希
6. packages.yaml 单文件过大，批量变更时难以审查

---

## 改进项 1：类型检查（mypy）

### 目标
在核心模块引入静态类型检查，提前发现 fetcher 返回值偏离契约的问题。

### 设计决策
- **渐进式启用**：先对 3 个核心文件强制类型检查，25 个 fetcher 暂不强制
  - `scripts/fetchers/base.py`：FetchResult / AssetInfo 数据契约
  - `scripts/editions.py`：版本过滤逻辑
  - `scripts/sync.py`：同步主流程
- **严格模式**：启用 `strict = true`，确保类型注解的完整性
- **CI 集成**：在 ruff 检查后追加 mypy 检查

### 实施范围
- **新增依赖**：mypy、types-PyYAML、types-requests
- **配置文件**：pyproject.toml（[tool.mypy] 配置）
- **CI 修改**：.github/actions/python-lint-test/action.yml
- **不改动**：所有 scripts/fetchers/*.py（除非类型错误暴露真 bug）

### 验收标准
- `python -m mypy` 对核心 3 个文件通过
- CI 中 mypy 检查步骤正常运行
- 现有测试全部通过

---

## 改进项 2：Dependabot 自动依赖升级

### 目标
自动化依赖升级流程，及时获取安全补丁和功能更新。

### 设计决策
- **分组策略**：minor + patch 更新合并为一个 PR，major 版本单独 PR
- **更新频率**：每周一检查
- **PR 限制**：最多 5 个开放 PR

### 实施范围
- **新增文件**：.github/dependabot.yml
- **覆盖范围**：pip 依赖 + GitHub Actions

### 验收标准
- dependabot.yml 配置正确
- Dependabot 能正常创建 PR（需推送到 GitHub 验证）

---

## 改进项 3：结构化错误日志 + 失败率监控

### 目标
将同步过程的错误信息结构化，实现失败率自动监控。

### 设计决策
- **非破坏性**：保留现有 print() 输出，同时追加 JSONL 格式日志
- **失败率门槛**：10% 失败率触发 CI 失败
- **日志位置**：data/sync_errors.jsonl（追加写入）

### 数据结构
```json
{
  "id": "firefox",
  "fetcher": "github_release",
  "status": "ok|fail|stale",
  "error": "错误信息（仅 fail 时）",
  "timestamp": "2026-05-01T12:00:00Z"
}
```

### 实施范围
- **修改文件**：scripts/sync.py（+30 行）、.github/workflows/sync.yml
- **新增文件**：scripts/check_sync_health.py（~60 行）、tests/test_check_sync_health.py
- **gitignore**：追加 data/sync_errors.jsonl

### 验收标准
- sync 运行后生成 data/sync_errors.jsonl
- 失败率 > 10% 时 CI 步骤失败
- 现有 print() 输出不变

---

## 改进项 4：pre-commit hooks

### 目标
在提交前自动执行代码质量检查，减少 CI 重跑。

### 设计决策
- **仅本地便利**：CI 仍是 ruff 检查的真理来源
- **钩子范围**：ruff check、ruff format、YAML 校验、大文件检查、行尾修复

### 实施范围
- **新增文件**：.pre-commit-config.yaml
- **文档更新**：CLAUDE.md、AGENTS.md（添加安装说明）

### 验收标准
- `pre-commit run --all-files` 通过
- 文档中有清晰的安装说明

---

## 改进项 5：packages.yaml 拆分

### 目标
将大文件按版本拆分，便于 git diff 审查。

### 设计决策
- **拆分方式**：按 editions 字段拆分为 3 个文件
  - `packages/shared.yaml`：33 个 cn+intl 共享软件
  - `packages/cn.yaml`：52 个国内版软件
  - `packages/intl.yaml`：343 个国际版软件
- **兼容性**：保留 packages.yaml 兼容路径，降低迁移风险
- **迁移验证**：拆分前后总数一致（428 = 33 + 52 + 343）

### 实施范围
- **修改文件**：scripts/sync.py（+25 行）、scripts/validate_config.py
- **新增文件**：scripts/migrate_packages.py（一次性迁移脚本）、packages/*.yaml
- **测试更新**：tests/test_validate_config.py（跨文件 id 唯一性检查）
- **删除**：packages.yaml（迁移完成且 CI 通过后）

### 验收标准
- 迁移前后软件总数一致（428 个）
- `python -m scripts.sync && git diff data/latest.json` 除时间戳外无 diff
- 跨文件 id 唯一性检查通过

### 风险与缓解
- **风险**：拆分时丢失或重复条目 → 迁移脚本统计前后总数
- **风险**：CI 分片逻辑依赖 packages 总数 → 验证分片仍按 id 工作
- **回滚**：保留 packages.yaml 兼容路径直到下个 release

---

## 改进项 6：前端构建管道（esbuild）

### 目标
为前端资源添加 minification 和版本哈希，提升加载性能和缓存管理。

### 设计决策
- **最小侵入**：保持无框架，只加 esbuild 一步
- **vendor 不重打包**：已 sha256 锁定，保留独立可审计性
- **降级路径**：若 esbuild 失败，回退到原文件

### 构建产物
- `web/dist/app.[hash].js`：minified app.js
- `web/dist/styles.[hash].css`：minified styles.css
- `web/dist/asset-manifest.json`：资源映射表

### 实施范围
- **新增文件**：package.json、package-lock.json、scripts/build_assets.mjs
- **修改文件**：scripts/build_web.py（+20 行）、.github/workflows/sync.yml
- **gitignore**：追加 web/dist/、node_modules/

### 验收标准
- `npm run build` 生成带哈希的资源文件
- build_web.py 正确引用 hashed 资源
- esbuild 失败时回退到原文件

### 风险与缓解
- **风险**：增加 Node 依赖 → esbuild 单一二进制 + 无运行时依赖
- **降级路径**：esbuild 失败时回退到原文件

---

## 实施策略

### 顺序
按风险递增、收益由内到外排序：
1. Dependabot（极低风险）
2. pre-commit（低风险）
3. mypy（中风险，可能暴露 bug）
4. 结构化错误日志（中风险）
5. 前端构建（中高风险）
6. packages.yaml 拆分（高风险）

### PR 策略
每个改进项单独一个 PR，便于独立 review 和 revert。

### 验证方案
- 每个 PR 完成后运行完整测试套件
- 改进项 5 需专项验证迁移前后数据一致性
- 改进项 6 需验证 esbuild 失败时的降级路径

---

## 依赖关系

- 改进项 1-4 相互独立，可并行实施
- 改进项 5 软依赖改进项 3（结构化日志有助于监控迁移过程，但非硬性要求）
- 改进项 6 独立于其他改进项

## 成功标准

所有 6 个改进项完成后：
- `pytest` 全部通过
- `python -m mypy` 对核心文件通过
- `pre-commit run --all-files` 通过
- CI 所有检查步骤通过
- 前端资源有版本哈希
- packages.yaml 拆分为 3 个文件
