#!/usr/bin/env python3
"""Load check: create a map with the mod and run it for some ticks, fail on any error.

Usage:
  python tools/load_check.py --factorio <factorio binary> --zip <mod zip> [--mode plain] [--mode space-age]

--mode plain      only base + the mod
--mode space-age  base + every built-in mod of the install (space-age, quality, elevated-rails, ...) + the mod
--data            the install's data folder (default: <binary>/../../data)
--test-mod DIR    functional tests: DIR (a control.lua, optionally data.lua etc.) is loaded as an extra mod
                  "<mod>-functional-test" (info.json is generated) in every mode, and the benchmark runs at
                  least --test-ticks ticks. The test mod writes log lines "[functional-test] PASS|FAIL ..."
                  and must end with "[functional-test] DONE"; any FAIL or a missing DONE fails the check.

Writes <work>/<mode>/create.log and benchmark.log, and with --summary a Markdown report with the
log excerpt of every failed run. In GitHub Actions it also sets the step outputs factorio_version,
factorio_minor, mod_factorio_version, newer_minor and failed.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ERROR_LINE = re.compile(r"^\s*\d+\.\d+\s+(Error|Fatal)\b|^Error\b|Error while|Failed to load mod", re.I)


def run(cmd, log_path):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    text = proc.stdout.decode("utf-8", "replace")
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return proc.returncode, text


def excerpt(text, limit=60):
    lines = text.splitlines()
    hits = [i for i, l in enumerate(lines) if ERROR_LINE.search(l)]
    if hits:
        keep = set()
        for i in hits[:10]:
            keep.update(range(max(0, i - 3), min(len(lines), i + 15)))
        out = [lines[i] for i in sorted(keep)]
    else:
        out = lines[-limit:]
    return "\n".join(out[:limit * 2])


def builtin_mods(data_dir):
    return sorted(
        d for d in os.listdir(data_dir)
        if d not in ("core", "base") and os.path.isfile(os.path.join(data_dir, d, "info.json"))
    )


def factorio_version(binary):
    out = subprocess.run([binary, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.decode()
    m = re.search(r"Version:\s*(\d+\.\d+\.\d+)", out)
    if not m:
        sys.exit("cannot read the Factorio version:\n" + out)
    return m.group(1)


TEST_TAG = "[functional-test]"


def add_test_mod(mods_dir, test_dir, mod, minor):
    name = mod["name"] + "-functional-test"
    target = os.path.join(mods_dir, name + "_1.0.0")
    shutil.copytree(test_dir, target)
    with open(os.path.join(target, "info.json"), "w", encoding="utf-8") as fh:
        json.dump({"name": name, "version": "1.0.0", "title": name, "author": mod.get("author", ""),
                   "factorio_version": minor, "dependencies": [mod["name"]]}, fh, indent=2)
    return name


def check_mode(binary, data_dir, zip_path, mod, mode, work, ticks, test_dir=None, minor=None):
    """Returns (ok, problems, log text of the failed step)."""
    base = os.path.join(work, mode)
    shutil.rmtree(base, ignore_errors=True)
    mods_dir = os.path.join(base, "mods")
    os.makedirs(mods_dir)
    shutil.copy(zip_path, mods_dir)
    enabled = mode == "space-age"
    builtins = builtin_mods(data_dir)
    if enabled and "space-age" not in builtins:
        return False, ["this Factorio install has no space-age mod"], ""
    mod_list = [{"name": "base", "enabled": True}, {"name": mod["name"], "enabled": True}]
    if test_dir:
        mod_list.append({"name": add_test_mod(mods_dir, test_dir, mod, minor), "enabled": True})
    mod_list += [{"name": b, "enabled": enabled} for b in builtins]
    with open(os.path.join(mods_dir, "mod-list.json"), "w", encoding="utf-8") as fh:
        json.dump({"mods": mod_list}, fh, indent=2)

    map_path = os.path.join(base, "load-check.zip")
    steps = [
        ("create", [binary, "--create", map_path, "--mod-directory", mods_dir]),
        ("benchmark", [binary, "--benchmark", map_path, "--benchmark-ticks", str(ticks), "--mod-directory", mods_dir]),
    ]
    for step, cmd in steps:
        code, text = run(cmd, os.path.join(base, step + ".log"))
        problems = []
        if code != 0:
            problems.append(f"{step}: exit code {code}")
        errors = [l.strip() for l in text.splitlines() if ERROR_LINE.search(l)]
        if errors:
            problems.append(f"{step}: {len(errors)} error line(s), first: {errors[0]}")
        if not re.search(r"Checksum of " + re.escape(mod["name"]) + r":", text):
            problems.append(f"{step}: mod {mod['name']} was not loaded")
        if step == "benchmark" and not re.search(r"Performed %d updates" % ticks, text):
            problems.append(f"benchmark: no 'Performed {ticks} updates' line")
        if step == "benchmark" and test_dir:
            fails = [l.strip() for l in text.splitlines() if TEST_TAG + " FAIL" in l]
            passes = [l for l in text.splitlines() if TEST_TAG + " PASS" in l]
            if fails:
                problems.append(f"functional test: {len(fails)} failure(s), first: {fails[0]}")
            if not any(TEST_TAG + " DONE" in l for l in text.splitlines()):
                problems.append(f"functional test: no '{TEST_TAG} DONE' line (test did not finish in {ticks} ticks)")
            print(f"    functional test: {len(passes)} passed, {len(fails)} failed")
        if problems:
            return False, problems, text
    return True, [], ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factorio", required=True, help="path to the factorio binary")
    ap.add_argument("--zip", required=True, help="the built mod zip")
    ap.add_argument("--data", help="data folder of the install")
    ap.add_argument("--mode", action="append", choices=["plain", "space-age"])
    ap.add_argument("--ticks", type=int, default=600)
    ap.add_argument("--work", help="work folder (default: a temporary folder)")
    ap.add_argument("--summary", help="write a Markdown report here")
    ap.add_argument("--test-mod", help="folder of the functional test mod (see above)")
    ap.add_argument("--test-ticks", type=int, default=3600)
    args = ap.parse_args()

    binary = os.path.abspath(args.factorio)
    data_dir = args.data or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(binary))), "data")
    work = os.path.abspath(args.work or tempfile.mkdtemp(prefix="load-check-"))
    with zipfile.ZipFile(args.zip) as z:
        info_name = next(n for n in z.namelist() if n.count("/") == 1 and n.endswith("/info.json"))
        mod = json.loads(z.read(info_name).decode("utf-8"))

    version = factorio_version(binary)
    minor = ".".join(version.split(".")[:2])
    mod_minor = mod.get("factorio_version", "0.0")
    newer = tuple(map(int, minor.split("."))) > tuple(map(int, mod_minor.split(".")))
    print(f"Factorio {version}, {mod['name']} {mod['version']} (factorio_version {mod_minor})")

    report = [f"Load check of **{mod['name']} {mod['version']}** (factorio_version {mod_minor}) "
              f"against Factorio **{version}**.", ""]
    if newer:
        report += [f"Factorio {minor} is newer than the mod's factorio_version {mod_minor}.", ""]
    failed = False
    for mode in args.mode or ["plain"]:
        ticks = max(args.ticks, args.test_ticks) if args.test_mod else args.ticks
        test_dir = os.path.abspath(args.test_mod) if args.test_mod else None
        ok, problems, text = check_mode(binary, data_dir, args.zip, mod, mode, work, ticks, test_dir, minor)
        print(f"[{mode}] {'OK' if ok else 'FAILED'}")
        for p in problems:
            print("   ", p)
        report.append(f"- `{mode}`: {'OK' if ok else 'failed'}")
        report += [f"  - {p}" for p in problems]
        if not ok:
            failed = True
            report += ["", f"<details><summary>Log excerpt ({mode})</summary>", "", "```",
                       excerpt(text), "```", "", "</details>", ""]

    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as fh:
            fh.write("\n".join(report) + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"factorio_version={version}\nfactorio_minor={minor}\nmod_factorio_version={mod_minor}\n"
                     f"newer_minor={'true' if newer else 'false'}\nfailed={'true' if failed else 'false'}\n")
    print("logs in", work)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
