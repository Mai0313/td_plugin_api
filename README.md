<div align="center" markdown="1">

# TD Plugin API

[![PyPI version](https://img.shields.io/pypi/v/td_plugin_api.svg)](https://pypi.org/project/td_plugin_api/) [![python](https://img.shields.io/badge/-Python_%7C_3.12%7C_3.13%7C_3.14-blue?logo=python&logoColor=white)](https://www.python.org/downloads/source/) [![uv](https://img.shields.io/badge/-uv_dependency_management-2C5F2D?logo=python&logoColor=white)](https://docs.astral.sh/uv/) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty) [![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://docs.pydantic.dev/latest/contributing/#badges) [![tests](https://github.com/Mai0313/td_plugin_api/actions/workflows/test.yml/badge.svg)](https://github.com/Mai0313/td_plugin_api/actions/workflows/test.yml) [![code-quality](https://github.com/Mai0313/td_plugin_api/actions/workflows/code-quality-check.yml/badge.svg)](https://github.com/Mai0313/td_plugin_api/actions/workflows/code-quality-check.yml) [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Mai0313/td_plugin_api) [![license](https://img.shields.io/badge/License-MIT-green.svg?labelColor=gray)](https://github.com/Mai0313/td_plugin_api/tree/main?tab=License-1-ov-file) [![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Mai0313/td_plugin_api/pulls) [![contributors](https://img.shields.io/github/contributors/Mai0313/td_plugin_api.svg)](https://github.com/Mai0313/td_plugin_api/graphs/contributors)

</div>

A self-hosted HTTP API that stores and serves the records of the tradingagents agent plugin (analysis runs, rulings, follow-ups, settlements and watchlists) for several users. The analysis itself stays in the plugin; this server only keeps the data.

The API is designed in [DESIGN.md](https://github.com/Mai0313/td_plugin_api/blob/main/DESIGN.md) but not built yet. For now the service only answers a health check at `/healthz`.

Other Languages: [English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

## 🚀 Quick Start

With Docker Compose, which publishes the API on `127.0.0.1:8700` (set `TD_PLUGIN_API_PORT` in `.env` to change it):

```bash
docker compose up -d --build
curl http://127.0.0.1:8700/healthz
```

Or directly with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run td_plugin_api
```

The server listens on `127.0.0.1:8700` unless `TD_PLUGIN_API_HOST` or `TD_PLUGIN_API_PORT` says otherwise.

## 🤝 Contributing

Development setup, commands, CI and releases are in [CONTRIBUTING.md](https://github.com/Mai0313/td_plugin_api/blob/main/.github/CONTRIBUTING.md).

## 📄 License

MIT — see `LICENSE`.
