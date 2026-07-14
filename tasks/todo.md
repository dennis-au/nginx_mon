# nginx_mon Delivery Checklist

## 0. CentOS 9 Lab Bootstrap

- [x] Confirm `root@192.168.0.101` accepts SSH with the original credentials.
- [x] Verify CentOS Stream 9, x86_64, Python 3.9, RPM, and SELinux enforcing mode.
- [x] Repair the minimal installation's missing DNS resolver configuration.
- [x] Install Git, Python build tools, RPM build tools, Nginx, curl, and ApacheBench.
- [x] Copy the working tree to `/root/nginx_mon`.
- [x] Create `/root/nginx_mon/.venv` and install Textual 0.89.1, pytest 8.4.2, and PyInstaller 6.21.0.

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
- [x] Run a manual terminal smoke test on `192.168.0.101`.

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
- [x] Install the binary in `/usr/bin/nginx-mon` from the RPM.
- [x] Install the Nginx sample under `/usr/share/nginx-mon/` from the RPM.
- [x] Install the compressed man page from the RPM.
- [x] Build the RPM on `192.168.0.101`.
- [x] Verify RPM contents and dependencies with `rpm -qpl` and `rpm -qpR`.
- [x] Install the RPM and confirm the binary runs without the project virtual environment.

## 5. End-to-End Lab Validation

- [x] Install and start Nginx on `192.168.0.101`.
- [x] Start a local HTTP test backend on `192.168.0.101`.
- [x] Configure Nginx to proxy to the test backend and enable the monitor log format.
- [x] Generate requests through the Nginx frontend with `curl` and ApacheBench.
- [x] Verify live table rows show frontend URL and nonzero backend TX/RX.
- [x] Open a row and verify all per-request details against the access log.
- [x] Record the matching RPM artifacts: `/root/rpmbuild/RPMS/x86_64/nginx_mon-0.3.0-1.el9.x86_64.rpm` and `artifacts/nginx_mon-0.3.0-1.el9.x86_64.rpm`.

## 6. Quality and Source Control

- [x] Run the complete test suite on the lab host.
- [x] Review the final diff for correctness, security, readability, and performance.
- [x] Confirm no credentials, build outputs, or virtual environments are tracked.
- [x] Commit each completed implementation slice with a descriptive message.
- [x] Push the branch and verify the GitHub remote contains source, spec, and build instructions.
