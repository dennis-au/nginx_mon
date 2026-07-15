# Changelog

## [Unreleased]

### Added

- `--enable-global-json-log` and `--disable-global-json-log` safely manage an
  additional global JSON access-log mirror for the running Nginx instance.
- `--global-log-path` selects the mirror location for source-built and
  nonstandard Nginx installations.

## [0.6.0] - 2026-07-15

### Changed

- Default startup now autodetects the active nginx-mon JSON log from running
  Nginx processes instead of waiting for the RPM-specific log path.
- Failed autodetection now lists open regular-file candidates to identify an
  incompatible standard access log.

## [0.5.0] - 2026-07-15

### Added

- `--detect-nginx` and `--nginx-pid` locate a running Nginx instance's single
  active nginx-mon JSON access log through procfs.

### Fixed

- Log following retains unread records written to a renamed log before Nginx
  reopens its replacement.
