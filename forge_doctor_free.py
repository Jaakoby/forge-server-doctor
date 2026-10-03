#!/usr/bin/env python3
"""
Forge Server Doctor (FREE EDITION) — why won't my modded server start?

Reads a latest.log, debug.log or crash-report and names the root cause in plain
English, with the fix. Built for Forge/NeoForge 1.16-1.21 dedicated servers.

No dependencies. No install. Python 3.8+.

    python forge_doctor.py latest.log
    python forge_doctor.py crash-reports/crash-2026-10-01_12.34.56-server.txt
    python forge_doctor.py logs/latest.log.gz --json

Copyright (c) 2026. Sold as-is under the licence in LICENSE.txt.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern, Tuple

VERSION = "1.0.0-free"

UPGRADE_NOTICE = """
  ──────────────────────────────────────────────────────────────────────
  FREE edition: 6 startup checks, plus culprit attribution.

  Every failure mode, with the fix for each, is free to read:
    https://jaakoby.github.io/fix/

  The full version diagnoses 18 more of them in the log itself —
  mixin conflicts, missing dependencies, stale jars, invalid resource
  IDs, registry remapping, mod-rejection kicks, watchdog timeouts — and
  prints the specific fix instead of leaving you to match it by hand.

  https://kaiven.gumroad.com/l/forge-server-doctor
  ──────────────────────────────────────────────────────────────────────
