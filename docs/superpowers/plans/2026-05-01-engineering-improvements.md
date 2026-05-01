# latest-softwares 工程化改进实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实施 6 项工程化改进，使项目在规模达到 1000+ 软件时仍能可靠维护

**Architecture:** 按风险递增顺序逐个实施，每个改进项独立 PR，保持向后兼容

**Tech Stack:** Python 3.10+, mypy, ruff, pre-commit, esbuild, GitHub Actions

---

## 文件结构映射

### 改进项 1：mypy 类型检查
- **Modify:** `requirements-dev.txt` - 添加 mypy 依赖
- **Modify:** `pyproject.toml` - 添加 [tool.mypy] 配置
- **Modify:** `.github/actions/python-lint-test/action.yml` - 添加 mypy 检查步骤

### 改进项 2：Dependabot
- **Create:** `.github/dependabot.yml` - Dependabot 配置

### 改进项 3：结构化错误日志
- **Modify:** `scripts/sync.py` - 添加 JSONL 日志输出
- **Create:** `scripts/check_sync_health.py` - 失败率检查脚本
- **Create:** `tests/test_check_sync_health.py` - 失败率检查测试
- **Modify:** `.github/workflows/sync.yml` - 添加失败率检查步骤
- **Modify:** `.gitignore` - 添加 sync_errors.jsonl

### 改进项 4：pre-commit hooks
- **Create:** `.pre-commit-config.yaml` - pre-commit 配置
- **Modify:** `CLAUDE.md` - 添加 pre-commit 安装说明
- **Modify:** `AGENTS.md` - 添加 pre-commit 安装说明

### 改进项 5：packages.yaml 拆分
- **Create:** `packages/shared.yaml` - 共享软件清单
- **Create:** `packages/cn.yaml` - 国内版软件清单
- **Create:** `packages/intl.yaml` - 国际版软件清单
- **Create:** `scripts/migrate_packages.py` - 迁移脚本
- **Modify:** `scripts/sync.py` - 支持目录加载
- **Modify:** `scripts/validate_config.py` - 跨文件 id 唯一性检查
- **Modify:** `tests/test_validate_config.py` - 添加跨文件测试

### 改进项 6：前端构建管道
- **Create:** `package.json` - Node.js 依赖配置
- **Create:** `scripts/build_assets.mjs` - esbuild 构建脚本
- **Modify:** `scripts/build_web.py` - 集成构建管道
- **Modify:** `.github/workflows/sync.yml` - 添加 Node.js 构建步骤
- **Modify:** `.gitignore` - 添加 web/dist/ 和 node_modules/

---

## 改进项 1：mypy 类型检查

### Task 1.1: 添加 mypy 依赖

**Files:**
- Modify: `requirements-dev.txt`

- [ ] **Step 1: 读取当前 requirements-dev.txt**

```bash
cat requirements-dev.txt
```

Expected output:
```
ruff==0.15.12
pytest==9.0.3
```

- [ ] **Step 2: 添加 mypy 和类型存根依赖**

```python
# requirements-dev.txt
ruff==0.15.12
pytest==9.0.3
mypy==1.13.0
types-PyYAML==6.0.12.12
types-requests==2.31.0.2
```

- [ ] **Step 3: 安装依赖验证**

```bash
pip install -r requirements-dev.txt
python -m mypy --version
```

Expected output: `mypy 1.13.0`

- [ ] **Step 4: Commit**

```bash
git add requirements-dev.txt
git commit -m "deps: add mypy and type stubs for static type checking"
```

---

### Task 1.2: 配置 mypy

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 读取当前 pyproject.toml**

```bash
cat pyproject.toml
```

- [ ] **Step 2: 添加 mypy 配置**

```toml
# pyproject.toml (追加到文件末尾)

[tool.mypy]
python_version = "3.10"
strict = true
files = ["scripts/fetchers/base.py", "scripts/editions.py", "scripts/sync.py"]

[[tool.mypy.overrides]]
module = "scripts.fetchers.*"
disallow_untyped_defs = false
```

