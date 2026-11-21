#!/usr/bin/env python3
"""Turn-by-turn timing report for a Claude Code session.

Adapted from the owner's many-game-show project (scripts/session_timing.py). It reads the session
transcript the harness keeps under ~/.claude/projects/<project-slug>/<session-id>.jsonl and writes
a markdown table with one row per human request:

- "Agent time spent": from the human message to the last assistant or tool event before the next
  human message, i.e. how long the agent was working.
- "Human think time": from the end of that agent work to the next human message, i.e. how long the
  human took to read and reply, with the agent's own time taken out.
- Token use for the turn, summed over every model round-trip in it.

The log is committed to a public repo, so each prompt is cleaned and *redacted* before the first 70
characters are kept: harness reminders are dropped, and secret-shaped strings, emails and Claude
session links are replaced. The transcript's path is not printed either.

    python3 scripts/session_timing.py --header scripts/session_log_header.md --out-dir session-logs

writes session-logs/<start of the session, UTC>.md, so a later session never overwrites an earlier
one. With --out FILE it writes that file; with neither it prints the report.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

PROMPT_CHARS = 70

# Real single-turn agent work should not plausibly take longer than this; a larger value usually
# means an event was stamped near session-resume time, so it is flagged instead of counted.
AGENT_TIME_SANITY_SECONDS = 30 * 60

# Think time over this means the human stepped away. It is left out of the total and the average.
THINK_TIME_OUTLIER_SECONDS = 15 * 60

# ---- cleaning and redaction ----------------------------------------------------------------

_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
_PASTE_TAG = re.compile(r"</?pasted_content[^>]*>")

# Order matters: the specific shapes go first so the generic ones do not half-match them.
_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"https?://\S*claude\.ai/\S*", re.I), "[link removed]"),
    (re.compile(r"\bsession_[A-Za-z0-9]{8,}\b"), "[session id removed]"),
    (
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*-----|$)", re.S),
        "[key]",
    ),
    (re.compile(r"\b(?:https?|ssh|ftp)://[^\s/@:]+:[^\s/@]+@\S+", re.I), "[url with login]"),
    (re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]*"), "[token]"),
    (re.compile(r"\bgithub_pat_\w{20,}"), "[token]"),
    (re.compile(r"\b(?:gh[pousr]|sk|pk|rk)[-_][A-Za-z0-9_-]{16,}"), "[token]"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{8,}"), "[token]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[token]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{30,}"), "[token]"),
    (re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"), "[token]"),
    (re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", re.I), "Bearer [redacted]"),
    (
        re.compile(
            r"(?i)\b(pass(?:word|wd)?|pwd|secret|token|api[_-]?key|credential|auth)s?\b"
            r"(\s*[:=]\s*)(\S+)"
        ),
        r"\1\2[redacted]",
    ),
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email]"),
    # Any long run that mixes letters and digits (hashes, keys) and is not an ordinary word.
    (re.compile(r"\b(?=[\w=-]*\d)(?=[\w=-]*[A-Za-z])[\w=-]{32,}\b"), "[redacted]"),
]


def redact(text: str) -> str:
    """Replace secret-shaped strings, emails and Claude links so the text is safe to publish."""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def clean_prompt(text: str) -> str:
    """The human's own words: no harness reminders or paste wrappers, one line, redacted."""
    text = _REMINDER.sub(" ", text)
    text = _PASTE_TAG.sub(" ", text)
    text = " ".join(text.split())
    return redact(text)


# ---- reading the transcript ----------------------------------------------------------------


def project_slug(cwd: Path) -> str:
    return str(cwd.resolve()).replace("/", "-")


