"""Administrative CLI for M11 identity bootstrap and customer grants."""

from __future__ import annotations

import argparse
import getpass
import os

from omni_healthcheck.auth import AuthStore


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="omni-healthcheck-auth")
    root.add_argument("--database-url", default=os.environ.get("OMNICHECK_DATABASE_URL"))
    commands = root.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user")
    create.add_argument("--username", required=True)
    create.add_argument("--display-name", required=True)
    create.add_argument("--platform-admin", action="store_true")
    grant = commands.add_parser("grant-customer")
    grant.add_argument("--user-id", required=True)
    grant.add_argument("--customer-id", required=True)
    grant.add_argument("--role", choices=["engineer", "reviewer", "viewer"], required=True)
    return root


def main() -> None:
    args = parser().parse_args()
    if not args.database_url:
        raise SystemExit("OMNICHECK_DATABASE_URL or --database-url is required")
    store = AuthStore(args.database_url)
    if args.command == "create-user":
        password = getpass.getpass("Password (minimum 12 characters): ")
        confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            raise SystemExit("passwords do not match")
        user = store.create_user(username=args.username, display_name=args.display_name,
                                 password=password,
                                 platform_role="platform_admin" if args.platform_admin else None)
        print(f"created user {user['username']} ({user['user_id']})")
    elif args.command == "grant-customer":
        grant = store.grant_customer(args.user_id, args.customer_id, args.role)
        print(f"granted {grant['role']} on {grant['customer_id']} to {grant['user_id']}")


if __name__ == "__main__":
    main()
