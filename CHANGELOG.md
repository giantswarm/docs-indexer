# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Migrate Chart.yaml annotations to new format as per https://docs.giantswarm.io/reference/platform-api/chart-metadata/
## [4.0.0] - 2025-11-21

### Changed

- Moved to new Open Search backend

## [3.5.0] - 2025-09-17

### Removed

- Remove PodSecurityPolicy template

### Added

- Enable log collection in Loki via `observability.giantswarm.io/tenant: giantswarm` annotation


## [3.4.3] - 2025-05-15

- Dependency updates

## [3.4.2] - 2024-03-13

## [3.4.1] - 2024-02-13

- Fix reference to secret in Role resource

## [3.4.0] - 2024-02-09

### Changed

- Make secret resources part of the chart

## [3.3.4] - 2024-02-06

### Changed

- Adjust job spec for security compliance in K8s 1.25
- Set container registry to `gsoci.azurecr.io`

## [3.3.3] - 2024-02-05

### Added

- Add PSS resources (PolicyException)

## [3.3.2] - 2024-01-29

### Fixed

- Move pss values under the global property

## [3.3.1] - 2023-11-30

## [3.3.0] - 2023-11-10

### Changed

- Add a switch for PSP CR installation.

## [3.2.1] - 2023-10-04

## [3.2.0] - 2023-02-28

### Changed

- Fix handling of upper/mixed case file names in HUGO pages.

## [3.1.1] - 2022-12-15

### Changed

- Fix intranet base url 

## [3.1.0] - 2022-12-15

- Improve docker image build speed by using PyYAML from Alpine.
- Fix removal of a slash from the URL scheme.
- Add `type` field to search documents for filtering.

## [3.0.1] - 2022-12-15

- Fix log template

## [3.0.0] - 2022-12-15

- Modify configuration
- Add cronjobs for handbook and intranet
- Add `url` field containing the absolute resource URL

## [2.8.1] - 2022-11-03

### Changed

- Support HubSpot private app token

### Added

- Workflows
- First release adhering to [how-to-release-a-project](https://intranet.giantswarm.io/docs/dev-and-releng/releases/how-to-release-a-project/)


[Unreleased]: https://github.com/giantswarm/docs-indexer/compare/v4.0.0...HEAD
[4.0.0]: https://github.com/giantswarm/docs-indexer/compare/v3.5.0...v4.0.0
[3.5.0]: https://github.com/giantswarm/docs-indexer/compare/v3.4.3...v3.5.0
[3.4.3]: https://github.com/giantswarm/docs-indexer/compare/v3.4.2...v3.4.3
[3.4.2]: https://github.com/giantswarm/docs-indexer/compare/v3.4.1...v3.4.2
[3.4.1]: https://github.com/giantswarm/docs-indexer/compare/v3.4.0...v3.4.1
[3.4.0]: https://github.com/giantswarm/docs-indexer/compare/v3.3.4...v3.4.0
[3.3.4]: https://github.com/giantswarm/docs-indexer/compare/v3.3.3...v3.3.4
[3.3.3]: https://github.com/giantswarm/docs-indexer/compare/v3.3.2...v3.3.3
[3.3.2]: https://github.com/giantswarm/docs-indexer/compare/v3.3.1...v3.3.2
[3.3.1]: https://github.com/giantswarm/docs-indexer/compare/v3.3.0...v3.3.1
[3.3.0]: https://github.com/giantswarm/docs-indexer/compare/v3.2.1...v3.3.0
[3.2.1]: https://github.com/giantswarm/docs-indexer/compare/v3.2.0...v3.2.1
[3.2.0]: https://github.com/giantswarm/docs-indexer/compare/v3.1.1...v3.2.0
[3.1.1]: https://github.com/giantswarm/docs-indexer/compare/v3.1.0...v3.1.1
[3.1.0]: https://github.com/giantswarm/docs-indexer/compare/v3.0.1...v3.1.0
[3.0.1]: https://github.com/giantswarm/docs-indexer/compare/v3.0.0...v3.0.1
[3.0.0]: https://github.com/giantswarm/docs-indexer/compare/v2.8.1...v3.0.0
[2.8.1]: https://github.com/giantswarm/docs-indexer/compare/v2.8.1...v2.8.1
