# Implementation Plan: nginx_mon

## Overview

`nginx-mon` is a local Textual terminal application that tails a dedicated
Nginx JSON access log, aggregates upstream traffic by frontend virtual host,
and exposes recent requests in a selectable detail screen.

## Architecture Decisions

- Use an Nginx `log_format ... escape=json` contract. JSON avoids ambiguity in
  quoted request URIs and supports robust handling of Nginx's `-` values.
- Keep the recent request history bounded in memory; this is a live monitor,
  not a long-term log index.
- Poll the access-log file directly, handling truncation and rotation without
  invoking `tail` as a child process.
- Bundle the Python application with PyInstaller during RPM builds so installed
  hosts need only the resulting `nginx-mon` executable.

## Dependency Graph

```text
Nginx JSON log contract
  -> parser and request model
    -> file follower and aggregation store
      -> Textual table and request detail screen
        -> CLI, documentation, PyInstaller, RPM
          -> CentOS 9 proxy traffic verification
```

## Task List

### Phase 1: Data Foundation

- [x] Task 1: Define request/summary models and parse the Nginx JSON log.
  Acceptance: valid records parse; missing upstream values and malformed input
  are handled safely; upstream byte lists are summed.
  Verification: focused parser tests.
- [x] Task 2: Follow a log file across appends, truncation, and rotation, and
  aggregate a bounded rolling request history.
  Acceptance: new lines are read once; rotation does not stall monitoring;
  frontend summaries expose request count and backend TX/RX rates.
  Verification: focused follower/store tests.

### Checkpoint: Foundation

- [x] Unit tests pass and the package can be imported.

### Phase 2: Interactive Monitor

- [x] Task 3: Build the Textual main screen with periodically refreshed
  frontend summary rows and refresh/quit bindings.
  Acceptance: table displays frontend URL, request count, backend TX/RX rates,
  and a readable log status.
  Verification: application smoke test plus model-driven UI unit tests.
- [x] Task 4: Add the selectable per-frontend request detail screen.
  Acceptance: Enter/click opens method, path, status, upstream, TX/RX, and
  latency for retained requests; Escape returns to the live table.
  Verification: Textual pilot test.

### Checkpoint: Interactive Monitor

- [x] Full CentOS 9 test suite passes; the installed TUI opens against a live proxy log.

### Phase 3: Packaging and Lab Validation

- [x] Task 5: Add the Nginx format/proxy sample, README, man page, PyInstaller
  build flow, and RPM spec.
  Acceptance: instructions configure a test proxy and produce an x86_64 RPM.
  Verification: documentation command review and package syntax checks.
- [x] Task 6: Build the RPM on CentOS Stream 9, install it, generate proxied
  traffic, and capture evidence that the monitor parses the live log.
  Acceptance: installed executable works without a project Python environment;
  the RPM contains the binary, Nginx sample, and man page.
  Verification: `rpm -ql`, executable help/smoke checks, and real proxy log.

### Checkpoint: Complete

- [x] Tests, build, TUI smoke test, RPM build, and installation test pass.
- [ ] Incremental commits are pushed to the configured GitHub remote.

## Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Nginx upstream variables can contain `-` or multiple attempts | Medium | Treat fields as untrusted strings and parse numbers defensively. |
| Log rotation can drop a file descriptor | Medium | Detect inode changes and truncation on each poll. |
| PyInstaller behavior differs on EL9 | High | Build and install-test on the supplied CentOS 9-compatible host. |
| RPM build dependencies may not be installed | Medium | Document and install only explicit build prerequisites on the lab host. |
