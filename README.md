# nginx_mon

`nginx-mon` is a real-time terminal monitor for Nginx reverse-proxy traffic.
It tails one dedicated JSON access log and groups recent requests by frontend
virtual host. Select a frontend row to inspect the requests that produced its
upstream traffic.

## What It Measures

The main table displays one live row per `scheme://host` frontend URL:

- request count in the current 60-second rolling window;
- backend TX/s and RX/s, plus totals for that same window;
- TLS state, source endpoints, and selected backend endpoints;
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

## Installation

Install the produced RPM on CentOS Stream 9 / RHEL 9 compatible x86_64 hosts:

```bash
sudo dnf install ./nginx_mon-0.2.0-1.el9.x86_64.rpm
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
nginx-mon --refresh-interval 0.5 --max-records 10000
```

Use Up/Down to move through table rows, Enter or click to view a frontend's
requests, Escape to return, `r` to refresh, and `q` or Ctrl-C to quit.

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
git archive --format=tar.gz --prefix=nginx_mon-0.2.0/ \
  -o ~/rpmbuild/SOURCES/nginx_mon-0.2.0.tar.gz HEAD
rpmbuild -bb packaging/nginx_mon.spec
```

The resulting artifact is under
`~/rpmbuild/RPMS/x86_64/nginx_mon-0.2.0-1.el9.x86_64.rpm`.

Verify and install it:

```bash
rpm -qpl ~/rpmbuild/RPMS/x86_64/nginx_mon-0.2.0-1.el9.x86_64.rpm
rpm -qpR ~/rpmbuild/RPMS/x86_64/nginx_mon-0.2.0-1.el9.x86_64.rpm
sudo dnf install -y ~/rpmbuild/RPMS/x86_64/nginx_mon-0.2.0-1.el9.x86_64.rpm
/usr/bin/nginx-mon --help
```

## Development

The parser, rolling aggregation, file follower, CLI, and Textual table have
focused pytest coverage. Run all tests with:

```bash
.venv/bin/python -m pytest
```