def find_transcript(session_id: str | None = None, home: Path | None = None) -> Path:
    base = (home or Path.home()) / ".claude" / "projects" / project_slug(Path.cwd())
    if session_id:
        path = base / f"{session_id}.jsonl"
        if not path.exists():
            raise SystemExit(f"No session transcript for that id under {base.name}")
        return path
    found = sorted(base.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not found:
        raise SystemExit(f"No session transcript found under {base.name}")
    return found[0]


def is_human_turn(entry: dict) -> bool:
    return entry.get("type") == "user" and (entry.get("origin") or {}).get("kind") == "human"


def is_agent_activity(entry: dict) -> bool:
    """Model output, or a tool result feeding the agent's own loop. Harness bookkeeping entries
    (queue operations, attachments, system notes) are not: they can be stamped on either side of
    a turn boundary and would stretch a turn that has already ended."""
    kind = entry.get("type")
    return kind == "assistant" or (kind == "user" and not is_human_turn(entry))


def usage_of(entry: dict) -> dict[str, int]:
    usage = (entry.get("message") or {}).get("usage") or {}
    return {
        "input": usage.get("input_tokens", 0),
        "output": usage.get("output_tokens", 0),
        "cache_write": usage.get("cache_creation_input_tokens", 0),
        "cache_read": usage.get("cache_read_input_tokens", 0),
    }


def first_text(entry: dict) -> str:
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return str(block.get("text", ""))
    return ""


def parse_ts(raw: str) -> datetime:
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


def fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes:.0f}m {secs:.0f}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours:.0f}h {mins:.0f}m"


def load_turns(path: Path) -> list[dict]:
    """One dict per human message: cleaned, redacted prompt; start; last agent activity; usage."""
    entries = []
    with path.open() as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    entries = sorted((e for e in entries if e.get("timestamp")), key=lambda e: e["timestamp"])

    turns: list[dict] = []
    current: dict | None = None
    for entry in entries:
        if is_human_turn(entry):
            if current is not None:
                turns.append(current)
            current = {
                "prompt": clean_prompt(first_text(entry)),
                "start": entry["timestamp"],
                "last_activity": entry["timestamp"],
                "usage": {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0},
            }
        elif current is not None and is_agent_activity(entry):
            current["last_activity"] = entry["timestamp"]
            if entry.get("type") == "assistant":
                for key, value in usage_of(entry).items():
                    current["usage"][key] += value
    if current is not None:
        turns.append(current)
    return turns


# ---- the report ----------------------------------------------------------------------------


def summarize(turns: list[dict]) -> dict:
    total_agent = flagged_agent = total_think = think_outlier_seconds = 0.0
    think_count = 0
    flagged: list[int] = []
    outliers: list[int] = []
    usage = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    for i, turn in enumerate(turns, 1):
        agent_seconds = (parse_ts(turn["last_activity"]) - parse_ts(turn["start"])).total_seconds()
        if agent_seconds > AGENT_TIME_SANITY_SECONDS:
            flagged.append(i)
            flagged_agent += agent_seconds
        else:
            total_agent += agent_seconds
        if i < len(turns):
            gap = (parse_ts(turns[i]["start"]) - parse_ts(turn["last_activity"])).total_seconds()
            if gap > THINK_TIME_OUTLIER_SECONDS:
                outliers.append(i)
                think_outlier_seconds += gap
            else:
                total_think += gap
                think_count += 1
        for key in usage:
            usage[key] += turn["usage"][key]
    return {
        "turns": len(turns),
        "agent_seconds": total_agent,
        "flagged_agent_seconds": flagged_agent,
        "flagged_turns": flagged,
        "think_seconds": total_think,
        "think_count": think_count,
        "think_outlier_turns": outliers,
        "think_outlier_seconds": think_outlier_seconds,
        "usage": usage,
    }


