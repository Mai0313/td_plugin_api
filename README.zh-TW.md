<div align="center" markdown="1">

# TD Plugin API

[![PyPI version](https://img.shields.io/pypi/v/td_plugin_api.svg)](https://pypi.org/project/td_plugin_api/) [![python](https://img.shields.io/badge/-Python_%7C_3.12%7C_3.13%7C_3.14-blue?logo=python&logoColor=white)](https://www.python.org/downloads/source/) [![uv](https://img.shields.io/badge/-uv_dependency_management-2C5F2D?logo=python&logoColor=white)](https://docs.astral.sh/uv/) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty) [![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://docs.pydantic.dev/latest/contributing/#badges) [![tests](https://github.com/Mai0313/td_plugin_api/actions/workflows/test.yml/badge.svg)](https://github.com/Mai0313/td_plugin_api/actions/workflows/test.yml) [![code-quality](https://github.com/Mai0313/td_plugin_api/actions/workflows/code-quality-check.yml/badge.svg)](https://github.com/Mai0313/td_plugin_api/actions/workflows/code-quality-check.yml) [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Mai0313/td_plugin_api) [![license](https://img.shields.io/badge/License-MIT-green.svg?labelColor=gray)](https://github.com/Mai0313/td_plugin_api/tree/main?tab=License-1-ov-file) [![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Mai0313/td_plugin_api/pulls) [![contributors](https://img.shields.io/github/contributors/Mai0313/td_plugin_api.svg)](https://github.com/Mai0313/td_plugin_api/graphs/contributors)

</div>

自架的 HTTP API，為多位使用者儲存並提供 tradingagents agent 外掛的紀錄（分析執行、判定、追蹤、結算與觀察清單）。分析本身留在外掛中；這個伺服器只負責保存資料。

API 的設計在 [DESIGN.md](https://github.com/Mai0313/td_plugin_api/blob/main/DESIGN.md)，尚未實作。目前服務只在 `/healthz` 回應健康檢查。

其他語言: [English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

## 🚀 快速開始

使用 Docker Compose，API 會發布在 `127.0.0.1:8700`（在 `.env` 設定 `TD_PLUGIN_API_PORT` 可更改）：

```bash
docker compose up -d --build
curl http://127.0.0.1:8700/healthz
```

或直接使用 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync
uv run td_plugin_api
```

除非 `TD_PLUGIN_API_HOST` 或 `TD_PLUGIN_API_PORT` 另有設定，伺服器會監聽 `127.0.0.1:8700`。

## 🤝 貢獻

開發環境、常用指令、CI 與發佈流程請見 [CONTRIBUTING.md](https://github.com/Mai0313/td_plugin_api/blob/main/.github/CONTRIBUTING.md)。

## 📄 授權

MIT — 詳見 `LICENSE`。
