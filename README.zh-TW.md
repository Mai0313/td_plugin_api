<div align="center" markdown="1">

# TD Plugin API

[![PyPI version](https://img.shields.io/pypi/v/td_plugin_api.svg)](https://pypi.org/project/td_plugin_api/) [![python](https://img.shields.io/badge/-Python_%7C_3.12%7C_3.13%7C_3.14-blue?logo=python&logoColor=white)](https://www.python.org/downloads/source/) [![uv](https://img.shields.io/badge/-uv_dependency_management-2C5F2D?logo=python&logoColor=white)](https://docs.astral.sh/uv/) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty) [![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://docs.pydantic.dev/latest/contributing/#badges) [![tests](https://github.com/Mai0313/td_plugin_api/actions/workflows/test.yml/badge.svg)](https://github.com/Mai0313/td_plugin_api/actions/workflows/test.yml) [![code-quality](https://github.com/Mai0313/td_plugin_api/actions/workflows/code-quality-check.yml/badge.svg)](https://github.com/Mai0313/td_plugin_api/actions/workflows/code-quality-check.yml) [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Mai0313/td_plugin_api) [![license](https://img.shields.io/badge/License-MIT-green.svg?labelColor=gray)](https://github.com/Mai0313/td_plugin_api/tree/main?tab=License-1-ov-file) [![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Mai0313/td_plugin_api/pulls) [![contributors](https://img.shields.io/github/contributors/Mai0313/td_plugin_api.svg)](https://github.com/Mai0313/td_plugin_api/graphs/contributors)

</div>

自架的 HTTP API，為多位使用者儲存並提供 tradingagents agent 外掛的紀錄（分析執行、判定、追蹤、結算與觀察清單）。分析本身留在外掛中；這個伺服器只負責保存資料。

[DESIGN.md](https://github.com/Mai0313/td_plugin_api/blob/main/DESIGN.md) 說明每個 endpoint，伺服器執行時也會在 `/docs` 提供自動產生的參考文件。

其他語言: [English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

## 🚀 快速開始

使用 Docker Compose，會在 API 旁一起執行 PostgreSQL，API 發布在 `127.0.0.1:8700`（在 `.env` 設定 `TD_PLUGIN_API_PORT` 可更改）。請先在 `.env` 設定 `POSTGRES_PASSWORD`（參考 `.env.example`）：

```bash
docker compose up -d --build
curl http://127.0.0.1:8700/healthz
```

沒有註冊流程。先建立使用者，再為每台機器或讀取端建立 token；token 只會顯示一次：

```bash
docker compose exec app uv run td_plugin_api admin create-user wei --role owner
docker compose exec app uv run td_plugin_api admin create-token wei --name desk --machine 59a937828f3c
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8700/v1/me
```

只需要讀取的讀取端加上 `--scopes read`，`admin revoke-token <id>` 可停用 token。

或直接使用 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync
uv run td_plugin_api
```

除非 `TD_PLUGIN_API_HOST` 或 `TD_PLUGIN_API_PORT` 另有設定，伺服器會監聽 `127.0.0.1:8700`；除非 `TD_PLUGIN_API_DATABASE_URL` 指定其他資料庫，資料會存在 `data/` 下的 SQLite 檔案。

## 🤝 貢獻

開發環境、常用指令、CI 與發佈流程請見 [CONTRIBUTING.md](https://github.com/Mai0313/td_plugin_api/blob/main/.github/CONTRIBUTING.md)。

## 📄 授權

MIT — 詳見 `LICENSE`。