def build_report(turns: list[dict], header: str = "# Session Timing Report\n") -> str:
    out = [header.rstrip("\n") + "\n\n"]
    out.append(
        "| # | Prompt (truncated) | Started (UTC) | Agent time spent | Human think time "
        "| Input | Output | Cache Write | Cache Read |\n"
    )
    out.append("|---|---|---|---|---|---|---|---|---|\n")
    for i, turn in enumerate(turns, 1):
        start = parse_ts(turn["start"])
        agent_seconds = (parse_ts(turn["last_activity"]) - start).total_seconds()
        suspicious = agent_seconds > AGENT_TIME_SANITY_SECONDS
        if i < len(turns):
            gap = (parse_ts(turns[i]["start"]) - parse_ts(turn["last_activity"])).total_seconds()
            think = fmt_duration(gap) + (" ⏳" if gap > THINK_TIME_OUTLIER_SECONDS else "")
        else:
            think = "—"
        prompt = turn["prompt"]
        prompt = prompt[:PROMPT_CHARS] + ("…" if len(prompt) > PROMPT_CHARS else "")
        prompt = prompt.replace("|", "\\|")
        agent = fmt_duration(agent_seconds) + (" ⚠" if suspicious else "")
        u = turn["usage"]
        out.append(
            f"| {i} | {prompt} | {start.strftime('%H:%M:%S')} | {agent} | {think} "
            f"| {u['input']:,} | {u['output']:,} | {u['cache_write']:,} | {u['cache_read']:,} |\n"
        )

    s = summarize(turns)
    avg_think = s["think_seconds"] / s["think_count"] if s["think_count"] else 0.0
    u = s["usage"]
    prompt_side = u["input"] + u["cache_write"] + u["cache_read"]
    ratio = u["cache_read"] / prompt_side if prompt_side else 0.0
    out.append(
        f"\n**Total turns:** {s['turns']}  \n"
        f"**Total agent time spent (excl. flagged):** {fmt_duration(s['agent_seconds'])}  \n"
        f"**Total human think time (excl. outliers):** {fmt_duration(s['think_seconds'])}  \n"
        f"**Average human think time (excl. outliers):** {fmt_duration(avg_think)}  \n"
        f"**Think-time outliers (> {THINK_TIME_OUTLIER_SECONDS // 60} min):** "
        f"{len(s['think_outlier_turns'])}  \n"
        f"**Total input tokens:** {u['input']:,}  \n"
        f"**Total output tokens:** {u['output']:,}  \n"
        f"**Total cache-write tokens:** {u['cache_write']:,}  \n"
        f"**Total cache-read tokens:** {u['cache_read']:,}  \n"
        f"**Cache hit ratio (cache-read / all prompt-side tokens):** {ratio:.0%}\n"
    )
    if s["flagged_turns"]:
        out.append(
            f"\n⚠ Turn(s) {', '.join(map(str, s['flagged_turns']))} show agent time over "
            f"{AGENT_TIME_SANITY_SECONDS // 60} min "
            f"(total {fmt_duration(s['flagged_agent_seconds'])}), which is not plausible as real "
            "work, probably an entry stamped near session-resume time. Excluded from the "
            "agent-time total.\n"
        )
    if s["think_outlier_turns"]:
        out.append(
            f"\n⏳ Turn(s) {', '.join(map(str, s['think_outlier_turns']))} show think time over "
            f"{THINK_TIME_OUTLIER_SECONDS // 60} min (total "
            f"{fmt_duration(s['think_outlier_seconds'])}), likely a break or a resumed session. "
            "Excluded from the total and the average, still shown per row.\n"
        )
    return "".join(out)


def default_log_name(turns: list[dict]) -> str:
    """File name from when the session started, so a later session never overwrites this one."""
    return parse_ts(turns[0]["start"]).strftime("%Y-%m-%dT%H%MZ") + ".md"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("session_id", nargs="?", default=None)
    parser.add_argument("--header", type=Path, help="markdown text to use as the report's title")
    parser.add_argument("--out", type=Path, help="write the report to this file")
    parser.add_argument("--out-dir", type=Path, help="write DIR/<session start, UTC>.md")
    args = parser.parse_args()

    turns = load_turns(find_transcript(args.session_id))
    if not turns:
        raise SystemExit("The transcript has no human turns yet")
    header = args.header.read_text() if args.header else "# Session Timing Report\n"
    report = build_report(turns, header)
    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        target = args.out_dir / default_log_name(turns)
        target.write_text(report)
        print(target)
    elif args.out:
        args.out.write_text(report)
    else:
        print(report, end="")


if __name__ == "__main__":
    main()
