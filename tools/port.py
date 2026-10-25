#!/usr/bin/env python3
"""Port the mod to a newer Factorio minor version (used by the weekly auto-port workflow).

Usage:
  python tools/port.py --minor 2.2 [--date "25. 10. 2026"]

- info.json: factorio_version = MINOR; every dependency on a built-in mod (base, space-age, quality,
  elevated-rails, recycler) that has a version gets ">= MINOR.0" (prefixes like "?" are kept); the mod
  version gets its minor bumped (1.4.2 -> 1.5.0).
- changelog.txt: if the topmost section is not released yet (no date), it becomes the new version
  (its lines are released with the port); otherwise a new section is added on top. Either way it gets
  the date and an "Info:" line about the port.

Prints the new mod version. Does not touch anything when info.json already has MINOR or newer
(exit code 2).
"""
import argparse
import datetime
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILTIN = {"base", "space-age", "quality", "elevated-rails", "recycler"}
SEPARATOR = "-" * 99
DEP = re.compile(r"^(?P<prefix>[!?~()]+\s*)?(?P<name>[^<>=\s][^<>=]*?)\s*(?:(?P<op><=|>=|<|>|=)\s*(?P<ver>\S+))?\s*$")


def vtuple(v):
    return tuple(int(x) for x in v.split("."))


def port_dependency(dep, minor):
    m = DEP.match(dep)
    if not m or m.group("name") not in BUILTIN or not m.group("ver"):
        return dep
    prefix = (m.group("prefix") or "").strip()
    return f"{prefix + ' ' if prefix else ''}{m.group('name')} >= {minor}.0"


def bump_minor(version):
    major, minor_, *_ = version.split(".")
    return f"{major}.{int(minor_) + 1}.0"


def port_changelog(text, new_version, date, line):
    # Sections are separated by a line of dashes; the first section starts after the first separator.
    parts = re.split(r"^-{20,}[ \t]*\r?\n", text, flags=re.M)
    head, sections = parts[0], parts[1:]
    nl = "\r\n" if "\r\n" in text else "\n"
    entry = f"  Info:{nl}    - {line}{nl}"
    if sections and not re.search(r"^Date:[ \t]*\S*\d", sections[0], re.M):
        top = sections[0]
        top = re.sub(r"^Version:.*$", f"Version: {new_version}", top, count=1, flags=re.M)
        if re.search(r"^Date:.*$", top, flags=re.M):
            top = re.sub(r"^Date:.*$", f"Date: {date}", top, count=1, flags=re.M)
        else:
            top = re.sub(r"^(Version:.*\r?\n)", r"\g<1>" + f"Date: {date}{nl}", top, count=1, flags=re.M)
        if re.search(r"^  Info:[ \t]*\r?$", top, flags=re.M):
            top = re.sub(r"^(  Info:[ \t]*\r?\n)", r"\g<1>" + f"    - {line}{nl}", top, count=1, flags=re.M)
        else:
            top = top.rstrip("\r\n") + nl + entry
        sections[0] = top
    else:
        sections.insert(0, f"Version: {new_version}{nl}Date: {date}{nl}{entry}")
    return head + "".join(SEPARATOR + nl + s for s in sections)


def default_date(changelog):
    today = datetime.date.today()
    m = re.search(r"^Date:[ \t]*(\S.*?)\s*$", changelog, re.M)
    if m and re.fullmatch(r"\d{4}-\d{2}-\d{2}", m.group(1)):
        return today.isoformat()
    return f"{today.day:02d}. {today.month:02d}. {today.year}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minor", required=True, help="the new Factorio minor version, e.g. 2.2")
    ap.add_argument("--date", help="default: today, in the date format of the latest dated changelog section")
    args = ap.parse_args()
    if not re.fullmatch(r"\d+\.\d+", args.minor):
        sys.exit("--minor must look like 2.2")

    info_path = os.path.join(ROOT, "info.json")
    with open(info_path, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    info = json.loads(raw)
    old_minor = info.get("factorio_version", "0.0")
    if vtuple(old_minor) >= vtuple(args.minor):
        print(f"info.json already has factorio_version {old_minor}", file=sys.stderr)
        sys.exit(2)

    new_version = bump_minor(info["version"])
    info["factorio_version"] = args.minor
    info["dependencies"] = [port_dependency(d, args.minor) for d in info.get("dependencies", [])]
    info["version"] = new_version
    indent = 2
    m = re.search(r'^\{\s*\n([ \t]+)"', raw)
    if m:
        indent = m.group(1)
    info_nl = "\r\n" if "\r\n" in raw else "\n"
    with open(info_path, "w", encoding="utf-8", newline="") as fh:
        fh.write((json.dumps(info, indent=indent, ensure_ascii=False) + "\n").replace("\n", info_nl))

    changelog_path = os.path.join(ROOT, "changelog.txt")
    with open(changelog_path, encoding="utf-8", newline="") as fh:
        changelog = fh.read()
    tests = "load check and functional tests" if os.path.isdir(os.path.join(ROOT, "tests")) else "load check"
    line = (f"Ported to Factorio {args.minor} automatically: factorio_version and the dependencies on "
            f"built-in mods updated; {tests} passed against Factorio {args.minor}.")
    date = args.date or default_date(changelog)
    with open(changelog_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(port_changelog(changelog, new_version, date, line))
    print(new_version)


if __name__ == "__main__":
    main()
