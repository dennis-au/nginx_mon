# Changelog

## [0.5.0] - 2026-07-15

### Added

- `--detect-nginx` and `--nginx-pid` locate a running Nginx instance's single
  active nginx-mon JSON access log through procfs.

### Fixed

- Log following retains unread records written to a renamed log before Nginx
  reopens its replacement.
