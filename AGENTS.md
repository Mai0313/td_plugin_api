# td_plugin_api

A self-hosted HTTP API that stores and serves the records of the tradingagents agent plugin (analysis runs, rulings, follow-ups, settlements and watchlists) for several users. It runs under Docker Compose on the owner's machine, later behind nginx and Cloudflare.

- The server only stores and serves data. Analysis logic stays in the plugin; do not move any of it here.
- The API, storage schema and auth are designed with the owner before they are written. Do not add data endpoints, database models or auth on your own.
- The repository is public. Data the server receives lives in `data/` and secrets in `.env`, both gitignored; never commit either, and never put real records in tests or fixtures.
- The scaffold (workflows, pre-commit, Makefile, Dockerfile) comes from `Mai0313/repo_template`. Keep it aligned with the template rather than restructuring it here.