"""


# Severity ranks how much this finding matters, not how loud the log was.
FATAL = "FATAL"      # the server did not start / died because of this
ERROR = "ERROR"      # broken, but the server may still be up
WARN = "WARN"        # worth fixing, not why you're here
INFO = "INFO"        # context


@dataclass
class Rule:
    """One known failure mode.

    `patterns` are searched against the whole log. The FIRST pattern that hits
    provides the evidence line; named groups from it feed into the detail text.
    """

    id: str
    title: str
    severity: str
    patterns: List[str]
    root_cause: str
    fix: str
    # Rules with a higher weight win when two rules describe the same crash.
    weight: int = 0
    # Optional: only fire if this also appears somewhere in the log.
    requires: Optional[str] = None
    # Optional: never fire if this appears (kills false positives).
    unless: Optional[str] = None
    detail: Optional[str] = None

    _compiled: List[Pattern] = field(default_factory=list, repr=False)

    def compile(self) -> "Rule":
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]
        return self


# ---------------------------------------------------------------------------
# The rule library. Each of these is a real failure mode with a real fix.
# ---------------------------------------------------------------------------

RULES: List[Rule] = [
    Rule(
        id="duplicate-mods",
        title="The same mod is installed twice",
        severity=FATAL,
        weight=95,
        patterns=[
            r"Found duplicate mods?.{0,200}?(?P<mod>\S{1,80})",
            r"DuplicateModsFoundException",
            r"Duplicate mod ids?: ?(?P<mod2>\S+)",
        ],
        root_cause=(
            "Two jars in mods/ declare the same mod id — usually an old copy left "
            "behind next to the new one after an update, or the same mod shipped inside "
            "another jar."
        ),
        fix=(
            "Delete the older jar. Sort mods/ by date and look for two files whose\n"
            "names differ only by version. If you deploy by copying a new jar in,\n"
            "ALWAYS remove the old one first -- copying does not replace a file whose\n"
            "name changed."
        ),
    ),
    Rule(
        id="world-lock",
        title="The world folder is already in use",
        severity=FATAL,
        weight=80,
        patterns=[
            r"Failed to check session lock",
            r"The directory .* is already being used",
            r"MinecraftException: Failed to check session lock",
            r"world is already in use",
        ],
        root_cause=(
            "Another process already holds this world. Either the server is genuinely "
            "still running, or a previous run did not shut down cleanly and left the "
            "session.lock held."
        ),
        fix=(
            "Make sure no other copy of the server is running -- check Task Manager\n"
            "for a java process, or `ps aux | grep java`. Stop it properly with the\n"
            "`stop` command, never by killing the window, or the lock survives.\n"
            "NOTE: if you are boot-testing a server while someone is playing on it,\n"
            "THIS is the error you get, and it tests nothing. Stop the live server\n"
            "first or test against a copy of the world."
        ),
    ),
    Rule(
        id="java-version",
        title="Wrong Java version",
        severity=FATAL,
        weight=98,
        patterns=[
            r"UnsupportedClassVersionError.*class file version (?P<cfv>\d+)\.\d+",
            r"has been compiled by a more recent version of the Java Runtime",
            r"java\.lang\.UnsupportedClassVersionError",
        ],
        root_cause=(
            "The server (or a mod) was compiled for a newer Java than the one running "
            "it. Class file version 52=Java 8, 60=Java 16, 61=Java 17, 65=Java 21."
        ),
        fix=(
            "Minecraft 1.17-1.20.4 wants Java 17. 1.20.5+ and 1.21 want Java 21.\n"
            "1.16 and older want Java 8.\n"
            "Point your start script at the right JDK explicitly rather than relying\n"
            "on whatever `java` resolves to on PATH -- that is usually the cause."
        ),
    ),
    Rule(
        id="out-of-memory",
        title="Out of memory",
        severity=FATAL,
        weight=88,
        patterns=[
            r"java\.lang\.OutOfMemoryError: (?P<what>[\w ]+)",
            r"GC overhead limit exceeded",
        ],
        root_cause=(
            "The JVM hit its heap ceiling. On a modded server this is usually a heap "
            "that's simply too small for the pack, but it can also be a memory leak or "
            "a world-gen spike from a chunk-heavy mod."
        ),
        fix=(
            "Raise -Xmx in your start script / user_jvm_args.txt. Rules of thumb for\n"
            "modded: 100 mods ~ 6G, 200+ mods ~ 8-10G. Set -Xms equal to -Xmx.\n"
            "Do NOT give the JVM all your RAM -- leave 2-4G for the OS.\n"
            "If it dies at the same point every time with plenty of heap, it is a leak\n"
            "or a worldgen spike, not a size problem; check what loaded just before."
        ),
    ),
    Rule(
        id="port-in-use",
        title="The port is already taken",
        severity=FATAL,
        weight=90,
        patterns=[
            r"java\.net\.BindException: Address already in use",
            r"\*\*\*\* FAILED TO BIND TO PORT",
            r"Perhaps a server is already running on that port",
        ],
        root_cause=(
            "Something already holds the port this server wants — usually another "
            "Minecraft server, or the previous run that hasn't fully exited."
        ),
        fix=(
            "Find the holder and stop it:\n"
            "  Windows: netstat -ano | findstr :25565   then Task Manager by PID\n"
            "  Linux:   ss -lptn 'sport = :25565'\n"
            "If you run more than one server on this machine, give each its own port\n"
            "in server.properties. Voice-chat mods bind their OWN port (24454) --\n"
            "if that is the one failing, the fix is the same but a different number."
        ),
    ),
    Rule(
        id="eula",
        title="EULA not accepted",
        severity=FATAL,
        weight=99,
        patterns=[
            r"You need to agree to the EULA",
            r"Go to eula\.txt for more info",
        ],
        root_cause="Mojang requires an explicit EULA acceptance before a server will start.",
        fix="Open eula.txt next to the server jar and set `eula=true`. That's the whole fix.",
    ),
]

for _r in RULES:
    _r.compile()



# Frames belonging to Minecraft, Forge and the JVM never identify a culprit.
_VANILLA = re.compile(
    # Minecraft, the loader itself, and the JVM.
    r"(server-1\.|client-1\.|forge-\d|neoforge-\d|^java\.|^jdk\.|^sun\.|"
    r"fmlcore|fmlloader|fmlearlydisplay|javafmllanguage|lowcodelanguage|mclanguage|"
    r"modlauncher|securejarhandler|bootstraplauncher|"
    r"^net\.minecraftforge|^net\.neoforged|^cpw\.mods|"
    # Shared libraries that ship inside the server are never the culprit.
    r"netty-|^io\.netty|^com\.google|^org\.apache|^org\.slf4j|^com\.mojang|"
    r"eventbus-|brigadier-|guava-|mixin-|log4j|slf4j|gson-|commons-|asm-|"
    r"jopt-|oshi-|^joptsimple|^oshi|authlib-|datafixerupper-|"
    r"^com\.electronwill|nightconfig)",
    re.I,
)


def blame_mod(lines: List[str]) -> Optional[Dict[str, str]]:
    """Name the mod that owns the first non-vanilla frame in the stack trace.

    Forge annotates every frame with the jar it came from, like
    `~[examplemod-2.4.0.jar%23132!/:2.4.0]`. The first such frame that is not
    Minecraft, Forge or the JDK is almost always the mod at fault.
    """
    frame_re = re.compile(r"^\s+at ([\w$\.]+)\([^)]*\)\s*~?\[([^\]]+)\]")
    for line in lines:
        m = frame_re.match(line)
        if not m:
            continue
        symbol, origin = m.group(1), m.group(2)
        jar = origin.split("%")[0].split("!")[0]
        if _VANILLA.search(jar) or _VANILLA.search(symbol):
            continue
        if not jar.endswith(".jar"):
            continue
        return {"jar": jar, "symbol": symbol}
    return None


# ---------------------------------------------------------------------------
# Log reading
# ---------------------------------------------------------------------------

# Real logs are adversarial. A mod that fetches a URL and logs the response
# can put an entire HTML page on ONE line -- a live server's debug.log was
# found carrying a single 107,445-character line of GitHub markup. No
# diagnostic message lives past the first couple of thousand characters, so
# matching is capped. Without this, scanning that file took 59 seconds.
MAX_SCAN_LINE = 4000


def read_log(path: str) -> List[str]:
    """Read a log, transparently handling .gz and odd encodings.

    Over-long lines are truncated for scanning (see MAX_SCAN_LINE).
    """
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as fh:  # type: ignore[operator]
        raw = fh.read()
    # Minecraft logs are usually UTF-8 but mods write whatever they like.
    text = raw.decode("utf-8", errors="replace")
    return [
        ln if len(ln) <= MAX_SCAN_LINE else ln[:MAX_SCAN_LINE] + " …[truncated]"
        for ln in text.splitlines()
    ]


@dataclass
class Finding:
    rule: Rule
    line_no: int
    evidence: str
    groups: Dict[str, str]


def environment(lines: List[str]) -> Dict[str, Optional[str]]:
    """Pull the facts worth knowing before reading any error."""
    env: Dict[str, Optional[str]] = {
        "minecraft": None,
        "forge": None,
        "java": None,
        "mod_count": None,
        "started_ok": None,
        "xmx": None,
        "description": None,
        "exception": None,
        "culprit_jar": None,
        "culprit_symbol": None,
    }
    joined = "\n".join(lines[:400]) + "\n".join(lines[-200:])

    m = re.search(r"Minecraft Version:\s*(\S+)", joined) or re.search(
        r"Starting minecraft server version (\S+)", joined
    )
    if m:
        env["minecraft"] = m.group(1)

    # Loader version, in priority order. The first two are authoritative; the
    # loose fallbacks are last because `forge-1.20.1-47.4.10-universal.jar`
    # will happily hand you the MINECRAFT version if you match too eagerly.
    for pat in (
        r"Forge:\s*net\.(?:neo)?(?:minecraft)?forge:(?:forge:)?(\d+\.\d+[\.\d]*)",
        r"(?:neo)?forge-\d+\.\d+(?:\.\d+)?-(\d+\.\d+[\.\d]*)-universal",
        r"(?:neo)?forge[^\n]{0,24}?version[:\s]+(\d+\.\d+[\.\d]*)",
        r"\|(?:neo)?forge\s*\|\s*(\d+\.\d+[\.\d]*)",
    ):
        m = re.search(pat, joined, re.I)
        if m:
            env["forge"] = m.group(1)
            break

    # Crash reports state the failure in one line. It is the best single
    # summary available and it is present in every real report.
    m = re.search(r"^Description:\s*(.+)$", joined, re.M)
    if m:
        env["description"] = m.group(1).strip()

    # The first exception line after the description is the real throwable.
    m = re.search(
        r"^Description:.*\n+\s*((?:[\w$]+\.)+[\w$]*(?:Error|Exception)[^\n]*)",
        joined,
        re.M,
    )
    if m:
        env["exception"] = truncate(m.group(1).strip(), 180)

    m = re.search(r"Java Version:\s*([\w\.\+\-]+)", joined) or re.search(
        r"java\.version[=: ]+([\w\.\+\-]+)", joined
    )
    if m:
        env["java"] = m.group(1)

    m = re.search(r"Loading (\d+) mods", joined) or re.search(
        r"(\d+) mods? loaded", joined
    )
    if m:
        env["mod_count"] = m.group(1)

    m = re.search(r"-Xmx(\d+[GgMm])", joined)
    if m:
        env["xmx"] = m.group(1)

    env["started_ok"] = "yes" if re.search(r'Done \([\d\.]+s\)', "\n".join(lines)) else "no"

    culprit = blame_mod(lines)
    if culprit:
        env["culprit_jar"] = culprit["jar"]
        env["culprit_symbol"] = culprit["symbol"]
    return env


def diagnose(lines: List[str]) -> List[Finding]:
    """Run every rule over the log and return deduplicated findings."""
    whole = "\n".join(lines)
    found: Dict[str, Finding] = {}

    # Pre-filter on requires/unless once, not per line.
    active = []
    for rule in RULES:
        if rule.requires and not re.search(rule.requires, whole, re.I):
            continue
        if rule.unless and re.search(rule.unless, whole, re.I):
            continue
        active.append(rule)

    # ONE pass over the log. Each rule drops out as soon as it hits, so a long
    # log costs lines x remaining-patterns, not lines x every-pattern. Scanning
    # per pattern instead (the obvious way) re-reads the whole file ~70 times
    # and takes minutes on a real debug.log.
    remaining = list(active)
    for i, line in enumerate(lines, start=1):
        if not remaining:
            break
        still: List[Rule] = []
        for rule in remaining:
            hit = None
            for pat in rule._compiled:
                m = pat.search(line)
                if m:
                    hit = m
                    break
            if hit is not None:
                groups = {k: v for k, v in (hit.groupdict() or {}).items() if v}
                # First hit wins -- causes precede effects in a log.
                found[rule.id] = Finding(rule, i, line.strip(), groups)
            else:
                still.append(rule)
        remaining = still

    order = {FATAL: 0, ERROR: 1, WARN: 2, INFO: 3}
    return sorted(
        found.values(),
        key=lambda f: (order.get(f.rule.severity, 9), -f.rule.weight, f.line_no),
    )


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

BAR = "=" * 72
THIN = "-" * 72


def truncate(s: str, n: int = 160) -> str:
    s = s.strip()
    return s if len(s) <= n else s[: n - 1] + "…"


FIX_URL = "https://jaakoby.github.io/fix/%s.html"


def render_text(path: str, env: Dict[str, Optional[str]], findings: List[Finding]) -> str:
    out = io.StringIO()
    p = out.write

    p(BAR + "\n")
    p(f" FORGE SERVER DOCTOR {VERSION}\n")
    p(f" {os.path.basename(path)}\n")
    p(BAR + "\n\n")

    p("ENVIRONMENT\n")
    p(THIN + "\n")
    rows = [
        ("Minecraft", env["minecraft"]),
        ("Loader", env["forge"]),
        ("Java", env["java"]),
        ("Mods", env["mod_count"]),
        ("Heap (-Xmx)", env["xmx"]),
        ("Reached 'Done'", env["started_ok"]),
    ]
    for label, val in rows:
        p(f"  {label:<16} {val if val else 'not found in log'}\n")
    if env.get("description"):
        p(f"\n  Crash description: {env['description']}\n")
    if env.get("exception"):
        p(f"  Thrown:            {env['exception']}\n")
    if env.get("culprit_jar"):
        p(f"\n  CULPRIT (first non-vanilla frame):\n")
        p(f"    {env['culprit_jar']}\n")
        p(f"    in {env['culprit_symbol']}\n")
    p("\n")

    if not findings:
        p("NO KNOWN FAILURE PATTERN MATCHED\n")
        p(THIN + "\n")
        p(
            "  This log does not contain any of the failure modes this tool knows.\n"
            "  That is not the same as 'nothing is wrong'. Things to check by hand:\n\n"
            "    - Search the log for 'Caused by:' and read the LAST one. That is\n"
            "      usually the real error; everything above it is the wrapper.\n"
            "    - If the server did reach 'Done', the problem is in gameplay, not\n"
            "      startup -- look at the time the issue happened, not the top.\n"
            "    - A native crash (no Java stack trace, no crash-report written)\n"
            "      usually means the JVM itself died. Look for an hs_err_pid file\n"
            "      next to the server jar.\n"
            "\n"
            "  Every failure mode, with what it means and the fix, is written out\n"
            "  here -- search it for the text in your log:\n"
            "    https://jaakoby.github.io/fix/\n"
        )
        return out.getvalue()

    fatal = [f for f in findings if f.rule.severity == FATAL]
    p(f"DIAGNOSIS — {len(findings)} finding(s)")
    if fatal:
        p(f", {len(fatal)} fatal")
    p("\n")
    p(THIN + "\n\n")

    for n, f in enumerate(findings, start=1):
        p(f"[{n}] {f.rule.severity}  {f.rule.title}\n")
        p(f"     rule: {f.rule.id}\n\n")

        if f.groups:
            for k, v in f.groups.items():
                p(f"     {k}: {v}\n")
            p("\n")

        p(f"     Evidence (line {f.line_no}):\n")
        p(f"       {truncate(f.evidence)}\n\n")

        p("     What it means:\n")
        for line in wrap(f.rule.root_cause, 64):
            p(f"       {line}\n")
        p("\n")

        p("     How to fix it:\n")
        for line in f.rule.fix.split("\n"):
            p(f"       {line}\n")
        p("\n")
        p(f"     Full write-up: {FIX_URL % f.rule.id}\n\n")
        if n != len(findings):
            p(THIN + "\n\n")

    p(BAR + "\n")
    if fatal:
        p(" Start with finding [1]. Causes precede effects in a log, and a fatal\n")
        p(" error early on produces a cascade of noise after it.\n")
    else:
        p(" Nothing fatal. The findings above are worth fixing but did not stop\n")
        p(" the server by themselves.\n")
    p(BAR + "\n")
    p(UPGRADE_NOTICE)
    return out.getvalue()


def wrap(text: str, width: int) -> List[str]:
    words = " ".join(text.split()).split(" ")
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


def render_share(path: str, env: Dict[str, Optional[str]],
                 findings: List[Finding]) -> str:
    """A short Markdown block to paste into a forum or help thread.

    People with a broken server do not paste a 400-line crash report — they
    paste a wall of text nobody reads, and the thread dies. This gives them the
    four things anyone helping actually needs: versions, the mod at fault, the
    diagnosis and the fix. It is genuinely more useful to the person answering
    than the raw log.

    The attribution is one line at the end and is theirs to delete. The tool
    earns the mention by having been useful first, or it does not deserve it.
    """
    out = io.StringIO()
    p = out.write

    mc = env.get("minecraft") or "?"
    loader = env.get("loader_version") or "?"
    p(f"**Minecraft {mc} / Forge {loader}**")
    if env.get("mod_count"):
        p(f" · {env['mod_count']} mods")
    if env.get("java"):
        p(f" · Java {env['java']}")
    p("\n\n")

    if env.get("culprit_jar"):
        p(f"**Mod at fault:** `{env['culprit_jar']}`\n")
        if env.get("culprit_symbol"):
            p(f"**In:** `{env['culprit_symbol']}`\n")
        p("\n")

    if findings:
        f = findings[0]
        p(f"**Diagnosis:** {f.rule.title}\n\n")
        p(f"> {' '.join(f.evidence.split())[:300]}\n\n")
        p("**Fix:**\n\n")
        for line in f.rule.fix.split("\n"):
            if line.strip():
                p(f"{line.strip()}\n")
        p("\n")
        if len(findings) > 1:
            p(f"<sub>{len(findings) - 1} further finding(s) not shown.</sub>\n\n")
        p(f"Full write-up: {FIX_URL % f.rule.id}\n\n")
    else:
        p("**No known failure pattern matched.** The culprit above is from the "
          "first non-vanilla stack frame.\n\n")
        p("Every failure mode, with fixes: https://jaakoby.github.io/fix/\n\n")

    p("<sub>Diagnosed with forge-server-doctor (free, no dependencies): "
      "https://github.com/Jaakoby/forge-server-doctor</sub>\n")
    return out.getvalue()




def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="forge_doctor",
        description="Diagnose a Forge/NeoForge Minecraft server log or crash report.",
    )
    ap.add_argument("logfile", nargs="+", help="latest.log, debug.log, or a crash-report (.gz ok)")
    ap.add_argument("--share", action="store_true",
                    help="short Markdown summary to paste into a help thread")
    ap.add_argument("--quiet", action="store_true", help="only print fatal findings")
    ap.add_argument("--version", action="version", version=f"forge-server-doctor {VERSION}")
    args = ap.parse_args(argv)

    exit_code = 0
    for path in args.logfile:
        try:
            lines = read_log(path)
        except FileNotFoundError:
            print(f"error: no such file: {path}", file=sys.stderr)
            exit_code = 2
            continue

        env = environment(lines)
        findings = diagnose(lines)
        if args.quiet:
            findings = [f for f in findings if f.rule.severity == FATAL]

        if args.share:
            print(render_share(path, env, findings))
        else:
            print(render_text(path, env, findings))

        if any(f.rule.severity == FATAL for f in findings):
            exit_code = max(exit_code, 1)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
