# lab-spoilage-cleaner

Factorio mod "Lab Spoilage Cleaner" (portal: https://mods.factorio.com/mod/lab-spoilage-cleaner). The repository root is the mod folder.

## Rules

- English on GitHub: commits, issues, pull requests, comments and release notes.
- Every change adds its lines to the topmost section of `changelog.txt` (Factorio changelog format:
  categories such as `Features:`, `Changes:`, `Bugfixes:`, `Info:`, two-space indent, `- ` entries).
- Do not bump `version` in `info.json` outside a release.
- Test with the CI's load check before pushing (see below). It must pass for every mode in
  `.github/workflows/check.yml` (`LOAD_CHECK_MODES`: plain, space-age).

## Build and load check

```
python tools/build.py                      # -> dist/lab-spoilage-cleaner_<version>.zip
python tools/load_check.py --factorio <path to factorio(.exe)> --zip dist/lab-spoilage-cleaner_<version>.zip --mode plain --mode space-age --test-mod tests/functional-test
```

`tools/build.py` packs everything except `.git*`, `.github/`, `tools/`, `tests/`, `dist/`, `CLAUDE.md` and editor
folders. `tools/load_check.py` puts the zip into a fresh mod folder, enables it (with `--mode space-age` also every
built-in mod: space-age, quality, elevated-rails, recycler), creates a map with `--create`, runs it with
`--benchmark ... --benchmark-ticks 600` and fails on a non-zero exit code, an error line in the log, or when the mod
was not loaded. `--data` points to the install's `data` folder when it is not `<binary>/../../data` (for example a
copied Steam binary).

Functional tests: `tests/functional-test/` is loaded by `--test-mod` as an extra mod
`lab-spoilage-cleaner-functional-test` (info.json generated). It lets agricultural science packs spoil in
labs and checks robots mode (robots carry the spoilage to a storage chest), a lab without network (untouched),
network mode (remote call `clean_lab(lab, "network")`) and a space platform lab (hub). Settings of this mod cannot be
changed by the test mod, so other modes are tested through the remote interface. Without Space Age it only logs a
skip. It logs
`[functional-test] PASS|FAIL ...` and `[functional-test] DONE`; any FAIL or a missing DONE fails the check. Extend it
when the mod's behaviour changes: the automatic port only releases when these tests pass.

## CI

- `check.yml`: on push, pull request and manually: load check + functional tests against the latest stable headless
  Factorio for Linux.
- `port.yml`: weekly (Fridays 15:00 Europe/Berlin) and manually (input `dry_run`). Same minor as `factorio_version`: load check, one issue
  (label `load-check`) on failure. Newer minor: automatic port with `tools/port.py` (factorio_version and built-in
  dependencies to the new minor, mod version minor bump, changelog section; an undated topmost section is released
  with it). If load check and functional tests pass, it commits to main as github-actions[bot], tags `v<version>`,
  creates the GitHub release and calls `release.yml`; otherwise one issue (label `auto-port`) and nothing is committed.
- `release.yml`: on a published GitHub release, or called by `port.yml` with input `tag`. Checks tag = `v` + info.json
  version and a dated changelog section, builds the zip, runs the load check, attaches the zip to the release and
  uploads it to the mod portal with the repository secret `FACTORIO_API_KEY`. If the portal does not know the mod yet
  (`UnknownMod`), it publishes it instead (Mod publish API: `init_publish`, with README.md up to "## Build" as
  description, category and license from `PORTAL_CATEGORY`/`PORTAL_LICENSE` in the workflow and the repo as source
  URL). The key needs the usages "ModPortal: Upload Mods" and "ModPortal: Publish Mods".
- `tools/build.py --notes [VERSION]` prints a changelog section as Markdown (release notes).

## Release

1. Set `version` in `info.json` and the `Date:` of the topmost changelog section (same version), commit, push.
2. Wait for the load check to pass, then publish a GitHub release with tag `v<version>` on `main`.
