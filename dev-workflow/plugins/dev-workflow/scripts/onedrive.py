#!/usr/bin/env python3
"""OneDrive / SharePoint CLI for the project's configured folders (Microsoft Graph or a locally synced folder).

Usage (through the wrapper):
    dw onedrive login | logout | whoami
    dw onedrive folders [--check]
    dw onedrive discover
    dw onedrive ls <alias>:[path] [--json]
    dw onedrive mkdir <alias>:<path> [--dry-run]
    dw onedrive put <local-file> <alias>:<path> [--overwrite] [--mkdir] [--dry-run]
    dw onedrive get <alias>:<path> [--out FILE]

Folders come from `[onedrive].folders` in `.claude/dev-workflow.toml` (alias -> sharing URL for Graph,
or `~/...` / `/...` path of a folder synced by the OneDrive app for the local backend).
Exit codes: 0 ok, 1 Graph, network or local file error or conflict, 2 usage/config error or not signed in.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from dw_config import ConfigError, resolve_config
from od_auth import AuthError, Session, device_code_login, open_token_store
from od_graph import STATUS_CONFLICT, GraphClient, GraphError, UploadPlan, file_size, is_folder
from od_local import BackendKind, LocalClient, backend_kind, discover_roots, local_root
from od_http import NetworkError, Transport, urllib_transport
from od_paths import PathError, RemotePath, parse_remote

EXIT_OK = 0
EXIT_REMOTE_ERROR = 1
EXIT_USAGE = 2
PROG = "dw onedrive"
SETUP_HINT = (
    "set [onedrive].client_id in .claude/dev-workflow.toml: register a public client app in Microsoft Entra ID "
    "with 'Allow public client flows' (device code) and delegated permission Files.ReadWrite.All, "
    "or use the app ID your company provides"
)
OVERWRITE_HINT = "already exists; pass --overwrite to replace it"
LIST_FIELD_SEPARATOR = "\t"
KIND_DIR, KIND_FILE, KIND_ROOT = "d", "f", "root"
EXISTS, MISSING = "exists", "missing"


class UsageError(Exception):
    """Bad arguments or missing configuration (exit 2)."""


@dataclass
class OneDriveSettings:
    client_id: str
    tenant: str
    folders: dict[str, str]


@dataclass
class Context:
    settings: OneDriveSettings
    transport: Transport
    sleep: Callable[[float], None]
    _session: Session | None = None
    _client: GraphClient | None = None
    _local: LocalClient | None = None

    def session(self) -> Session:
        if not self.settings.client_id:
            raise UsageError(SETUP_HINT)
        if self._session is None:
            store = open_token_store(self.settings.tenant, self.settings.client_id)
            self._session = Session(self.transport, self.settings.tenant, self.settings.client_id, store, self.sleep)
        return self._session

    def client(self) -> GraphClient:
        if self._client is None:
            session = self.session()
            self._client = GraphClient(self.transport, session.access_token, self.settings.folders, self.sleep)
        return self._client

    def is_local(self, alias: str) -> bool:
        return backend_kind(self.settings.folders[alias]) == BackendKind.LOCAL

    def client_for(self, alias: str) -> GraphClient | LocalClient:
        if not self.is_local(alias):
            return self.client()
        if self._local is None:
            self._local = LocalClient(self.settings.folders)
        return self._local

    def remote(self, spec: str) -> RemotePath:
        return parse_remote(spec, self.settings.folders)


def load_settings(config_path: str | None) -> OneDriveSettings:
    config = resolve_config(config_path)
    section = config.data["onedrive"]
    folders = {alias: str(value) for alias, value in dict(section["folders"]).items()}
    for alias, value in folders.items():
        if backend_kind(value) is None:
            raise UsageError(f"[onedrive].folders.{alias} must be an https:// sharing URL or a ~/ or / path "
                             f"of a synced folder, got '{value}'")
    return OneDriveSettings(section["client_id"], section["tenant"] or "organizations", folders)


# --- commands ------------------------------------------------------------------------------
def cmd_login(ctx: Context, args: argparse.Namespace) -> int:
    session = ctx.session()
    session.adopt(device_code_login(ctx.transport, ctx.settings.tenant, ctx.settings.client_id, sleep=ctx.sleep))
    print(f"signed in as {ctx.client().me().get('userPrincipalName', '?')}")
    return EXIT_OK


def cmd_logout(ctx: Context, args: argparse.Namespace) -> int:
    removed = ctx.session().store.delete()
    print("signed out" if removed else "no stored sign-in")
    return EXIT_OK


def cmd_whoami(ctx: Context, args: argparse.Namespace) -> int:
    print(ctx.client().me().get("userPrincipalName", "?"))
    return EXIT_OK


def cmd_folders(ctx: Context, args: argparse.Namespace) -> int:
    if not ctx.settings.folders:
        print("no folders configured in [onedrive].folders", file=sys.stderr)
        return EXIT_OK
    sep = LIST_FIELD_SEPARATOR
    for alias, value in sorted(ctx.settings.folders.items()):
        kind = backend_kind(value)
        if not args.check:
            print(f"{alias}{sep}{kind}{sep}{value}")
            continue
        if kind == BackendKind.LOCAL:
            path = local_root(value)
            print(f"{alias}{sep}{kind}{sep}{path}{sep}{EXISTS if path.is_dir() else MISSING}")
            continue
        root = ctx.client().root(alias)
        print(f"{alias}{LIST_FIELD_SEPARATOR}{root.name}{LIST_FIELD_SEPARATOR}{root.web_url}")
    return EXIT_OK


def cmd_discover(ctx: Context, args: argparse.Namespace) -> int:
    roots = discover_roots()
    if not roots:
        print("no OneDrive sync folder found; install and sign in to the OneDrive app first", file=sys.stderr)
        return EXIT_OK
    for root, children in roots:
        print(f"{KIND_ROOT}{LIST_FIELD_SEPARATOR}{root}")
        for child in children:
            print(f"{KIND_DIR}{LIST_FIELD_SEPARATOR}{child}")
    return EXIT_OK


def _list_line(item: dict[str, Any]) -> str:
    kind = KIND_DIR if is_folder(item) else KIND_FILE
    fields = [kind, item.get("name", ""), str(item.get("size", "")), item.get("lastModifiedDateTime", "")]
    return LIST_FIELD_SEPARATOR.join(fields)


def cmd_ls(ctx: Context, args: argparse.Namespace) -> int:
    target = ctx.remote(args.remote)
    items = ctx.client_for(target.alias).list_children(target)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return EXIT_OK
    for item in items:
        print(_list_line(item))
    return EXIT_OK


def cmd_mkdir(ctx: Context, args: argparse.Namespace) -> int:
    target = ctx.remote(args.remote)
    if not target.parts:
        raise UsageError("mkdir needs a path below the alias folder")
    if args.dry_run:
        print(f"dry-run: mkdir -p {target.display()} (alias {target.alias}, {len(target.parts)} level(s))")
        return EXIT_OK
    print(ctx.client_for(target.alias).mkdir(target).get("webUrl", ""))
    return EXIT_OK


def cmd_put(ctx: Context, args: argparse.Namespace) -> int:
    local = Path(args.local)
    if not local.is_file():
        raise UsageError(f"local file not found: {local}")
    target, size = ctx.remote(args.remote), file_size(local)
    if args.dry_run:
        shown = target.child(local.name) if target.trailing_slash or not target.parts else target
        mode = "overwrite" if args.overwrite else "no overwrite"
        note = "; parent folders created" if args.mkdir else ""
        print(f"dry-run: put {local} -> {shown.display()} ({size} bytes, alias {target.alias}, {mode}{note}; "
              "file name is appended if the target is an existing folder)")
        return EXIT_OK
    client = ctx.client_for(target.alias)
    if args.mkdir and target.parts and not target.trailing_slash:
        client.mkdir(target.parent())
    elif args.mkdir and target.parts:
        client.mkdir(target)
    final = client.resolve_upload_target(local, target)
    try:
        item = client.upload(UploadPlan(local, size, final, args.overwrite))
    except GraphError as exc:
        if exc.status == STATUS_CONFLICT and not args.overwrite:
            raise GraphError(exc.status, exc.code, f"{final.display()} {OVERWRITE_HINT}") from exc
        raise
    print(f"{item.get('name', final.parts[-1])}{LIST_FIELD_SEPARATOR}{item.get('size', size)}"
          f"{LIST_FIELD_SEPARATOR}{item.get('webUrl', '')}")
    return EXIT_OK


def cmd_get(ctx: Context, args: argparse.Namespace) -> int:
    source = ctx.remote(args.remote)
    if not source.parts:
        raise UsageError("get needs a file path below the alias folder")
    client = ctx.client_for(source.alias)
    if args.out:
        with open(args.out, "wb") as sink:
            written = client.download(source, sink)
        print(f"{args.out}{LIST_FIELD_SEPARATOR}{written} bytes", file=sys.stderr)
        return EXIT_OK
    client.download(source, sys.stdout.buffer)
    sys.stdout.buffer.flush()
    return EXIT_OK


# Setup guides shipped with the skill, printed verbatim by `guide` (no config, no network).
GUIDES_DIR = Path(__file__).resolve().parent.parent / "skills" / "onedrive" / "references"
GUIDE_TOPICS: dict[str, str] = {"macos-sync": "macos-sync-setup.md"}
DEFAULT_GUIDE_TOPIC = "macos-sync"
GUIDE_COMMAND = "guide"


def cmd_guide(args: argparse.Namespace) -> int:
    file_name = GUIDE_TOPICS.get(args.topic)
    if file_name is None:
        print(f"{PROG}: unknown guide topic {args.topic!r}; available: {', '.join(sorted(GUIDE_TOPICS))}",
              file=sys.stderr)
        return EXIT_USAGE
    sys.stdout.write((GUIDES_DIR / file_name).read_text(encoding="utf-8"))
    return EXIT_OK


COMMANDS: dict[str, Callable[[Context, argparse.Namespace], int]] = {
    "login": cmd_login, "logout": cmd_logout, "whoami": cmd_whoami, "folders": cmd_folders, "discover": cmd_discover,
    "ls": cmd_ls, "mkdir": cmd_mkdir, "put": cmd_put, "get": cmd_get,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROG, description="OneDrive/SharePoint over Microsoft Graph or a synced folder.")
    parser.add_argument("--config", help="path to dev-workflow.toml (default: search upwards from cwd)")
    sub = parser.add_subparsers(dest="command", required=True)
    login = sub.add_parser("login", help="sign in with a device code")
    logout = sub.add_parser("logout", help="remove the stored sign-in")
    whoami = sub.add_parser("whoami", help="print the signed-in account")
    folders = sub.add_parser("folders", help="list configured folder aliases")
    folders.add_argument("--check", action="store_true", help="resolve each alias (Graph) or check its path (local)")
    discover = sub.add_parser("discover", help="list OneDrive sync folders on this machine")
    ls = sub.add_parser("ls", help="list a folder: kind, name, size, lastModified")
    ls.add_argument("remote", metavar="ALIAS:[PATH]")
    ls.add_argument("--json", action="store_true")
    mkdir = sub.add_parser("mkdir", help="create nested folders (like mkdir -p)")
    mkdir.add_argument("remote", metavar="ALIAS:PATH")
    mkdir.add_argument("--dry-run", action="store_true")
    put = sub.add_parser("put", help="upload a local file")
    put.add_argument("local", metavar="LOCAL_FILE")
    put.add_argument("remote", metavar="ALIAS:PATH")
    put.add_argument("--overwrite", action="store_true", help="replace an existing file")
    put.add_argument("--mkdir", action="store_true", help="create missing parent folders first")
    put.add_argument("--dry-run", action="store_true")
    get = sub.add_parser("get", help="download a file to --out or stdout")
    get.add_argument("remote", metavar="ALIAS:PATH")
    get.add_argument("--out", metavar="FILE")
    guide = sub.add_parser(GUIDE_COMMAND, help="print a setup guide (no config needed)")
    guide.add_argument("--topic", default=DEFAULT_GUIDE_TOPIC, help=f"one of: {', '.join(sorted(GUIDE_TOPICS))}")
    for child in (guide, login, logout, whoami, folders, discover, ls, mkdir, put, get):
        child.add_argument("--config", default=argparse.SUPPRESS, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None, transport: Transport = urllib_transport,
         sleep: Callable[[float], None] = time.sleep) -> int:
    args = build_parser().parse_args(argv)
    if args.command == GUIDE_COMMAND:
        return cmd_guide(args)
    try:
        ctx = Context(load_settings(args.config), transport, sleep)
        return COMMANDS[args.command](ctx, args)
    except (ConfigError, UsageError, PathError, AuthError) as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except GraphError as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        return EXIT_REMOTE_ERROR
    except NetworkError as exc:
        print(f"{PROG}: network error: {exc}", file=sys.stderr)
        return EXIT_REMOTE_ERROR
    except OSError as exc:
        print(f"{PROG}: file error: {exc}", file=sys.stderr)
        return EXIT_REMOTE_ERROR


if __name__ == "__main__":
    sys.exit(main())
