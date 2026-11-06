import os
import argparse

import uvicorn

from td_plugin_api.db import database_url, open_database
from td_plugin_api.app import app
from td_plugin_api.auth import SCOPES, create_user, create_token, revoke_token


def main(argv: list[str] | None = None) -> None:
    """Serves the API on `TD_PLUGIN_API_HOST` and `TD_PLUGIN_API_PORT`, or runs an `admin` command."""
    parser = argparse.ArgumentParser(prog="td_plugin_api")
    commands = parser.add_subparsers(dest="command")
    admin = commands.add_parser("admin", help="manage users and tokens").add_subparsers(
        dest="action", required=True
    )
    user = admin.add_parser("create-user", help="add a user")
    user.add_argument("handle")
    user.add_argument("--display-name", default="")
    user.add_argument("--role", choices=["owner", "member"], default="member")
    token = admin.add_parser(
        "create-token", help="make a token for a user and print its ID and the token, once"
    )
    token.add_argument("handle")
    token.add_argument("--name", required=True, help="what the token is for, such as a machine")
    token.add_argument(
        "--scopes", default="read,write", help=f"comma-separated: {', '.join(SCOPES)}"
    )
    token.add_argument("--machine", help="the machine ID the token belongs to")
    revoke = admin.add_parser("revoke-token", help="stop a token from working")
    revoke.add_argument("id", type=int)
    args = parser.parse_args(argv)

    if args.command is None:
        uvicorn.run(
            app,
            host=os.getenv("TD_PLUGIN_API_HOST", "127.0.0.1"),
            port=int(os.getenv("TD_PLUGIN_API_PORT", "8700")),
        )
        return
    engine, sessions = open_database(database_url())
    try:
        with sessions() as session:
            if args.action == "create-user":
                created = create_user(session, args.handle, args.display_name, args.role)
                print(f"created user {created.handle} ({created.role})")  # noqa: T201
            elif args.action == "create-token":
                token_id, secret = create_token(
                    session, args.handle, args.name, args.scopes, args.machine
                )
                print(f"token {token_id}: {secret}")  # noqa: T201
            else:
                revoke_token(session, args.id)
                print(f"revoked token {args.id}")  # noqa: T201
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
