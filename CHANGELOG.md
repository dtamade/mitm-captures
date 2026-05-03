# Changelog

All notable changes to this project will be documented in this file.

## v0.1.1 - 2026-05-03

This patch release updates the public release line from the original `v0.1.0` tag to the current, fully verified cross-platform state.

- Added real GitHub Actions smoke validation on `ubuntu-latest`, `macos-latest`, and `windows-latest`.
- Hardened the native Windows batch entrypoint for `install/start/stop/status/ai/cert`.
- Fixed multiple Windows-specific process-launch, state-loading, and encoding edge cases found by real CI.
- Added dedicated static and unit coverage for Windows batch behavior, manifest/BOM handling, and runtime smoke I/O.
- Upgraded GitHub Actions workflow dependencies and tightened default workflow permissions.

## v0.1.0 - 2026-05-03

Initial public release.

- Linux/macOS shell entrypoints for start/stop/analyze.
- Native Windows single-file batch entrypoint.
- `latest.*` artifacts plus AI-ready bundle generation.
