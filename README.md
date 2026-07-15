# nginx-mon

`nginx-mon` is a real-time terminal monitor for Nginx reverse-proxy traffic.
It tails a dedicated JSON access log, groups recent requests by frontend URL,
and shows the upstream traffic that Nginx actually exchanged with backends.

It is designed for CentOS Stream 9 / RHEL 9 compatible x86_64 hosts and is
distributed as a self-contained executable and RPM. The target does not need a
Python environment.

## What You See

Each frontend row represents one `scheme://host` URL over a rolling 60-second
window:

- request count, backend TX/s and RX/s, and rolling byte totals;
- listener network connection, TLS protocol, client source endpoints, and
  selected upstream endpoints;
- a request detail view with method, URI, status, source IP:port, listener,
  backend IP:port, upstream retry chain, bytes, and latency.

`Backend TX` is `$upstream_bytes_sent`: bytes Nginx sent to the upstream.
`Backend RX` is `$upstream_bytes_received`: bytes Nginx received from it.
When Nginx retries an upstream, nginx-mon sums the byte values across attempts
and retains the complete upstream chain in the detail view.

## Install

Download the matching `nginx_mon-<version>-1.el9.x86_64.rpm` from the
[releases page](https://github.com/dennis-au/nginx_mon/releases), then install
it on the Nginx host:

```bash
sudo dnf install ./nginx_mon-0.6.0-1.el9.x86_64.rpm
nginx-mon --version
```

The RPM installs:

```text
/usr/bin/nginx-mon
/usr/share/nginx-mon/nginx_mon.conf
/usr/share/man/man1/nginx-mon.1.gz
```

The standalone `nginx-mon-<version>-el9-x86_64` release asset can be run
directly on a compatible EL9 host:

```bash
chmod +x nginx-mon-0.6.0-el9-x86_64
./nginx-mon-0.6.0-el9-x86_64 --version
```

## Quick Start

nginx-mon needs one Nginx access log in its JSON format. Choose the setup that
matches your Nginx configuration.

### Global Default Log

For a conventional Nginx installation, enable an additional global JSON log
without replacing the existing access log:

```bash
sudo nginx-mon --enable-global-json-log
nginx-mon --log-file /var/log/nginx/nginx-mon-access.json.log
```

The command finds the running master through `/proc`, uses that executable's
`nginx -V` output to locate its main configuration, then adds one marked include
inside the top-level `http` block. It writes a managed fragment beside the main
configuration, validates with `nginx -t`, and sends HUP only after validation
succeeds. A failed validation restores the previous files.

Use the explicit log path until the first request creates a valid JSON record;
after that, ordinary autodiscovery also works:

```bash
nginx-mon
```

Use a nonstandard writable log directory when needed:

```bash
sudo nginx-mon --enable-global-json-log \
  --global-log-path /usr/local/nginx/logs/nginx-mon-access.json.log
```

The global log is a default only. A `server` or `location` with its own
`access_log` directive does not inherit it. Configure those virtual hosts
explicitly as described next.

### Virtual-Host Log

For an existing proxy virtual host, add the `nginx_mon_json` `log_format` from
[the supplied configuration](packaging/nginx_mon.conf) to the `http` block,
then add this directive in the target `server` or `location` scope:

```nginx
access_log /var/log/nginx/nginx-mon-access.json.log nginx_mon_json;
```

Do not copy the sample's test `server` block into a deployed virtual host.
Validate and reload Nginx, generate one request, then start the monitor with an
explicit path:

```bash
sudo nginx -t
sudo systemctl reload nginx
nginx-mon --log-file /var/log/nginx/nginx-mon-access.json.log
```

The format uses `escape=json`, so quoted paths and headers remain valid JSON.
`$ssl_protocol` is empty for plaintext traffic and appears as `Plain` in the
monitor. Builds without the HTTP SSL module can omit that key.

## Use the Monitor

```bash
nginx-mon
nginx-mon --log-file /path/to/nginx-mon-access.json.log
nginx-mon --nginx-pid 1234
nginx-mon --refresh-interval 0.5 --max-records 10000
```

| Control | Action |
| --- | --- |
| Up/Down, Enter, click | Select a frontend and open its requests |
| Escape | Return to the frontend table |
| `p` | Pause or resume ingestion and freeze the current display |
| `r` | Refresh immediately |
| `q`, Ctrl-C | Quit |
| `Global JSON Log` switch | Toggle nginx-mon's managed global log |

The TUI uses the Monokai theme. Its `Global JSON Log` switch and the commands
below manage only nginx-mon's marked include and fragment. The control is
disabled, with the reason shown in its tooltip, when the current user cannot
safely manage the running Nginx master.

```bash
sudo nginx-mon --enable-global-json-log
sudo nginx-mon --disable-global-json-log
sudo nginx-mon --toggle-global-json-log
```

For process-control safety, the manager only operates on an Nginx master owned
by the same effective user. Use `sudo` for the normal root-owned Nginx service.
Use explicit enable or disable commands in automation; the toggle is intended
for interactive use.

## Log Discovery

With no `--log-file`, nginx-mon locates running Nginx masters via procfs, reads
their master and worker file descriptors, and chooses the one regular file that
contains a valid nginx-mon JSON record. This avoids assumptions about Nginx RPM
paths, systemd units, or source-build prefixes.

Discovery deliberately refuses to guess. Pass `--log-file` when:

- the monitor log is still empty;
- more than one matching JSON log is open;
- `/proc` visibility is restricted;
- Nginx logs to syslog, journald, stdout, or a pipe;
- the log is an ordinary combined-format access log.

`$remote_addr` is Nginx's direct TCP peer. Configure Nginx's real IP module
when Nginx sits behind another load balancer and the original client address is
required. Network connection names come from `$server_addr` via `ip` and
NetworkManager; nginx-mon falls back to the interface name when NetworkManager
does not own it.

## Architecture

```text
Nginx JSON access log
        |
        v
parser -> rotation-aware follower -> bounded rolling store -> Textual TUI
                                                    |
                                                    v
                                      NetworkManager listener resolution
```

The monitor is intentionally a live operational view, not a log archive. It
keeps a bounded request history and polls a local file directly so it can handle
partial writes, truncation, and rename-and-reopen rotation without invoking
`tail` as a child process.

The global log manager is separate from traffic collection. It uses a marked
include rather than rewriting arbitrary virtual-host logging, preserving
existing global access logs and making disable/revert behavior unambiguous.

## Build From Source

Build on CentOS Stream 9 / RHEL 9 compatible x86_64 for a compatible RPM and
single-file executable:

```bash
sudo dnf install -y git python3 python3-pip python3-devel gcc make \
  redhat-rpm-config rpm-build
git clone https://github.com/dennis-au/nginx_mon.git
cd nginx_mon
git checkout v0.6.0

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e . pytest pyinstaller
.venv/bin/python -m pytest

mkdir -p ~/rpmbuild/SOURCES
git archive --format=tar.gz --prefix=nginx_mon-0.6.0/ \
  -o ~/rpmbuild/SOURCES/nginx_mon-0.6.0.tar.gz v0.6.0
rpmbuild -bb packaging/nginx_mon.spec
```

The RPM is written to:

```text
~/rpmbuild/RPMS/x86_64/nginx_mon-0.6.0-1.el9.x86_64.rpm
```

The PyInstaller executable is created in the RPM build tree at:

```text
~/rpmbuild/BUILD/nginx_mon-0.6.0/dist/nginx-mon
```

Verify the packaged output before distribution:

```bash
rpm -qpl ~/rpmbuild/RPMS/x86_64/nginx_mon-0.6.0-1.el9.x86_64.rpm
rpm -qpR ~/rpmbuild/RPMS/x86_64/nginx_mon-0.6.0-1.el9.x86_64.rpm
sudo dnf install -y ~/rpmbuild/RPMS/x86_64/nginx_mon-0.6.0-1.el9.x86_64.rpm
/usr/bin/nginx-mon --version
```

## Project Layout

| Path | Responsibility |
| --- | --- |
| `src/nginx_mon/parser.py` | Nginx JSON contract and upstream byte parsing |
| `src/nginx_mon/tailer.py` | Append, truncation, and rotation-aware file following |
| `src/nginx_mon/store.py` | Bounded request retention and rolling summaries |
| `src/nginx_mon/discovery.py` | Procfs-based master and log discovery |
| `src/nginx_mon/configuration.py` | Safe managed global-log enable, disable, and toggle |
| `src/nginx_mon/app.py` | Textual dashboard and request detail screen |
| `packaging/` | Nginx sample, man page, PyInstaller entry point, and RPM spec |

## Development

Run the focused test suite with:

```bash
.venv/bin/python -m pytest
```

See the [changelog](CHANGELOG.md) for release history.

## License

[MIT](LICENSE)
