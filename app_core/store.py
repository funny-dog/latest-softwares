"""统计计数的存储后端策略。

两版后端唯一的本质差异就在这里:
  - JsonFileMetricsStore  —— 国内版,JSON 文件(阿里云 VPS 持久磁盘 + 单实例)
  - SqlMetricsStore       —— 国际版,本地 SQLite 或远程 Turso/libSQL(serverless)

端点逻辑(app_factory)只依赖 MetricsStore 的三个方法,完全不关心底层是文件还是
数据库、是本地还是远程。要新增一种存储,实现这三个方法即可。
"""

from __future__ import annotations

import abc
import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app_core.metrics import empty_metrics, utc_now_iso


class MetricsStore(abc.ABC):
    """访问/下载计数存储后端的抽象接口。

    子类需提供 scope/storage 两个属性(写入 metrics 骨架,如实反映存储语义)
    及下面三个方法。
    """

    #: 统计范围标签:单实例本地 or 全局共享
    scope: str = "instance-local"
    #: 存储介质标签
    storage: str = "unknown"

    @abc.abstractmethod
    def load(self) -> dict[str, Any]:
        """返回完整 metrics 字典(schema 见 metrics.empty_metrics)。"""

    @abc.abstractmethod
    def increment_visit(self, path: str) -> None:
        """页面访问计数 +1(总量 + 按路径)。"""

    @abc.abstractmethod
    def increment_download(self, package_id: str, platform: str) -> None:
        """下载点击计数 +1(总量 + 按包 + 按平台 + 按 asset)。"""


