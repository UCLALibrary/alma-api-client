# Changelog

## 0.2.3 - 2026-10-28

### Changed

- Added endpoints to retrieve Alma electronic collection and service data.

## 0.2.2 - 2025-12-15

### Fixed

- `_call_api()` now raises `APIError` when `requests` raises `requests.exceptions.SSLError`.

## 0.2.1 - 2025-10-10

### Fixed

- `wait_for_completion()` no longer causes an infinite loop.

## 0.2.0 - 2025-09-30

### Changed

- The API interface was completely rewritten.

## 0.1.0 - 2025-09-18

### Changed

- The MARC handling was completely rewritten.
