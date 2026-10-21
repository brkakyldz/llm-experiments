# Changelog

All notable changes to this project are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions: [SemVer](https://semver.org/).

## [Unreleased]

### Added
- `explanation-sways-judge`: an LLM judge graded 40 support replies bare and with the agent's
  explanation, 240 calls, every grade checked by a second model. Code, design, all recorded runs
  (pilots and trial included), offline replay, tests and the trace viewer.

### Changed
- A new look for the repo: light frosted-glass panels with a small robot avatar made with an
  image model. The README banner shows the project and how every experiment is run (record,
  grade, check, replay), rendered from `assets/src/`; experiments are listed in a table. Both experiments have their images and trace viewers in the same style, and the
  viewers embed Geist (SIL OFL 1.1) as their fallback font.

## [0.1.0] - 2026-10-15

### Added
- `said-vs-did`: a support agent graded three ways (LLM judge, outcome check, trajectory rules) on
  a deliberately loose tool harness. Code, design, all 11 recorded runs, offline replay, tests and
  a LangSmith-style HTML trace viewer.
