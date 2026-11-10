"""Inspect three model tiers and atomically patch their repository overrides."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from shared_config import (GlobalConfigError, _merge, _validate, canonical_backend,
                           file_stamp, load_config)
from usage_pricing import load_prices
from .constants import EFFORT_ALIASES, MODEL_CAPABILITIES, PROVIDER_EFFORTS

TIERS = {"brain": "main_session", "side": "side_session"}
PROFILE_KEYS = ("provider", "codex_model", "codex_effort", "claude_model",
                "claude_effort", "claude_account")
MODEL_KEYS = ("model", "effort")
REMINDER = "mở phiên mới để áp dụng"


def register(sub) -> None:
    parser = sub.add_parser("models", help="xem/set/unset model ba tầng")
    actions = parser.add_subparsers(dest="models_action")
    setters = actions.add_parser("set")
    for name in ("brain", "side", "hand", "hand-order"):
        setters.add_argument("--" + name, action="append")
    setters.add_argument("--tier", choices=("brain", "side", "hand"))
    for name in ("model", "effort", "account"):
        setters.add_argument("--" + name)
    unset = actions.add_parser("unset")
    unset.add_argument("tier", choices=("brain", "side", "hand"))
    options = actions.add_parser("options", help="liệt kê lựa chọn model ba tầng")
    for item in (parser, setters, unset, options):
        # Suppress child defaults so options before the subcommand also survive.
        item.add_argument("--cwd", default=argparse.SUPPRESS)
        item.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
        if item in (setters, unset):
            item.add_argument("--dry-run", action="store_true")


def _leaf(result, key: str, value=None) -> dict:
    parts = key.split(".")
    current = result.effective
    if value is None:
        for part in parts:
            current = current.get(part) if isinstance(current, dict) else None
        value = current
    source = result.sources.get(key, "plugin")
    return {"value": value, "source": source,
            "file": result.paths[source]["path"] if source != "plugin" else str(
                Path(__file__).with_name("constants.py") if parts[0] == "ext_hand" else
                Path(__file__).parents[1] / ("shared_config.py" if parts[0] == "main_session"
                                            else "side_session/constants.py"))}


def _raw_leaf(data: dict, key: str):
    for part in key.split("."):
        data = data.get(part) if isinstance(data, dict) else None
    return data


def _summary(leaves: list[dict], account: bool = False) -> str:
    sources = {leaf["source"] for leaf in leaves}
    values = [str(leaf["value"]) for leaf in leaves]
    if account:
        values[-1] = "@" + values[-1]
    if len(sources) == 1:
        return " ".join(values) + " [" + leaves[0]["source"] + "]"
    return " ".join(value + " [" + leaf["source"] + "]"
                    for value, leaf in zip(values, leaves))


def _print_text(payload: dict) -> None:
    print("Model cho phiên mới (brain qua side-session start --main):")
    for tier in TIERS:
        profile = payload[tier]
        provider = profile["provider"]
        selected = provider["value"]
        profiles = []
        for name in (selected, "claude" if selected == "codex" else "codex"):
            leaves = [profile[name + "_model"], profile[name + "_effort"]]
            if name == "claude":
                leaves.append(profile["claude_account"])
            label = name + " [" + provider["source"] + "]" if name == selected else name + ":"
            profiles.append(label + " " + _summary(leaves, name == "claude"))
        print(tier + ": " + " · ".join(profiles))
    hand = payload["hand"]
    print("hand order: " + ", ".join(hand["order"]["value"]) +
          " [" + hand["order"]["source"] + "]")
    for name, row in hand["backends"].items():
        summary = (_summary([row["model"], row["effort"]])
                   if row["supported"] else "(ngoài phạm vi chỉnh)")
        if row.get("account"):
            summary += " @" + row["account"]
        print(f"  {name:<10} {summary}")
    for warning in payload["warnings"]:
        print(warning)
    if "diff" in payload:
        for leaf, (old, new) in payload["diff"].items():
            print(f"{leaf}: {json.dumps(old, ensure_ascii=False)} → {json.dumps(new, ensure_ascii=False)}")
        print("file: " + payload["file"])
        if payload["dry_run"]:
            print("dry-run: không ghi")
        if "reminder" in payload:
            print(payload["reminder"])


def _supported(name: str, accounts: dict) -> bool:
    return name in ("codex", "dsh") or (name.startswith("claude-") and name[7:] in accounts)


def _status(result) -> dict:
    output = {}
    for tier, section in TIERS.items():
        output[tier] = {key: _leaf(result, f"{section}.{key}") for key in PROFILE_KEYS}
    ext = result.effective["ext_hand"]
    names = list(dict.fromkeys(canonical_backend(n) for n in
                 ext["order"] + list(ext["backends"]) + ["claude-" + a for a in ext["claude_accounts"]]))
    rows = {}
    for name in names:
        row = {"supported": _supported(name, ext["claude_accounts"])}
        for key in MODEL_KEYS:
            path = f"ext_hand.backends.{name}.{key}"
            if name.startswith("claude-") and name[7:] in ext["claude_accounts"]:
                account = name[7:]
                alias = {"v1": "claude-main", "v2": "claude"}.get(account)
                paths = [f"ext_hand.backends.{alias}.{key}",
                         f"ext_hand.claude_accounts.{account}.{key}", path]
                selected = next((p for p in reversed(paths) if result.sources.get(p) in
                                 ("global", "repo")), None)
                row[key] = _leaf(result, selected) if selected else _leaf(
                    result, f"ext_hand.backends.claude.{key}",
                    "claude-opus-5-5" if key == "model" else "low")
                row["account"] = account
            else:
                row[key] = _leaf(result, path)
        rows[name] = row
    output["hand"] = {"order": _leaf(result, "ext_hand.order"), "backends": rows}
    output["warnings"] = ["Model hand cũng áp dụng cho native subagent dùng cùng backend."]
    backend = result.effective["parallel_subagents"]["backend"]
    if backend.startswith("claude-") and backend[7:] != result.effective["main_session"]["claude_account"]:
        output["warnings"].append("Backend subagent khác tài khoản brain; native cần cùng tài khoản.")
    return output


def _validate_model(provider: str, model, effort) -> None:
    if provider not in MODEL_CAPABILITIES or model not in MODEL_CAPABILITIES[provider]:
        raise ValueError("model không thuộc capability provider")
    if model not in load_prices():
        raise ValueError("model không có giá hợp lệ")
    if effort not in PROVIDER_EFFORTS[provider]:
        raise ValueError("effort không hợp lệ cho provider")


def _put(data: dict, key: str, value) -> None:
    parts = key.split(".")
    for part in parts[:-1]:
        data = data.setdefault(part, {})
        if not isinstance(data, dict):
            raise ValueError("section phải là object")
    data[parts[-1]] = value


def _remove(data: dict, parts: list[str]) -> None:
    if len(parts) == 1:
        data.pop(parts[0], None)
    elif isinstance(data.get(parts[0]), dict):
        child = data[parts[0]]
        _remove(child, parts[1:])
        if not child:
            data.pop(parts[0])


def _candidate(result, raw: dict):
    candidate = copy.deepcopy(result)
    candidate.effective, candidate.sources = {}, {}
    # Rebuild without the old repo source, retaining plugin/global inheritance.
    from shared_config import _build_config
    import io
    # Use a guaranteed absent path without creating a fixture or directory.
    import uuid
    base = _build_config(result.root, Path(result.paths["global"]["path"]),
                         result.root / (".models-absent-" + uuid.uuid4().hex), io.StringIO())
    for source, section in (("plugin", base.effective),):
        _merge(candidate.effective, section, candidate.sources, source)
    candidate.sources = copy.deepcopy(base.sources)
    _merge(candidate.effective, raw, candidate.sources, "repo")
    _validate(raw, Path(result.paths["repo"]["path"]))
    return candidate


def _expand_flat(args, accounts: dict) -> list[str]:
    if not any(getattr(args, name) is not None for name in ("tier", "model", "effort", "account")):
        return []
    if any(getattr(args, name) is not None for name in ("brain", "side", "hand", "hand_order")):
        raise ValueError("cờ phẳng không được dùng chung với --brain/--side/--hand/--hand-order")
    if not all(getattr(args, name) for name in ("tier", "model", "effort")):
        raise ValueError("cờ phẳng cần --tier, --model và --effort")
    providers = [p for p, models in MODEL_CAPABILITIES.items() if args.model in models]
    if len(providers) != 1:
        raise ValueError("model không thuộc capability provider")
    provider = providers[0]
    effort = EFFORT_ALIASES.get(provider, {}).get(args.effort, args.effort)
    _validate_model(provider, args.model, effort)
    warnings = []
    account = args.account
    if provider != "claude" and account is not None:
        warnings.append("account chỉ áp cho Claude, đã bỏ qua")
        account = None
    if provider == "claude" and account is not None:
        if not re.fullmatch(r"v[1-9][0-9]*", account) or account not in accounts:
            raise ValueError("account không hợp lệ")
    if args.tier == "hand":
        if provider == "claude" and account is None:
            raise ValueError("hand Claude cần --account vN")
        backend = "claude-" + account if provider == "claude" else provider
        args.hand = [f"{backend}={args.model}:{effort}"]
    else:
        if provider not in ("claude", "codex"):
            raise ValueError("provider phải là claude hoặc codex")
        profile = f"{provider}:{args.model}:{effort}"
        setattr(args, args.tier, [profile + ("@" + account if account is not None else "")])
    return warnings


def _patch(args, result, raw: dict) -> list[str]:
    touched = []
    accounts = result.effective["ext_hand"]["claude_accounts"]
    if args.models_action == "unset":
        if args.tier in TIERS:
            touched = [TIERS[args.tier] + "." + k for k in PROFILE_KEYS]
        else:
            touched = ["ext_hand.order"]
            ext = raw.get("ext_hand", {})
            for registry in ("backends", "claude_accounts"):
                for name in ext.get(registry, {}):
                    if (registry == "claude_accounts" and re.fullmatch(r"v[1-9][0-9]*", name)
                            or registry == "backends" and _supported(canonical_backend(name), accounts)):
                        touched.extend(f"ext_hand.{registry}.{name}.{key}" for key in MODEL_KEYS)
        for key in touched:
            _remove(raw, key.split("."))
        return touched
    def put(key, value):
        _put(raw, key, value)
        touched.append(key)
    for tier, section in TIERS.items():
        values = getattr(args, tier)
        if not values:
            continue
        if len(values) != 1:
            raise ValueError("mỗi tầng chỉ được truyền một lần")
        match = re.fullmatch(r"(claude|codex):([^:@]+)(?::([^:@]+))?(?:@(v[1-9][0-9]*))?", values[0])
        if not match:
            raise ValueError("profile phải là PROVIDER:MODEL[:EFFORT][@vN]")
        provider, model, effort, account = match.groups()
        if account and (provider != "claude" or account not in accounts):
            raise ValueError("account không hợp lệ")
        put(section + ".provider", provider)
        put(section + f".{provider}_model", model)
        if effort:
            put(section + f".{provider}_effort", effort)
        if account:
            put(section + ".claude_account", account)
    seen = set()
    for value in args.hand or []:
        match = re.fullmatch(r"([^=]+)=([^:@]+)(?::([^:@]+))?", value)
        if not match:
            raise ValueError("hand phải là BACKEND=MODEL[:EFFORT]")
        name, model, effort = match.groups()
        name = canonical_backend(name)
        if name in seen or not _supported(name, accounts):
            raise ValueError("backend trùng hoặc không được hỗ trợ")
        seen.add(name)
        put(f"ext_hand.backends.{name}.model", model)
        if effort:
            put(f"ext_hand.backends.{name}.effort", effort)
    if args.hand_order:
        if len(args.hand_order) != 1:
            raise ValueError("order chỉ được truyền một lần")
        order = [canonical_backend(n) for n in args.hand_order[0].split(",")]
        if len(set(order)) != len(order) or not all(_supported(n, accounts) for n in order):
            raise ValueError("order rỗng, trùng hoặc backend không hợp lệ")
        put("ext_hand.order", order)
    if not touched:
        raise ValueError("set cần ít nhất một thay đổi")
    return touched


def _validate_candidate(result) -> None:
    for section in TIERS.values():
        profile = result.effective[section]
        provider = profile["provider"]
        if provider not in ("claude", "codex"):
            raise ValueError("provider phải là claude hoặc codex")
        for p in ("claude", "codex"):
            _validate_model(p, profile[p + "_model"], profile[p + "_effort"])
        if profile["claude_account"] not in result.effective["ext_hand"]["claude_accounts"]:
            raise ValueError("account không tồn tại")
    for name, row in _status(result)["hand"]["backends"].items():
        if row["supported"]:
            _validate_model("claude" if name.startswith("claude-") else name,
                            row["model"]["value"], row["effort"]["value"])


def _write(path: Path, raw: dict, stamps: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(raw, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if any(file_stamp(p) != stamp for p, stamp in stamps.items()):
            raise OSError("config đã đổi; chạy lại")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def command(args) -> int:
    try:
        result = load_config(Path(getattr(args, "cwd", None) or Path.cwd()))
        payload = _status(result)
        if args.models_action == "options":
            from .models_options import build_options, print_options
            payload = build_options(result, payload)
            if getattr(args, "json", False):
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print_options(payload)
            return 0
        if args.models_action:
            path = Path(result.paths["repo"]["path"])
            stamps = {Path(info["path"]): file_stamp(Path(info["path"]))
                      for info in result.paths.values()}
            result = load_config(known_root=result.root, config_file=path)
            raw = json.loads(path.read_text()) if path.exists() else {}
            before = copy.deepcopy(raw)
            warnings = (_expand_flat(args, result.effective["ext_hand"]["claude_accounts"])
                        if args.models_action == "set" else [])
            touched = _patch(args, result, raw)
            candidate = _candidate(result, raw)
            _validate_candidate(candidate)
            payload = _status(candidate)
            payload["warnings"].extend(warnings)
            for warning in warnings:
                print(warning, file=sys.stderr)
            changed = raw != before
            dry_run = getattr(args, "dry_run", False)
            if changed and not dry_run:
                _write(path, raw, stamps)
            diff = {key: [_raw_leaf(before, key), _raw_leaf(raw, key)]
                    for key in touched}
            payload.update(changed=changed, dry_run=dry_run, leaves=touched,
                           diff=diff, file=str(path))
            if changed and not dry_run:
                payload["reminder"] = REMINDER
        if getattr(args, "json", False):
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            _print_text(payload)
        return 0
    except (OSError, GlobalConfigError) as exc:
        message = f"lỗi I/O/config ({type(exc).__name__})"
        if isinstance(exc, OSError) and str(exc) == "config đã đổi; chạy lại":
            message = "config đã đổi; chạy lại"
        print(f"models: {message}", file=sys.stderr)
        return 1
    except (ValueError, TypeError, KeyError) as exc:
        print(f"models: {exc}" if isinstance(exc, ValueError) else
              "models: cấu trúc cấu hình không hợp lệ", file=sys.stderr)
        return 2