- [ ] **Step 3: 验证配置**

```bash
python -m mypy --config-file pyproject.toml scripts/fetchers/base.py
```

Expected: 可能有类型错误，但配置本身应该有效

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "config: add mypy strict mode configuration for core modules"
```

---

### Task 1.3: 修复 mypy 类型错误（如有）

**Files:**
- Modify: `scripts/fetchers/base.py` (如有类型错误)
- Modify: `scripts/editions.py` (如有类型错误)
- Modify: `scripts/sync.py` (如有类型错误)

- [ ] **Step 1: 运行 mypy 检查核心文件**

```bash
python -m mypy scripts/fetchers/base.py scripts/editions.py scripts/sync.py
```

- [ ] **Step 2: 修复发现的类型错误**

根据 mypy 输出修复类型错误。常见修复：
- 添加缺失的类型注解
- 修复 Optional 类型处理
- 添加类型存根

- [ ] **Step 3: 验证修复**

```bash
python -m mypy scripts/fetchers/base.py scripts/editions.py scripts/sync.py
```

Expected: `Success: no issues found`

- [ ] **Step 4: 运行现有测试确保无回归**

```bash
pytest tests/test_sync.py tests/test_validate_config.py -q
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add scripts/fetchers/base.py scripts/editions.py scripts/sync.py
git commit -m "fix: resolve mypy type errors in core modules"
```

---

### Task 1.4: 集成 mypy 到 CI

**Files:**
- Modify: `.github/actions/python-lint-test/action.yml`

- [ ] **Step 1: 读取当前 CI action**

```bash
cat .github/actions/python-lint-test/action.yml
```

- [ ] **Step 2: 在 ruff 检查后添加 mypy 步骤**

```yaml
# .github/actions/python-lint-test/action.yml
# 在 "Lint - ruff format" 步骤后添加

    - name: Lint - mypy
      if: ${{ !cancelled() }}
      shell: bash
      run: python -m mypy
```

- [ ] **Step 3: 验证 YAML 语法**

```bash
python -c "import yaml; yaml.safe_load(open('.github/actions/python-lint-test/action.yml'))"
```

Expected: 无输出（语法正确）

- [ ] **Step 4: Commit**

```bash
git add .github/actions/python-lint-test/action.yml
git commit -m "ci: add mypy type checking to lint workflow"
```

---

## 改进项 2：Dependabot 自动依赖升级

### Task 2.1: 创建 Dependabot 配置

**Files:**
- Create: `.github/dependabot.yml`

- [ ] **Step 1: 创建 dependabot.yml**

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 5
    groups:
      python-minor-patch:
        update-types: ["minor", "patch"]

  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      actions-minor-patch:
        update-types: ["minor", "patch"]
```

- [ ] **Step 2: 验证 YAML 语法**

```bash
python -c "import yaml; yaml.safe_load(open('.github/dependabot.yml'))"
```

Expected: 无输出（语法正确）

- [ ] **Step 3: Commit**

```bash
git add .github/dependabot.yml
git commit -m "ci: add Dependabot for automated dependency updates"
```

---

## 改进项 3：结构化错误日志 + 失败率监控

### Task 3.1: 添加结构化日志输出

**Files:**
- Modify: `scripts/sync.py`

- [ ] **Step 1: 读取 sync.py 的 _run_one 函数**

```bash
grep -n "_run_one" scripts/sync.py
```

- [ ] **Step 2: 添加 JSONL 日志写入逻辑**

