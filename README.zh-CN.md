<div align="center" markdown="1">

# TD Plugin API

[![PyPI version](https://img.shields.io/pypi/v/td_plugin_api.svg)](https://pypi.org/project/td_plugin_api/) [![python](https://img.shields.io/badge/-Python_%7C_3.12%7C_3.13%7C_3.14-blue?logo=python&logoColor=white)](https://www.python.org/downloads/source/) [![uv](https://img.shields.io/badge/-uv_dependency_management-2C5F2D?logo=python&logoColor=white)](https://docs.astral.sh/uv/) [![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![ty](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json)](https://github.com/astral-sh/ty) [![Pydantic v2](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/pydantic/pydantic/main/docs/badge/v2.json)](https://docs.pydantic.dev/latest/contributing/#badges) [![tests](https://github.com/Mai0313/td_plugin_api/actions/workflows/test.yml/badge.svg)](https://github.com/Mai0313/td_plugin_api/actions/workflows/test.yml) [![code-quality](https://github.com/Mai0313/td_plugin_api/actions/workflows/code-quality-check.yml/badge.svg)](https://github.com/Mai0313/td_plugin_api/actions/workflows/code-quality-check.yml) [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Mai0313/td_plugin_api) [![license](https://img.shields.io/badge/License-MIT-green.svg?labelColor=gray)](https://github.com/Mai0313/td_plugin_api/tree/main?tab=License-1-ov-file) [![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/Mai0313/td_plugin_api/pulls) [![contributors](https://img.shields.io/github/contributors/Mai0313/td_plugin_api.svg)](https://github.com/Mai0313/td_plugin_api/graphs/contributors)

</div>

自托管的 HTTP API，为多位用户存储并提供 tradingagents agent 插件的记录（分析运行、判定、跟进、结算与观察列表）。分析本身留在插件中；这个服务器只负责保存数据。

[DESIGN.md](https://github.com/Mai0313/td_plugin_api/blob/main/DESIGN.md) 说明每个 endpoint，服务器运行时也会在 `/docs` 提供自动生成的参考文档。

其他语言: [English](README.md) | [繁體中文](README.zh-TW.md) | [简体中文](README.zh-CN.md)

## 🚀 快速开始

使用 Docker Compose，会在 API 旁一起运行 PostgreSQL，API 发布在 `127.0.0.1:8700`（在 `.env` 设置 `TD_PLUGIN_API_PORT` 可更改）。请先在 `.env` 设置 `POSTGRES_PASSWORD`（参考 `.env.example`）：

```bash
docker compose up -d --build
curl http://127.0.0.1:8700/healthz
```

没有注册流程。先创建用户，再为每台机器或读取端创建 token；token 只会显示一次：

```bash
docker compose exec app uv run td_plugin_api admin create-user wei --role owner
docker compose exec app uv run td_plugin_api admin create-token wei --name desk --machine 59a937828f3c
curl -H "Authorization: Bearer <token>" http://127.0.0.1:8700/v1/me
```

只需要读取的读取端加上 `--scopes read`，`admin revoke-token <id>` 可停用 token。

或直接使用 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync
uv run td_plugin_api
```

除非 `TD_PLUGIN_API_HOST` 或 `TD_PLUGIN_API_PORT` 另有设置，服务器会监听 `127.0.0.1:8700`；除非 `TD_PLUGIN_API_DATABASE_URL` 指定其他数据库，数据会存在 `data/` 下的 SQLite 文件。

## 🤝 贡献

开发环境、常用命令、CI 与发布流程请参阅 [CONTRIBUTING.md](https://github.com/Mai0313/td_plugin_api/blob/main/.github/CONTRIBUTING.md)。

## 📄 授权

MIT — 详见 `LICENSE`。
