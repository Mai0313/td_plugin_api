# td_plugin_api

A self-hosted HTTP API that stores and serves the records of the tradingagents agent plugin (analysis runs, rulings, follow-ups, settlements and watchlists) for several users. It runs under Docker Compose on the owner's machine, later behind nginx and Cloudflare.

- The server only stores and serves data. Analysis logic stays in the plugin; do not move any of it here.
- `DESIGN.md` is the API, storage and auth design agreed with the owner. Build from it; a change to the design is agreed with the owner first and lands in `DESIGN.md` in the same change.
- The repository is public. Data the server receives lives in `data/` and secrets in `.env`, both gitignored; never commit either, and never put real records in tests or fixtures.
- The scaffold (workflows, pre-commit, Makefile, Dockerfile) comes from `Mai0313/repo_template`. Keep it aligned with the template rather than restructuring it here.