```python
# scripts/sync.py
# 在文件顶部添加导入
import json
from pathlib import Path

# 在 _run_one 函数中，print 语句后添加 JSONL 日志写入
def _run_one(eid, entry, previous, ...):
    # ... 现有代码 ...
    try:
        # ... 现有 fetcher 调用逻辑 ...
        print(f"✓ {eid}: {res.version} ({len(res.assets)} 个平台)")

        # 新增：写入 JSONL 日志
        _write_sync_log(eid, entry.get("fetcher", "unknown"), "ok", None)

        return (eid, result, True, None)
    except Exception as e:
        msg = str(e)
        print(f"✗ {eid}: {msg}", file=sys.stderr)

        # 新增：写入 JSONL 日志
        _write_sync_log(eid, entry.get("fetcher", "unknown"), "fail", msg)

        if eid in previous:
            stale = _stale_from_previous(previous[eid], msg)
            _apply_config_metadata(stale, entry)
            print(f"  ↳ 复用上次数据（{previous[eid].get('version')}）", file=sys.stderr)
            return (eid, stale, False, (eid, msg))
        return (eid, None, False, (eid, msg))

def _write_sync_log(eid: str, fetcher: str, status: str, error: str | None) -> None:
    """追加同步结果到 JSONL 日志文件"""
    log_file = Path("data/sync_errors.jsonl")
    log_entry = {
        "id": eid,
        "fetcher": fetcher,
        "status": status,
        "error": error,
        "timestamp": datetime.now().isoformat(),
    }
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
```

- [ ] **Step 3: 添加 datetime 导入**

```python
# scripts/sync.py 文件顶部
from datetime import datetime
```

- [ ] **Step 4: 运行测试验证无回归**

```bash
pytest tests/test_sync.py -q
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add scripts/sync.py
git commit -m "feat: add structured JSONL logging to sync process"
```

---

### Task 3.2: 创建失败率检查脚本

**Files:**
- Create: `scripts/check_sync_health.py`
- Create: `tests/test_check_sync_health.py`

- [ ] **Step 1: 创建测试文件**

```python
# tests/test_check_sync_health.py
import json
import pytest
from pathlib import Path
from scripts.check_sync_health import check_sync_health


def test_check_sync_health_pass(tmp_path):
    """失败率低于阈值时应通过"""
    log_file = tmp_path / "sync_errors.jsonl"
    # 写入 10 条记录，1 条失败（10%）
    entries = [{"id": f"pkg{i}", "status": "ok"} for i in range(9)]
    entries.append({"id": "pkg9", "status": "fail", "error": "timeout"})
    with open(log_file, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    result = check_sync_health(log_file, max_fail_rate=0.10)
    assert result is True


def test_check_sync_health_fail(tmp_path):
    """失败率高于阈值时应失败"""
    log_file = tmp_path / "sync_errors.jsonl"
    # 写入 10 条记录，2 条失败（20%）
    entries = [{"id": f"pkg{i}", "status": "ok"} for i in range(8)]
    entries.append({"id": "pkg8", "status": "fail", "error": "timeout"})
    entries.append({"id": "pkg9", "status": "fail", "error": "404"})
    with open(log_file, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    result = check_sync_health(log_file, max_fail_rate=0.10)
    assert result is False


def test_check_sync_health_empty_file(tmp_path):
    """空日志文件应通过"""
    log_file = tmp_path / "sync_errors.jsonl"
    log_file.touch()

    result = check_sync_health(log_file, max_fail_rate=0.10)
    assert result is True


def test_check_sync_health_no_file(tmp_path):
    """日志文件不存在时应通过"""
    log_file = tmp_path / "sync_errors.jsonl"

    result = check_sync_health(log_file, max_fail_rate=0.10)
    assert result is True
```

- [ ] **Step 2: 运行测试验证失败**

```bash
pytest tests/test_check_sync_health.py -v
```

Expected: FAIL (模块不存在)

- [ ] **Step 3: 创建实现文件**

