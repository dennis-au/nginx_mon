# nginx_mon

`nginx-mon` is a real-time terminal monitor for Nginx reverse-proxy traffic.
It tails one dedicated JSON access log and groups recent requests by frontend
virtual host. Select a frontend row to inspect the requests that produced its
upstream traffic.

## What It Measures

The main table displays one live row per `scheme://host` frontend URL:

- request count in the current 60-second rolling window;
- backend TX/s and RX/s, plus totals for that same window;
- TLS state, source endpoints, NetworkManager connections, and selected backend endpoints;
- a bounded recent-request history for the detail screen.

The monitor maps Nginx variables as follows:

| Monitor value | Nginx variable | Meaning |
| --- | --- | --- |
| Backend TX | `$upstream_bytes_sent` | Bytes Nginx sent to the upstream backend. |
| Backend RX | `$upstream_bytes_received` | Bytes Nginx received from the upstream backend. |
| Client request bytes | `$request_length` | Complete request bytes received by Nginx. |
| Client response bytes | `$bytes_sent` | Response bytes sent by Nginx to the client. |
| Latency | `$request_time` | Full request processing time in seconds. |
| Source IP/port | `$remote_addr`, `$remote_port` | TCP peer address and port seen by Nginx. |
| Network connection | `$server_addr`, NetworkManager | Active connection for the Nginx listener address, such as `ens18`. |
| Frontend port | `$server_port` | Nginx listener port that accepted the request. |
| TLS state | `$ssl_protocol` | TLS protocol for HTTPS, or `Plain` when it is empty. |

Nginx can report comma-separated upstream values when it retries a request.
`nginx-mon` sums backend TX/RX values across those attempts. It displays the
request URL as the logged URI, including query parameters. For a retry chain,
the detail view retains the complete `$upstream_addr` value and shows the final
upstream endpoint as the selected backend IP:port.

`$remote_addr` is the direct TCP peer. When Nginx sits behind another load
balancer, configure Nginx's real IP module before logging so this field records
the original client address.

`nginx-mon` resolves `$server_addr` with `ip` and `nmcli` every 30 seconds. It
shows the active NetworkManager connection name in the main and detail tables;
when NetworkManager does not own the interface, it falls back to the interface
name. A missing local address or unavailable host tools is displayed as `-`.

## Installation

Install the produced RPM on CentOS Stream 9 / RHEL 9 compatible x86_64 hosts:

```bash
sudo dnf install ./nginx_mon-0.6.0-1.el9.x86_64.rpm
```

The installed files are:

```text
/usr/bin/nginx-mon
/usr/share/nginx-mon/nginx_mon.conf
/usr/share/man/man1/nginx-mon.1.gz
```

The executable bundles its Python dependencies. The target host does not need
a project Python environment.

## Nginx Setup

### Manage the global default

On a host with a running Nginx master, this is the quickest safe setup:

```bash
sudo nginx-mon --enable-global-json-log
nginx-mon --log-file /var/log/nginx/nginx-mon-access.json.log
```

The command obtains the running master's executable from `/proc`, uses
`nginx -V` to find its compiled main configuration path, then adds one marked
include to that file's top-level `http` block. The included fragment is placed
next to the main configuration file and writes a JSON mirror to
`/var/log/nginx/nginx-mon-access.json.log`. Existing global `access_log`
directives remain unchanged. The command runs `nginx -t` and sends HUP to the
same master only after validation succeeds.

Use the explicit log path until the first request creates a valid JSON record;
after that, ordinary `nginx-mon` autodetection will find it.
For process-control safety, the command only manages a master owned by the
same effective user as `nginx-mon`; the ordinary root-run Nginx service should
therefore be managed with `sudo`.

Use a writable existing directory for a source-built Nginx or a nonstandard
log location:

```bash
sudo nginx-mon --enable-global-json-log \
  --global-log-path /usr/local/nginx/logs/nginx-mon-access.json.log
```

Disable only the fragment that nginx-mon created, while retaining the original
default logging configuration:

```bash
sudo nginx-mon --disable-global-json-log
```

For an interactive one-control workflow, use the toggle command. It enables
the managed JSON mirror when absent and disables it when present:

```bash
sudo nginx-mon --toggle-global-json-log
```

Pass `--global-log-path PATH` with the toggle when turning it on for a
nonstandard Nginx log directory.

This is a global **default**. A `server` or `location` with its own
`access_log` directive does not inherit it; add the supplied JSON `access_log`
to that scope when you need to monitor that traffic.

### Add a specific virtual host

Copy the provided sample into Nginx's included configuration directory, then
replace `api.lab.test` and the upstream address with the deployed values.

```bash
sudo install -m 0644 /usr/share/nginx-mon/nginx_mon.conf \
  /etc/nginx/conf.d/nginx-mon.conf
sudo nginx -t
sudo systemctl reload nginx
```

