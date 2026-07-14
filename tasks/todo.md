# nginx_mon Delivery Checklist

## 1. Project and Data Foundation

- [x] Create the `codex/nginx-mon-prototype` branch and configure the GitHub remote.
- [x] Define typed request and frontend-summary data models.
- [x] Define the Nginx JSON access-log field contract.
- [x] Parse `time`, virtual host, request URL, method, status, and upstream address.
- [x] Parse backend TX from `$upstream_bytes_sent`, including multiple attempts.
- [x] Parse backend RX from `$upstream_bytes_received`, including missing values.
- [x] Parse client request/response byte fields and request latency.
- [x] Reject malformed or incomplete log lines without stopping the monitor.
- [x] Retain a bounded in-memory request history.
- [x] Aggregate request counts and backend TX/RX rates by frontend URL.
- [x] Follow complete appended log lines exactly once.
- [x] Continue after partial writes, log truncation, and log rotation.
- [x] Add focused parser, aggregation, and follower tests.

## 2. Textual Monitor

- [x] Install the declared Textual version on `192.168.0.101`.
- [x] Add the `nginx-mon` command-line entry point and argument validation.
- [x] Add a main Textual screen with a log-status line and live traffic table.
- [x] Show frontend URL, request count, backend TX/s, backend RX/s, and byte totals.
- [x] Refresh the table from the access log on a fixed interval.
- [x] Show an informative waiting/error state when the log cannot be read.
- [x] Support Up/Down navigation, Enter/click selection, `r` refresh, and `q`/Ctrl-C quit.
- [x] Add a detail screen for the selected frontend URL.
- [x] Show timestamp, request URI, method, status, upstream, TX/RX, and latency per request.
- [x] Support Escape to return from the detail screen.
- [x] Add a Textual pilot test for table and detail navigation.
- [x] Run the Textual test on `192.168.0.101`.
- [ ] Run a manual terminal smoke test on `192.168.0.101`.

## 3. Nginx Configuration and Documentation

- [x] Add an Nginx `log_format` snippet with JSON escaping and all required variables.
- [x] Add a sample reverse-proxy server block that writes the monitor log.
- [x] Add a minimal test backend setup and traffic-generation commands.
- [x] Document monitor installation, command-line options, and key bindings.
- [x] Explain the TX/RX variable mapping and 60-second rolling-rate behavior.
- [x] Add a `nginx-mon(1)` man page.

## 4. Binary and RPM Packaging

- [x] Add a PyInstaller build command that produces one x86_64 executable.
- [x] Add `.spec` metadata, build prerequisites, and source-tarball instructions.
- [x] Define installation of the binary in `/usr/bin/nginx-mon` from the RPM.
- [x] Define installation of the Nginx sample under `/usr/share/nginx-mon/` from the RPM.
- [x] Define installation of the compressed man page from the RPM.
- [ ] Build the RPM on `192.168.0.101`.
- [ ] Verify RPM contents and dependencies with `rpm -qpl` and `rpm -qpR`.
- [ ] Install the RPM and confirm the binary runs without the project virtual environment.

## 5. End-to-End Lab Validation

- [ ] Install and start Nginx on `192.168.0.101`.
- [ ] Start a local HTTP test backend on `192.168.0.101`.
- [ ] Configure Nginx to proxy to the test backend and enable the monitor log format.
- [ ] Generate requests through the Nginx frontend with `curl` or `ab`.
- [ ] Verify live table rows show frontend URL and nonzero backend TX/RX.
- [ ] Open a row and verify all per-request details against the access log.
- [ ] Record the final RPM artifact path and installation-test result.

## 6. Quality and Source Control

- [ ] Run the complete test suite on the lab host.
- [ ] Review the final diff for correctness, security, readability, and performance.
- [ ] Confirm no credentials, build outputs, or virtual environments are tracked.
- [ ] Commit each completed implementation slice with a descriptive message.
- [ ] Push the branch and verify the GitHub remote contains source, spec, and build instructions.
