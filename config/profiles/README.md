# 部署 Profile(config/profiles/)

每个 `<name>.json` 描述一个部署目标的装配差异,由 `app_core/app_builder.py` 的
`build_app("<name>")` 读取。新增部署目标 = 加一份 JSON + 把进程的 `APP_PROFILE`
设为该名字 + 入口指向 `app:app`,无需写新的 Python。

用 JSON 而非 TOML/YAML:国内版后端运行环境只装了 fastapi+uvicorn,配置解析必须
stdlib-only,JSON 是唯一「全 Python 版本兼容 + 公认配置格式」的选择。

## 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `edition` | string | `cn` / `intl`,决定包数据过滤 |
| `title` | string | FastAPI app 标题 |
| `description` | string | FastAPI app 描述 |
| `data_file` | string | 包数据路径(相对仓库根;可被 `LATEST_SOFTWARES_DATA_FILE` 覆盖) |
| `serve_static` | bool | 是否挂载 `dist/`(intl 自挂;cn 由 nginx 服务,填 false) |
| `packages_endpoint` | bool | 是否暴露 `/api/packages`(目前仅 intl) |
| `log_events` | bool | 是否打结构化事件日志(给日志平台采集) |
| `store.type` | string | `json_file` / `sql`,见下 |

### `store.type = "json_file"`(cn)
- `metrics_file`:统计文件路径(可被 `LATEST_SOFTWARES_METRICS_FILE` 覆盖)。
  放在部署目录之外(如 `/var/lib/...`),避免 rsync --delete 清掉。

### `store.type = "sql"`(intl)
- `db_path`:本地 SQLite 路径(可被 `LATEST_SOFTWARES_STATS_DB` 覆盖)。
- `seed_file`:可选;存在则启用 lifespan 启动回填(库为空时)。
- 远程 Turso 的 `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` 是 **secret,只走环境
  变量,绝不写进本文件**。

## 路径约定
相对路径相对仓库根解析;绝对路径原样使用。
