"""Read-only model choices for the three-tier picker."""
from __future__ import annotations

from account_label import PROVIDER_CLAUDE, account_label
from usage_pricing import load_prices
from .constants import MODEL_CAPABILITIES, PROVIDER_EFFORTS

TIER_LABELS = {"brain": "Brain chính", "side": "Phiên phụ", "hand": "Hand"}
CLAUDE_MODEL_ORDER = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")


def build_options(result, status: dict) -> dict:
    prices = load_prices()
    providers = {}
    for provider, models in MODEL_CAPABILITIES.items():
        ordered = CLAUDE_MODEL_ORDER if provider == "claude" else sorted(models)
        providers[provider] = {
            "models": [model for model in ordered if model in models and model in prices],
            "efforts": list(PROVIDER_EFFORTS[provider]),
        }
    profiles, tiers = {}, []
    for tier in ("brain", "side"):
        profile = status[tier]
        provider = profile["provider"]["value"]
        model = profile[provider + "_model"]["value"]
        effort = profile[provider + "_effort"]["value"]
        account = profile["claude_account"]["value"]
        profiles[tier] = dict(provider=provider, model=model, effort=effort, account=account)
        current = f"{provider}:{model}:{effort}"
        if provider == "claude":
            current += "@" + account
        tiers.append(dict(value=tier, label=TIER_LABELS[tier], current=current))
    order = status["hand"]["order"]["value"]
    tiers.append(dict(value="hand", label=TIER_LABELS["hand"], current=", ".join(order)))
    ext = result.effective["ext_hand"]
    accounts = [dict(slot=slot, label=account_label(PROVIDER_CLAUDE, slot, ext),
                     selected=slot == profiles["brain"]["account"])
                for slot in sorted(ext["claude_accounts"], key=lambda s: int(s[1:]))]
    backends = [dict(value=name, provider="claude" if row.get("account") else name,
                     model=row["model"]["value"], effort=row["effort"]["value"],
                     account=row.get("account"), in_order=name in order)
                for name, row in status["hand"]["backends"].items() if row["supported"]]
    return dict(tiers=tiers, providers=providers, profiles=profiles,
                accounts=accounts, hand_backends=backends,
                presets=_presets(profiles, backends, providers))


PROFILE_PRESETS = (
    ("claude", "claude-opus-5-5", "high"),
    ("claude", "claude-sonnet-5-5", "high"),
    ("codex", "gpt-6.1-sol", "high"),
    ("claude", "claude-opus-5-5", "max"),
    ("codex", "gpt-6.1-sol", "xhigh"),
)
MAX_PRESETS = 4


def _presets(profiles: dict, backends: list[dict], providers: dict) -> dict:
    def entry(label: str, description: str, args: list[str]) -> dict:
        return dict(label=label, description=description, args=args)

    def available(provider: str, model: str, effort: str) -> bool:
        return model in providers[provider]["models"] and effort in providers[provider]["efforts"]

    groups = {}
    for tier, current in profiles.items():
        suffix = " @" + current["account"] if current["provider"] == "claude" else ""
        rows = [entry("Giữ nguyên", f"{current['model']} {current['effort']}" + suffix, [])]
        for provider, model, effort in PROFILE_PRESETS:
            if not available(provider, model, effort):
                continue
            if (provider, model, effort) == (current["provider"], current["model"], current["effort"]):
                continue
            account = "@" + current["account"] if provider == "claude" else ""
            rows.append(entry(f"{model} {effort}" + (" " + account if account else ""),
                              provider, ["--" + tier, f"{model}:{effort}{account}"]))
        groups[tier] = rows[:MAX_PRESETS]
    for group, claude in (("hand_claude", True), ("hand_other", False)):
        selected = [row for row in backends if (row["provider"] == "claude") == claude]
        description = " · ".join(f"{row['value']} {row['model']} {row['effort']}" for row in selected)
        rows = [entry("Giữ nguyên", description, [])]
        for row in selected:
            candidates = (("claude-sonnet-5-5", "low"), ("claude-haiku-5-5", "low")) if claude else (
                (("gpt-6.1-sol", "medium"), ("gpt-6.1-sol", "high")) if row["provider"] == "codex"
                else (("deepseek-v4.1-flash", "high"),))
            for model, effort in candidates:
                if (model, effort) == (row["model"], row["effort"]) or not available(row["provider"], model, effort):
                    continue
                rows.append(entry(f"{row['value']} → {model} {effort}", row["provider"],
                                  ["--hand", f"{row['value']}={model}:{effort}"]))
        groups[group] = rows[:MAX_PRESETS]
    return groups


def print_options(payload: dict) -> None:
    for tier in payload["tiers"]:
        print(f"{tier['label']}: {tier['current']}")
    for provider, row in payload["providers"].items():
        print(f"{provider}: {', '.join(row['models'])}; effort: {', '.join(row['efforts'])}")
    for row in payload["accounts"]:
        print(f"{'*' if row['selected'] else ' '} {row['slot']}: {row['label']}")
    for row in payload["hand_backends"]:
        print(f"{'*' if row['in_order'] else ' '} {row['value']}: {row['model']}:{row['effort']}")
    for group, rows in payload["presets"].items():
        print(f"{group} presets: " + " | ".join(row["label"] for row in rows))
