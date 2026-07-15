Name:           nginx_mon
Version:        0.6.0
Release:        1%{?dist}
Summary:        Real-time Nginx reverse-proxy traffic monitor

License:        MIT
URL:            https://github.com/dennis-au/nginx_mon
Source0:        %{name}-%{version}.tar.gz

BuildArch:       x86_64
BuildRequires:   gcc
BuildRequires:   make
BuildRequires:   python3
BuildRequires:   python3-devel
BuildRequires:   python3-pip
BuildRequires:   redhat-rpm-config

%global debug_package %{nil}

%description
nginx-mon is a Textual terminal application that tails a dedicated Nginx JSON
access log and shows rolling upstream TX/RX traffic by frontend virtual host.
The RPM installs a self-contained PyInstaller executable, Nginx sample
configuration, and manual page. It has no runtime Python dependency.

%prep
%autosetup -n %{name}-%{version}

%build
python3 -m venv .build-venv
.build-venv/bin/python -m pip install --upgrade pip setuptools wheel
.build-venv/bin/python -m pip install . pyinstaller
.build-venv/bin/pyinstaller --clean --noconfirm --onefile --name nginx-mon \
    --paths src packaging/pyinstaller_entry.py

%install
install -Dpm 0755 dist/nginx-mon %{buildroot}%{_bindir}/nginx-mon
install -Dpm 0644 packaging/nginx_mon.conf \
    %{buildroot}%{_datadir}/nginx-mon/nginx_mon.conf
install -d %{buildroot}%{_mandir}/man1
gzip -9c packaging/nginx-mon.1 > %{buildroot}%{_mandir}/man1/nginx-mon.1.gz

%files
%license LICENSE
%doc README.md
%{_bindir}/nginx-mon
%{_datadir}/nginx-mon/nginx_mon.conf
%{_mandir}/man1/nginx-mon.1.gz

%changelog
* Wed Jul 15 2026 Dennis Au <dennis.518@gmail.com> - 0.6.0-1
- Autodetect the active nginx-mon JSON log by default
- Report open regular-file candidates when autodetection finds no monitor log

* Wed Jul 15 2026 Dennis Au <dennis.518@gmail.com> - 0.5.0-1
- Discover active nginx-mon JSON logs from running Nginx processes
- Preserve unread log entries across rename and reopen rotation

* Tue Jul 14 2026 Dennis Au <dennis.518@gmail.com> - 0.4.0-1
- Default to Monokai and add pause/resume live updates
- Remove the screenshot command

* Tue Jul 14 2026 Dennis Au <dennis.518@gmail.com> - 0.3.0-1
- Show the NetworkManager connection for each listener address

* Tue Jul 14 2026 Dennis Au <dennis.518@gmail.com> - 0.2.0-1
- Add source, backend endpoint, listener port, and TLS telemetry

* Tue Jul 14 2026 Dennis Au <dennis.518@gmail.com> - 0.1.0-1
- Initial package