```python
# scripts/check_sync_health.py
"""检查同步失败率，超过阈值时返回非零退出码"""

import json
import sys
from pathlib import Path


def check_sync_health(log_file: Path, max_fail_rate: float = 0.10) -> bool:
    """
    检查同步失败率

    Args:
        log_file: JSONL 日志文件路径
        max_fail_rate: 最大允许失败率（默认 10%）

    Returns:
        True 如果失败率在阈值内，False 否则
    """
    if not log_file.exists():
        return True

    total = 0
    failures = 0

    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            total += 1
            if entry.get("status") == "fail":
                failures += 1

    if total == 0:
        return True

    fail_rate = failures / total
    return fail_rate <= max_fail_rate


def main() -> int:
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-fail-rate",
        type=float,
        default=0.10,
        help="最大允许失败率（默认 0.10，即 10%%）",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("data/sync_errors.jsonl"),
        help="JSONL 日志文件路径",
    )
    args = parser.parse_args()

    if check_sync_health(args.log_file, args.max_fail_rate):
        print(f"✓ 同步健康检查通过（失败率 ≤ {args.max_fail_rate:.0%}）")
        return 0
    else:
        print(f"✗ 同步失败率超过阈值（{args.max_fail_rate:.0%}）", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行测试验证通过**

```bash
pytest tests/test_check_sync_health.py -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/check_sync_health.py tests/test_check_sync_health.py
git commit -m "feat: add sync health check script with failure rate monitoring"
```

---

### Task 3.3: 集成失败率检查到 CI

**Files:**
- Modify: `.github/workflows/sync.yml`
- Modify: `.gitignore`

- [ ] **Step 1: 读取 sync.yml 找到 sync 步骤位置**

```bash
grep -n "python -m scripts.sync" .github/workflows/sync.yml
```

- [ ] **Step 2: 在 sync 步骤后添加健康检查**

```yaml
# .github/workflows/sync.yml
# 在 "Run sync" 步骤后添加

    - name: Check sync failure rate
      if: ${{ !cancelled() }}
      shell: bash
      run: python scripts/check_sync_health.py --max-fail-rate 0.10
```

- [ ] **Step 3: 添加 sync_errors.jsonl 到 .gitignore**

```bash
echo "" >> .gitignore
echo "# 同步错误日志（CI 临时生成）" >> .gitignore
echo "data/sync_errors.jsonl" >> .gitignore
```

- [ ] **Step 4: 验证 .gitignore 更新**

```bash
tail -3 .gitignore
```

Expected:
```
# 同步错误日志（CI 临时生成）
data/sync_errors.jsonl
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/sync.yml .gitignore
git commit -m "ci: add sync failure rate check to workflow"
```

---

## 改进项 4：pre-commit hooks

### Task 4.1: 创建 pre-commit 配置

**Files:**
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: 创建配置文件**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.15.12
    hooks:
      - id: ruff
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: check-yaml
        exclude: ^packages\.yaml$
      - id: check-added-large-files
        args: ['--maxkb=500']
      - id: end-of-file-fixer
      - id: trailing-whitespace
```

- [ ] **Step 2: 验证 YAML 语法**

```bash
python -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml'))"
```

Expected: 无输出（语法正确）

- [ ] **Step 3: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "config: add pre-commit hooks for local code quality"
```

---

### Task 4.2: 更新文档添加 pre-commit 安装说明

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md` (如果存在)

- [ ] **Step 1: 读取 CLAUDE.md 找到开发流程章节**

```bash
grep -n "核心命令" CLAUDE.md
```

- [ ] **Step 2: 在开发流程章节添加 pre-commit 说明**

```markdown
# CLAUDE.md
# 在"核心命令"章节的代码块后添加

## Pre-commit Hooks

```bash
# 一次性安装 pre-commit hooks
pip install pre-commit && pre-commit install

# 手动运行所有 hooks
pre-commit run --all-files
```
```

- [ ] **Step 3: 检查 AGENTS.md 是否存在并更新**

```bash
if [ -f AGENTS.md ]; then
    # 在开发流程章节添加类似说明
    echo "AGENTS.md exists, update it similarly"
else
    echo "AGENTS.md does not exist, skip"
fi
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add pre-commit installation instructions"
```

---

## 改进项 5：packages.yaml 拆分

### Task 5.1: 创建迁移脚本

**Files:**
- Create: `scripts/migrate_packages.py`

- [ ] **Step 1: 创建迁移脚本**