class JsonFileMetricsStore(MetricsStore):
    """JSON 文件存储(国内版 / 阿里云 VPS)。

    文件路径应放在【部署目录之外】(如 /var/lib/latest-softwares/metrics.json),
    这样 rsync --delete 重新部署代码时不会清掉统计数据。VPS 单实例常驻 +
    进程内 Lock 即可保证一致性。
    """

    scope = "instance-local"
    storage = "persistent-file"

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def load(self) -> dict[str, Any]:
        metrics = empty_metrics(self.scope, self.storage)
        if not self.path.exists():
            return metrics
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return metrics
        metrics.update({key: data.get(key, metrics[key]) for key in metrics})
        metrics["visits"].setdefault("total", 0)
        metrics["visits"].setdefault("paths", {})
        metrics["downloads"].setdefault("total", 0)
        metrics["downloads"].setdefault("packages", {})
        metrics["downloads"].setdefault("platforms", {})
        metrics["downloads"].setdefault("assets", {})
        return metrics

    def _write(self, metrics: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def increment_visit(self, path: str) -> None:
        with self._lock:
            metrics = self.load()
            metrics["visits"]["total"] += 1
            paths = metrics["visits"]["paths"]
            paths[path] = paths.get(path, 0) + 1
            metrics["updated_at"] = utc_now_iso()
            self._write(metrics)

    def increment_download(self, package_id: str, platform: str) -> None:
        asset_key = f"{package_id}:{platform}"
        with self._lock:
            metrics = self.load()
            downloads = metrics["downloads"]
            downloads["total"] += 1
            downloads["packages"][package_id] = (
                downloads["packages"].get(package_id, 0) + 1
            )
            downloads["platforms"][platform] = (
                downloads["platforms"].get(platform, 0) + 1
            )
            downloads["assets"][asset_key] = downloads["assets"].get(asset_key, 0) + 1
            metrics["updated_at"] = utc_now_iso()
            self._write(metrics)


class SqlMetricsStore(MetricsStore):
    """SQLite / libSQL(Turso) 存储(国际版 / FastAPI Cloud)。

    serverless 容器的本地文件系统是临时的(冷启动清空、多实例各持一份),本地
    SQLite 无法持久。配置 turso_url + turso_auth_token 后写远程 libSQL(跨实例
    持久);否则回退本地 SQLite(本地开发 / pytest / CI)。

    libsql 为【延迟导入】——未配 Turso 时无需安装该依赖(国内版环境就不装)。
    """

    def __init__(
        self,
        *,
        db_path: Path | str,
        turso_url: str = "",
        turso_auth_token: str = "",
    ) -> None:
        self.db_path = Path(db_path)
        self.turso_url = (turso_url or "").strip()
        self.turso_auth_token = (turso_auth_token or "").strip()
        self._lock = threading.Lock()
        # 按目标缓存已建表,避免每个请求重复 CREATE TABLE(远程 libSQL 下每条语句
        # 都是一次 HTTP 往返)。键含 db_path/turso_url,测试切换库时会重新建表。
        self._initialized_targets: set[str] = set()

    @classmethod
    def from_env(cls, *, db_path: Path | str) -> "SqlMetricsStore":
        """从 TURSO_DATABASE_URL / TURSO_AUTH_TOKEN 环境变量装配。"""
        return cls(
            db_path=db_path,
            turso_url=os.environ.get("TURSO_DATABASE_URL", ""),
            turso_auth_token=os.environ.get("TURSO_AUTH_TOKEN", ""),
        )

    @property
    def _remote(self) -> bool:
        return bool(self.turso_url)

    @property
    def scope(self) -> str:  # type: ignore[override]
        return "global" if self._remote else "instance-local"

    @property
    def storage(self) -> str:  # type: ignore[override]
        return "turso-libsql" if self._remote else "local-sqlite"

    def _connect(self) -> Any:
        """返回 DBAPI 连接:配了 Turso 走远程 libSQL,否则本地 SQLite。

        libsql 的 API 与 sqlite3 基本一致(execute / fetchone / commit / close),
        但有差异:游标不可直接迭代,遍历查询必须 .fetchall()(见 load)。
        """
        if self._remote:
            import libsql  # 延迟导入:不连远程时无需安装该依赖

            return libsql.connect(self.turso_url, auth_token=self.turso_auth_token)
        return sqlite3.connect(str(self.db_path))

    def _init_db(self) -> None:
        target = self.turso_url or str(self.db_path)
        if target in self._initialized_targets:
            return
        if not self._remote:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connect()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metrics (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS visits (
                path TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS downloads (
                package_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (package_id, platform)
            )
            """
        )
        conn.commit()
        conn.close()
        self._initialized_targets.add(target)

    def load(self) -> dict[str, Any]:
        self._init_db()
        conn = self._connect()
        metrics = empty_metrics(self.scope, self.storage)

        row = conn.execute(
            "SELECT value FROM metrics WHERE key = 'visits_total'"
        ).fetchone()
        metrics["visits"]["total"] = int(row[0]) if row else 0

        # 必须 .fetchall():libsql 的 Cursor 不可直接迭代(sqlite3 可以),
        # fetchall() 对两者都返回 list。
        for path, count in conn.execute(
            "SELECT path, count FROM visits"
        ).fetchall():
            metrics["visits"]["paths"][path] = count

        row = conn.execute(
            "SELECT value FROM metrics WHERE key = 'downloads_total'"
        ).fetchone()
        metrics["downloads"]["total"] = int(row[0]) if row else 0

        packages: dict[str, int] = {}
        platforms: dict[str, int] = {}
        assets: dict[str, int] = {}
        for package_id, platform, count in conn.execute(
            "SELECT package_id, platform, count FROM downloads"
        ).fetchall():
            assets[f"{package_id}:{platform}"] = count
            packages[package_id] = packages.get(package_id, 0) + count
            platforms[platform] = platforms.get(platform, 0) + count
        metrics["downloads"]["packages"] = packages
        metrics["downloads"]["platforms"] = platforms
        metrics["downloads"]["assets"] = assets

        row = conn.execute(
            "SELECT value FROM metrics WHERE key = 'updated_at'"
        ).fetchone()
        metrics["updated_at"] = row[0] if row else None

        conn.close()
        return metrics

    def increment_visit(self, path: str) -> None:
        with self._lock:
            self._init_db()
            conn = self._connect()
            conn.execute(
                """
                INSERT INTO metrics (key, value) VALUES ('visits_total', '1')
                ON CONFLICT(key)
                DO UPDATE SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
                """
            )
            conn.execute(
                """
                INSERT INTO visits (path, count) VALUES (?, 1)
                ON CONFLICT(path) DO UPDATE SET count = count + 1
                """,
                (path,),
            )
            now = utc_now_iso()
            conn.execute(
                """
                INSERT INTO metrics (key, value) VALUES ('updated_at', ?)
                ON CONFLICT(key) DO UPDATE SET value = ?
                """,
                (now, now),
            )
            conn.commit()
            conn.close()

    def increment_download(self, package_id: str, platform: str) -> None:
        with self._lock:
            self._init_db()
            conn = self._connect()
            conn.execute(
                """
                INSERT INTO metrics (key, value) VALUES ('downloads_total', '1')
                ON CONFLICT(key)
                DO UPDATE SET value = CAST(CAST(value AS INTEGER) + 1 AS TEXT)
                """
            )
            conn.execute(
                """
                INSERT INTO downloads (package_id, platform, count) VALUES (?, ?, 1)
                ON CONFLICT(package_id, platform) DO UPDATE SET count = count + 1
                """,
                (package_id, platform),
            )
            now = utc_now_iso()
            conn.execute(
                """
                INSERT INTO metrics (key, value) VALUES ('updated_at', ?)
                ON CONFLICT(key) DO UPDATE SET value = ?
                """,
                (now, now),
            )
            conn.commit()
            conn.close()

    def seed_if_empty(self, seed_file: Path | str) -> None:
        """库为空时,从 JSON 种子文件初始化计数。

        国际版历史 workaround(serverless 上 SQLite 不持久,靠部署时抓取 live
        指标种子回填)。接入 Turso 持久化后基本是 no-op(库非空即跳过),保留以
        兼容部署管道。
        """
        seed_file = Path(seed_file)
        if not seed_file.exists():
            return
        try:
            seed = json.loads(seed_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not seed.get("visits") and not seed.get("downloads"):
            return
        self._init_db()
        conn = self._connect()
        row = conn.execute(
            "SELECT value FROM metrics WHERE key = 'visits_total'"
        ).fetchone()
        if row is not None and int(row[0]) > 0:
            conn.close()
            return
        visits_total = seed.get("visits", {}).get("total", 0)
        if visits_total:
            conn.execute(
                "INSERT INTO metrics (key, value) VALUES ('visits_total', ?)",
                (str(visits_total),),
            )
        for path, count in seed.get("visits", {}).get("paths", {}).items():
            if count:
                conn.execute(
                    "INSERT INTO visits (path, count) VALUES (?, ?)", (path, count)
                )
        downloads_total = seed.get("downloads", {}).get("total", 0)
        if downloads_total:
            conn.execute(
                "INSERT INTO metrics (key, value) VALUES ('downloads_total', ?)",
                (str(downloads_total),),
            )
        for asset_key, count in seed.get("downloads", {}).get("assets", {}).items():
            if ":" in asset_key and count:
                package_id, platform = asset_key.split(":", 1)
                conn.execute(
                    "INSERT INTO downloads (package_id, platform, count) "
                    "VALUES (?, ?, ?)",
                    (package_id, platform, count),
                )
        updated_at = seed.get("updated_at")
        if updated_at:
            conn.execute(
                "INSERT INTO metrics (key, value) VALUES ('updated_at', ?)",
                (updated_at,),
            )
        conn.commit()
        conn.close()
