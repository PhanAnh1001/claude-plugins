#!/usr/bin/env python3
"""Python fallback for install.sh when jq is missing: read or edit the statusLine key of a
Claude Code settings JSON document. Python >= 3.9, stdlib only.

Usage (the document is read from stdin):
    settings_json.py get-command          # print .statusLine.command when .statusLine.type is "command"
    settings_json.py set-command <cmd>    # print the document with .statusLine = {type: command, command: <cmd>}
    settings_json.py delete               # print the document without .statusLine
    settings_json.py install-path <key> <plugin-name>
                                          # stdin is installed_plugins.json; print the installPath of
                                          # <key>, else of the first "<plugin-name>@..." entry

Every other key is kept as it is (order included). Exit 1 with a message on stderr when stdin is
not a JSON object.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Optional

EXIT_OK = 0
EXIT_ERROR = 1
STATUS_LINE_KEY = "statusLine"
TYPE_KEY = "type"
COMMAND_KEY = "command"
COMMAND_TYPE = "command"
PLUGINS_KEY = "plugins"
INSTALL_PATH_KEY = "installPath"
PLUGIN_KEY_SEPARATOR = "@"
JSON_INDENT = 2


def read_object() -> dict:
    document = json.loads(sys.stdin.read())
    if not isinstance(document, dict):
        raise ValueError("settings JSON is not an object")
    return document


def write_object(document: dict) -> None:
    sys.stdout.write(json.dumps(document, indent=JSON_INDENT, ensure_ascii=False) + "\n")


def get_command(document: dict) -> Optional[str]:
    status_line = document.get(STATUS_LINE_KEY)
    if not isinstance(status_line, dict) or status_line.get(TYPE_KEY) != COMMAND_TYPE:
        return None
    command = status_line.get(COMMAND_KEY)
    return command if isinstance(command, str) else None


def set_command(document: dict, command: str) -> dict:
    current = document.get(STATUS_LINE_KEY)
    status_line: dict[str, Any] = dict(current) if isinstance(current, dict) else {}
    status_line[TYPE_KEY] = COMMAND_TYPE
    status_line[COMMAND_KEY] = command
    document[STATUS_LINE_KEY] = status_line
    return document


def first_install_path(entries: Any) -> Optional[str]:
    if not isinstance(entries, list) or not entries or not isinstance(entries[0], dict):
        return None
    path = entries[0].get(INSTALL_PATH_KEY)
    return path if isinstance(path, str) and path else None


def install_path(document: dict, key: str, plugin_name: str) -> Optional[str]:
    plugins = document.get(PLUGINS_KEY)
    if not isinstance(plugins, dict):
        return None
    exact = first_install_path(plugins.get(key))
    if exact:
        return exact
    prefix = plugin_name + PLUGIN_KEY_SEPARATOR
    for name, entries in plugins.items():
        path = first_install_path(entries) if name.startswith(prefix) else None
        if path:
            return path
    return None


def main(argv: list) -> int:
    action = argv[1] if len(argv) > 1 else ""
    try:
        document = read_object()
    except ValueError as error:
        sys.stderr.write(f"settings_json.py: invalid JSON: {error}\n")
        return EXIT_ERROR
    if action == "get-command":
        sys.stdout.write(get_command(document) or "")
    elif action == "set-command" and len(argv) == 3:
        write_object(set_command(document, argv[2]))
    elif action == "delete":
        document.pop(STATUS_LINE_KEY, None)
        write_object(document)
    elif action == "install-path" and len(argv) == 4:
        sys.stdout.write(install_path(document, argv[2], argv[3]) or "")
    else:
        sys.stderr.write(f"settings_json.py: unknown action {argv[1:]}\n")
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv))