```python
# scripts/migrate_packages.py
"""将 packages.yaml 按 editions 字段拆分为 3 个文件"""

import yaml
import sys
from pathlib import Path


def migrate_packages(source: Path, target_dir: Path) -> dict[str, int]:
    """
    迁移 packages.yaml 到按版本拆分的目录

    Args:
        source: 源 packages.yaml 文件路径
        target_dir: 目标目录路径

    Returns:
        各文件的软件数量统计
    """
    with open(source, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    packages = data.get("packages", [])

    # 按 editions 分组
    shared = []
    cn_only = []
    intl_only = []

    for pkg in packages:
        editions = pkg.get("editions", [])
        if "cn" in editions and "intl" in editions:
            shared.append(pkg)
        elif "cn" in editions:
            cn_only.append(pkg)
        elif "intl" in editions:
            intl_only.append(pkg)
        else:
            # 默认归入 shared
            shared.append(pkg)

    # 创建目标目录
    target_dir.mkdir(parents=True, exist_ok=True)

    # 写入文件
    for filename, items in [
        ("shared.yaml", shared),
        ("cn.yaml", cn_only),
        ("intl.yaml", intl_only),
    ]:
        target_file = target_dir / filename
        with open(target_file, "w", encoding="utf-8") as f:
            yaml.dump(
                {"packages": items},
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
            )

    return {
        "shared": len(shared),
        "cn": len(cn_only),
        "intl": len(intl_only),
        "total": len(packages),
    }


def main() -> int:
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("packages.yaml"),
        help="源 packages.yaml 文件路径",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path("packages"),
        help="目标目录路径",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅显示统计信息，不实际写入文件",
    )
    args = parser.parse_args()

    if not args.source.exists():
        print(f"✗ 源文件不存在: {args.source}", file=sys.stderr)
        return 1

    if args.dry_run:
        with open(args.source, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        packages = data.get("packages", [])
        shared = sum(1 for p in packages if "cn" in p.get("editions", []) and "intl" in p.get("editions", []))
        cn = sum(1 for p in packages if "cn" in p.get("editions", []) and "intl" not in p.get("editions", []))
        intl = sum(1 for p in packages if "intl" in p.get("editions", []) and "cn" not in p.get("editions", []))
        print(f"统计: shared={shared}, cn={cn}, intl={intl}, total={len(packages)}")
        return 0

    stats = migrate_packages(args.source, args.target_dir)
    print(f"✓ 迁移完成:")
    print(f"  shared: {stats['shared']}")
    print(f"  cn: {stats['cn']}")
    print(f"  intl: {stats['intl']}")
    print(f"  total: {stats['total']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 测试迁移脚本（dry-run）**

```bash
python scripts/migrate_packages.py --dry-run
```

Expected output: `统计: shared=33, cn=52, intl=343, total=428`

- [ ] **Step 3: Commit**

```bash
git add scripts/migrate_packages.py
git commit -m "feat: add packages.yaml migration script"
```

---

### Task 5.2: 执行迁移

**Files:**
- Create: `packages/shared.yaml`
- Create: `packages/cn.yaml`
- Create: `packages/intl.yaml`

- [ ] **Step 1: 执行迁移**

```bash
python scripts/migrate_packages.py
```

Expected output:
```
✓ 迁移完成:
  shared: 33
  cn: 52
  intl: 343
  total: 428
```

- [ ] **Step 2: 验证迁移结果**

```bash
# 验证文件存在
ls -la packages/

# 验证总数一致
python -c "
import yaml
total = sum(len(yaml.safe_load(open(f'packages/{e}.yaml')).get('packages', []))
            for e in ['shared', 'cn', 'intl'])
print(f'迁移后总数: {total}')
"
```

Expected: `迁移后总数: 428`

- [ ] **Step 3: Commit**

```bash
git add packages/
git commit -m "feat: split packages.yaml into shared/cn/intl editions"
```

---

### Task 5.3: 修改 sync.py 支持目录加载

**Files:**
- Modify: `scripts/sync.py`

- [ ] **Step 1: 读取 sync.py 的配置加载逻辑**

```bash
grep -n "yaml.safe_load" scripts/sync.py
```

- [ ] **Step 2: 添加目录加载函数**

```python
# scripts/sync.py
# 在文件顶部添加导入
from pathlib import Path

