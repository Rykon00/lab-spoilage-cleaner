#!/usr/bin/env python3
"""Build the mod zip <name>_<version>.zip (with a <name>_<version>/ folder) from the repository.

Usage:
  python tools/build.py [--out DIR]          build the zip (default: dist/), print its path
  python tools/build.py --check-release TAG  check TAG == "v" + info.json version and that
                                             changelog.txt has that version with a date
  python tools/build.py --notes [VERSION]    print the changelog.txt section of VERSION (default: info.json
                                             version) as Markdown release notes
"""
import argparse
import json
import os
import re
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Top-level entries that are not part of the mod (".git*" covers .git, .github, .gitignore, .gitattributes).
EXCLUDE_TOP = {"tools", "tests", "dist", "CLAUDE.md"}
# Editor folders, at any depth.
EXCLUDE_DIRS = {".vscode", ".idea"}


def info():
    with open(os.path.join(ROOT, "info.json"), encoding="utf-8") as fh:
        return json.load(fh)


def mod_files():
    for top in sorted(os.listdir(ROOT)):
        if top.startswith(".git") or top in EXCLUDE_TOP or top in EXCLUDE_DIRS:
            continue
        path = os.path.join(ROOT, top)
        if os.path.isfile(path):
            yield top
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
            for f in sorted(filenames):
                yield os.path.relpath(os.path.join(dirpath, f), ROOT).replace(os.sep, "/")


def build(out_dir):
    meta = info()
    folder = f"{meta['name']}_{meta['version']}"
    os.makedirs(out_dir, exist_ok=True)
    target = os.path.join(out_dir, folder + ".zip")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        dirs = set()
        for rel in mod_files():
            parts = rel.split("/")[:-1]
            for i in range(len(parts)):
                d = "/".join(parts[: i + 1])
                if d not in dirs:
                    dirs.add(d)
                    z.write(os.path.join(ROOT, d), f"{folder}/{d}/")
            z.write(os.path.join(ROOT, rel), f"{folder}/{rel}")
    return target


def check_release(tag):
    meta = info()
    errors = []
    if tag != "v" + meta["version"]:
        errors.append(f"tag {tag} does not match info.json version {meta['version']} (expected v{meta['version']})")
    with open(os.path.join(ROOT, "changelog.txt"), encoding="utf-8") as fh:
        changelog = fh.read()
    m = re.search(r"^Version: " + re.escape(meta["version"]) + r"[ \t]*\r?\n(.*?)(?=^-{20,}|\Z)", changelog, re.S | re.M)
    if not m:
        errors.append(f"changelog.txt has no section 'Version: {meta['version']}'")
    elif not re.search(r"^Date:[ \t]*\S*\d", m.group(1), re.M):
        errors.append(f"changelog.txt section {meta['version']} has no 'Date:' line with a date")
    for e in errors:
        print("error:", e, file=sys.stderr)
    return not errors


def notes(version):
    with open(os.path.join(ROOT, "changelog.txt"), encoding="utf-8") as fh:
        changelog = fh.read().replace("\r\n", "\n")
    m = re.search(r"^Version: " + re.escape(version) + r"[ \t]*\n(.*?)(?=^-{20,}|\Z)", changelog, re.S | re.M)
    if not m:
        sys.exit(f"changelog.txt has no section 'Version: {version}'")
    out = []
    for line in m.group(1).splitlines():
        if line.startswith("Date:") or not line.strip():
            continue
        if re.match(r"^  \S.*:\s*$", line):
            out.append(f"### {line.strip().rstrip(':')}")
        else:
            out.append(re.sub(r"^    - ", "- ", re.sub(r"^      ", "  ", line)))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "dist"))
    ap.add_argument("--check-release", metavar="TAG")
    ap.add_argument("--notes", nargs="?", const="", metavar="VERSION")
    args = ap.parse_args()
    if args.check_release is not None:
        sys.exit(0 if check_release(args.check_release) else 1)
    if args.notes is not None:
        print(notes(args.notes or info()["version"]))
        return
    print(build(args.out))


if __name__ == "__main__":
    main()