The sample writes its monitor log to
`/var/log/nginx/nginx-mon-access.json.log`. It uses `log_format ... escape=json`
so request URLs and Host headers remain valid JSON. Its port 8080 listener is
plain HTTP; an SSL-enabled Nginx server automatically reports its protocol
through `$ssl_protocol`.

## Usage

```bash
nginx-mon
nginx-mon --log-file /var/log/nginx/nginx-mon-access.json.log
nginx-mon --detect-nginx  # explicit form of the default autodetection
nginx-mon --nginx-pid 1234
sudo nginx-mon --enable-global-json-log
sudo nginx-mon --disable-global-json-log
sudo nginx-mon --toggle-global-json-log
nginx-mon --refresh-interval 0.5 --max-records 10000
```

The monitor uses Textual's Monokai theme by default. Use Up/Down to move
through table rows, Enter or click to view a frontend's requests, Escape to
return, `p` to pause or resume live updates (freezing the current display),
`r` to refresh, and `q` or Ctrl-C to quit. The command palette does not offer
screenshot saving. The main screen also has a `Global JSON Log` switch. It
uses the same safe managed toggle as the command line; it is disabled with the
reason in its tooltip when the current user cannot manage the running Nginx
master.

## Source-Built Nginx

The monitor does not depend on an RPM, a specific Nginx prefix, or systemd.
For a source-built Nginx whose main configuration has a top-level `http`
block, `sudo nginx-mon --enable-global-json-log --global-log-path PATH`
manages the global default as above. It discovers the compiled main-config
path using that running master's executable, not `systemctl` or an RPM path.
For a virtual host with its own `access_log`, add the supplied JSON
`log_format` to its existing `http` block and the matching `access_log`
directive to the deployed proxy server. Do not copy the sample's test `server`
block into an existing vhost. Choose a writable, readable local log path under
the installation's own prefix.

By default, nginx-mon locates the running Nginx process and its one open,
nonempty log that matches the monitor JSON contract. Start it with:

```bash
nginx-mon
```

Discovery reads the running master and worker descriptors under `/proc`; it
does not execute Nginx or parse configuration includes. If multiple master
processes run, select one with `--nginx-pid PID`. If the log is empty, multiple
matching logs are open, `/proc` is restricted, or Nginx writes to syslog,
journald, stdout, or a pipe, pass the path explicitly with `--log-file`.
An ordinary combined-format `access.log` is not sufficient: configure the
nginx-mon JSON `log_format` and matching `access_log`, then send a request
before starting the monitor.

The account running `nginx-mon` must be able to read both `/proc/<pid>/fd` and
the log file. The supplied `$ssl_protocol` field requires Nginx's HTTP SSL
module; omit that JSON key for a plaintext-only build, which the monitor shows
as `Plain`.

## CentOS 9 Lab Test

On a CentOS Stream 9 lab host, install the build and proxy tools:

```bash
sudo dnf install -y git python3 python3-pip python3-devel gcc make \
  redhat-rpm-config rpm-build nginx curl httpd-tools
```

Create an isolated build environment and run the tests:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e . pytest pyinstaller
.venv/bin/python -m pytest
```

Start a test backend, install the sample configuration, and generate traffic:

```bash
nohup python3 -m http.server 18081 --directory /usr/share/nginx/html \
  >/var/log/nginx-mon-backend.log 2>&1 &
sudo setsebool -P httpd_can_network_connect 1
sudo install -m 0644 packaging/nginx_mon.conf /etc/nginx/conf.d/nginx-mon.conf
sudo nginx -t
sudo systemctl enable --now nginx
curl -H 'Host: api.lab.test' http://127.0.0.1:8080/
ab -n 20 -c 2 -H 'Host: api.lab.test' http://127.0.0.1:8080/
nginx-mon --log-file /var/log/nginx/nginx-mon-access.json.log
```

## RPM Build

Run this on CentOS Stream 9 after committing the source files:

```bash
mkdir -p ~/rpmbuild/SOURCES
git archive --format=tar.gz --prefix=nginx_mon-0.6.0/ \
  -o ~/rpmbuild/SOURCES/nginx_mon-0.6.0.tar.gz HEAD
rpmbuild -bb packaging/nginx_mon.spec
```

The resulting artifact is under
`~/rpmbuild/RPMS/x86_64/nginx_mon-0.6.0-1.el9.x86_64.rpm`.

Verify and install it:

```bash
rpm -qpl ~/rpmbuild/RPMS/x86_64/nginx_mon-0.6.0-1.el9.x86_64.rpm
rpm -qpR ~/rpmbuild/RPMS/x86_64/nginx_mon-0.6.0-1.el9.x86_64.rpm
sudo dnf install -y ~/rpmbuild/RPMS/x86_64/nginx_mon-0.6.0-1.el9.x86_64.rpm
/usr/bin/nginx-mon --help
```

## Development

The parser, rolling aggregation, file follower, CLI, and Textual table have
focused pytest coverage. Run all tests with:

```bash
.venv/bin/python -m pytest
```