def _load_packages_dir(packages_dir: Path) -> dict:
    """从 packages/ 目录加载并合并所有 yaml 文件"""
    all_packages = []
    for yaml_file in sorted(packages_dir.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        all_packages.extend(data.get("packages", []))
    return {"packages": all_packages}
```

- [ ] **Step 3: 修改主加载逻辑**

```python
# scripts/sync.py
# 找到配置加载位置，修改为：

PACKAGES_FILE = REPO_ROOT / "packages.yaml"
PACKAGES_DIR = REPO_ROOT / "packages"

def load_packages_config() -> dict:
    """加载软件包配置，支持目录或单文件"""
    if PACKAGES_DIR.is_dir():
        return _load_packages_dir(PACKAGES_DIR)
    else:
        return yaml.safe_load(PACKAGES_FILE.read_text(encoding="utf-8"))

# 在 main() 函数中使用
cfg = load_packages_config()
```

- [ ] **Step 4: 运行测试验证无回归**

```bash
pytest tests/test_sync.py -q
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add scripts/sync.py
git commit -m "feat: support loading packages from directory"
```

---

### Task 5.4: 添加跨文件 id 唯一性检查

**Files:**
- Modify: `scripts/validate_config.py`
- Modify: `tests/test_validate_config.py`

- [ ] **Step 1: 读取 validate_config.py**

```bash
grep -n "def validate" scripts/validate_config.py
```

- [ ] **Step 2: 添加跨文件 id 唯一性检查函数**

```python
# scripts/validate_config.py

def validate_cross_file_uniqueness(packages_dir: Path) -> list[str]:
    """检查 packages/ 目录下所有文件的 id 唯一性"""
    errors = []
    seen_ids = set()

    for yaml_file in sorted(packages_dir.glob("*.yaml")):
        if yaml_file.name.startswith("_"):
            continue
        with open(yaml_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for pkg in data.get("packages", []):
            pkg_id = pkg.get("id")
            if pkg_id in seen_ids:
                errors.append(f"重复的 id '{pkg_id}' 在 {yaml_file.name} 中")
            seen_ids.add(pkg_id)

    return errors
```

- [ ] **Step 3: 在主验证流程中调用**

```python
# scripts/validate_config.py
# 在 main() 函数中添加

packages_dir = Path("packages")
if packages_dir.is_dir():
    cross_file_errors = validate_cross_file_uniqueness(packages_dir)
    errors.extend(cross_file_errors)
```

- [ ] **Step 4: 添加测试**

```python
# tests/test_validate_config.py

def test_validate_cross_file_uniqueness(tmp_path):
    """测试跨文件 id 唯一性检查"""
    packages_dir = tmp_path / "packages"
    packages_dir.mkdir()

    # 创建两个有重复 id 的文件
    (packages_dir / "cn.yaml").write_text("""
packages:
  - id: firefox
    name: Firefox
""")
    (packages_dir / "intl.yaml").write_text("""
packages:
  - id: firefox
    name: Firefox International
  - id: chrome
    name: Chrome
""")

    errors = validate_cross_file_uniqueness(packages_dir)
    assert len(errors) == 1
    assert "firefox" in errors[0]
```

- [ ] **Step 5: 运行测试验证**

```bash
pytest tests/test_validate_config.py -v
```

Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add scripts/validate_config.py tests/test_validate_config.py
git commit -m "feat: add cross-file id uniqueness validation"
```

---

### Task 5.5: 清理旧的 packages.yaml

**Files:**
- Delete: `packages.yaml`

- [ ] **Step 1: 验证 sync 使用新目录**

```bash
python -m scripts.sync --only firefox,chrome
```

Expected: 成功同步（使用 packages/ 目录）

- [ ] **Step 2: 备份并删除旧文件**

```bash
# 备份（可选）
cp packages.yaml packages.yaml.bak

# 删除
rm packages.yaml
```

- [ ] **Step 3: 运行完整测试**

```bash
pytest
```

Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove legacy packages.yaml after migration"
```

---

## 改进项 6：前端构建管道

### Task 6.1: 创建 package.json 和构建脚本

**Files:**
- Create: `package.json`
- Create: `scripts/build_assets.mjs`

- [ ] **Step 1: 创建 package.json**

```json
{
  "name": "latest-softwares-web",
  "private": true,
  "devDependencies": {
    "esbuild": "0.24.0"
  },
  "scripts": {
    "build": "node scripts/build_assets.mjs"
  }
}
```

- [ ] **Step 2: 创建构建脚本**

```javascript
// scripts/build_assets.mjs
import { build } from 'esbuild';
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { createHash } from 'crypto';
import { join, basename } from 'path';

const WEB_DIR = 'web';
const DIST_DIR = 'web/dist';

// 确保 dist 目录存在
mkdirSync(DIST_DIR, { recursive: true });

// 读取源文件
const appJs = readFileSync(join(WEB_DIR, 'app.js'), 'utf-8');
const stylesCss = readFileSync(join(WEB_DIR, 'styles.css'), 'utf-8');

// 计算内容哈希
function contentHash(content) {
  return createHash('md5').update(content).digest('hex').slice(0, 8);
}

// 构建 JS
const jsResult = await build({
  stdin: {
    contents: appJs,
    loader: 'js',
  },
  bundle: false,
  minify: true,
  write: false,
});

const jsHash = contentHash(jsResult.outputFiles[0].text);
const jsFilename = `app.${jsHash}.js`;
writeFileSync(join(DIST_DIR, jsFilename), jsResult.outputFiles[0].text);

// 构建 CSS（简单 minification）
const minifiedCss = stylesCss
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/\s+/g, ' ')
  .replace(/\s*([{}:;,])\s*/g, '$1')
  .trim();

const cssHash = contentHash(minifiedCss);
const cssFilename = `styles.${cssHash}.css`;
writeFileSync(join(DIST_DIR, cssFilename), minifiedCss);

// 生成 asset manifest
const manifest = {
  'app.js': jsFilename,
  'styles.css': cssFilename,
};

writeFileSync(
  join(DIST_DIR, 'asset-manifest.json'),
  JSON.stringify(manifest, null, 2)
);

console.log('✓ Build complete:');
console.log(`  ${jsFilename} (${(jsResult.outputFiles[0].text.length / 1024).toFixed(1)}KB)`);
console.log(`  ${cssFilename} (${(minifiedCss.length / 1024).toFixed(1)}KB)`);
```

- [ ] **Step 3: 安装依赖并测试构建**

```bash
npm install
npm run build
```

Expected output:
```
✓ Build complete:
  app.XXXXXXXX.js (X.XKB)
  styles.XXXXXXXX.css (X.XKB)
```

- [ ] **Step 4: 验证构建产物**

```bash
ls -la web/dist/
cat web/dist/asset-manifest.json
```

Expected: 文件存在且 manifest 包含正确的哈希文件名

- [ ] **Step 5: Commit**

```bash
git add package.json package-lock.json scripts/build_assets.mjs
git commit -m "feat: add esbuild frontend build pipeline"
```

---

### Task 6.2: 集成构建到 build_web.py

**Files:**
- Modify: `scripts/build_web.py`

- [ ] **Step 1: 读取 build_web.py**

```bash
grep -n "def build" scripts/build_web.py
```

- [ ] **Step 2: 添加构建管道调用**

```python
# scripts/build_web.py
import subprocess
import json
from pathlib import Path

def run_frontend_build() -> dict[str, str] | None:
    """
    运行前端构建，返回 asset manifest

    Returns:
        Asset manifest 字典，如果构建失败返回 None
    """
    try:
        result = subprocess.run(
            ['npm', 'run', 'build'],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        if result.returncode != 0:
            print(f"⚠ 前端构建失败，使用原文件: {result.stderr}", file=sys.stderr)
            return None

        manifest_file = Path('web/dist/asset-manifest.json')
        if manifest_file.exists():
            return json.loads(manifest_file.read_text())
        return None
    except FileNotFoundError:
        print("⚠ Node.js 未安装，使用原文件", file=sys.stderr)
        return None
```

- [ ] **Step 3: 在生成 HTML 时使用 hashed 资源**

```python
# scripts/build_web.py
# 在生成 HTML 的函数中

def generate_html(edition: str, ...):
    # ... 现有代码 ...

    # 尝试获取 hashed 资源
    asset_manifest = run_frontend_build()

    if asset_manifest:
        app_js = f"dist/{asset_manifest['app.js']}"
        styles_css = f"dist/{asset_manifest['styles.css']}"
    else:
        app_js = "app.js"
        styles_css = "styles.css"

    # 在模板中使用
    # ... 渲染 HTML ...
```

- [ ] **Step 4: 运行测试验证无回归**

```bash
pytest tests/test_build_web.py -q
```

Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add scripts/build_web.py
git commit -m "feat: integrate frontend build pipeline into web generator"
```

---

### Task 6.3: 更新 CI 和 .gitignore

**Files:**
- Modify: `.github/workflows/sync.yml`
- Modify: `.gitignore`

- [ ] **Step 1: 在 sync.yml 的部署 job 添加 Node.js 步骤**

```yaml
# .github/workflows/sync.yml
# 在部署 job 中，在 Python 步骤之前添加

    - uses: actions/setup-node@v4
      with:
        node-version: '20'

    - name: Install Node dependencies
      run: npm ci

    - name: Build frontend assets
      run: npm run build
```

- [ ] **Step 2: 添加 web/dist/ 和 node_modules/ 到 .gitignore**

```bash
echo "" >> .gitignore
echo "# 前端构建产物和依赖" >> .gitignore
echo "web/dist/" >> .gitignore
echo "node_modules/" >> .gitignore
```

- [ ] **Step 3: 验证 .gitignore 更新**

```bash
tail -4 .gitignore
```

Expected:
```
# 前端构建产物和依赖
web/dist/
node_modules/
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/sync.yml .gitignore
git commit -m "ci: add Node.js build step to deployment workflow"
```

---

## 最终验证

### Task 7.1: 完整回归测试

- [ ] **Step 1: 运行完整测试套件**

```bash
pytest
```

Expected: All tests pass

- [ ] **Step 2: 运行类型检查**

```bash
python -m mypy
```

Expected: Success (核心文件)

- [ ] **Step 3: 运行 lint 检查**

```bash
python -m ruff check . && python -m ruff format --check .
```

Expected: All checks pass

- [ ] **Step 4: 测试 pre-commit（如已安装）**

```bash
pre-commit run --all-files
```

Expected: All hooks pass

- [ ] **Step 5: 端到端测试**

```bash
python -m scripts.sync --only firefox,chrome
python -m scripts.render
python scripts/build_web.py --edition intl
python scripts/build_web.py --edition cn
```

Expected: 所有步骤成功

- [ ] **Step 6: 验证前端构建**

```bash
npm run build
ls -la web/dist/
```

Expected: 构建产物存在

---

## 实施顺序总结

1. **改进项 1**: mypy 类型检查（Task 1.1 - 1.4）
2. **改进项 2**: Dependabot（Task 2.1）
3. **改进项 3**: 结构化错误日志（Task 3.1 - 3.3）
4. **改进项 4**: pre-commit hooks（Task 4.1 - 4.2）
5. **改进项 5**: packages.yaml 拆分（Task 5.1 - 5.5）
6. **改进项 6**: 前端构建管道（Task 6.1 - 6.3）
7. **最终验证**: 完整回归测试（Task 7.1）

每个改进项完成后应提交一个独立的 PR。
