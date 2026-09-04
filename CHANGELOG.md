# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Give the blog indexer the same leftover handling as the hugo one. An interrupted blog run left its index behind forever: the index is created before indexing starts, and only the index the alias pointed at was ever cleaned up. Blog indices that no alias points at are now deleted at the start of each run, scoped to the `blog-<timestamp>` naming scheme.
- Delete the blog index again when a run finds no posts, instead of leaving an empty index behind that no alias points at. The previously aliased index stays in service, as before.
- Move the blog index alias in a single atomic `POST /_aliases` call, the same fix already made for the hugo indexer.
- Replace a blog index left behind by an interrupted run in the same second, which pruning spares because it is the name the new run is about to use. `create_index` used to fail with `resource_already_exists_exception` in that case. Only reachable when two runs start within one second, so not something the daily schedule hits.

### Changed

- Move the index alias and leftover-pruning helpers into `common.py`, shared by both indexers rather than duplicated. No behaviour change for the hugo indexer.

### Added

- Add `architecture` value (`""` | `amd64` | `arm64`) to pin the indexer CronJobs to a CPU architecture, plus `nodeSelector` and `tolerations` passthrough values (the job pod specs previously had no scheduling fields). Setting `arm64` renders both the `kubernetes.io/arch` node selector and the toleration for the `kubernetes.io/arch=arm64:NoSchedule` taint that Giant Swarm arm64 node pools carry; both are required, so one value drives both. Applies to all four CronJobs (docs, blog, handbook, intranet). Defaults to `""`, which renders nothing, so output is unchanged for existing users.
- Add a `helm-unittest` suite for the `docs-indexer-app.podScheduling` helper (13 cases), run with `make helm-unittest`. Local only for now, since chart unit tests belong in the generated workflow set rather than a hand-written per-repo workflow.

### Fixed

- Treat the index alias as the marker that a hugo (docs/handbook/intranet) indexing run completed. A run killed before the alias switch used to leave a partial index behind that every later run for the same commit SHA skipped as "already exists" while exiting 0, so the CronJob reported success without indexing anything. An index that no alias points at is now treated as incomplete: it gets deleted and indexed again.
- Move the index alias to the new index in a single atomic `POST /_aliases` call, instead of deleting the old alias and adding the new one separately, which left the alias missing entirely if the run was killed in between. Predecessor indices are deleted only after the alias has moved.
- Determine each Markdown file's last modification date in one walk of the git history, instead of one history walk per file. The per-file walk was what exhausted the CronJob's 600s deadline: on `giantswarm/docs` (6630 Markdown files, 4379 commits) it takes 171s locally and roughly 595s on a cluster node, leaving no time to index. The single walk takes 0.28s for the same repo, and returns identical dates for all 6630 files.
- Delete this indexer's indices that no alias points at, at the start of every run. Leftovers of runs that never reached the alias switch used to accumulate indefinitely, since only the index the alias pointed at was ever cleaned up. Deletion is scoped to indices named after the alias plus a 40-character commit SHA, so indices created by anything else are left alone.

### Removed

- Remove the `GitPython` dependency, no longer used now that the git history is read with `git log` directly.

## [4.1.3] - 2026-06-09

### Added

- Building the container image multi-arch, to support linux/arm64

## [4.1.2] - 2026-03-27

### Changed

- Prepare chart for use with Flux OCIRepository + HelmRelease
- Use common labels consistently on all resources

### Removed

- Remove `app` label from resources

## [4.1.1] - 2026-01-14

### Added

- Added definition of `breadcrumb_1` ... `breadcrumb_5` to mappings.

### Changed

- Change type of `breadcrumb` field to `keyword` for exact matching.

## [4.1.0] - 2026-01-06

### Changed

- ABS migration
- Migrate Chart.yaml annotations to the new format as per https://docs.giantswarm.io/reference/platform-api/chart-metadata/

### Removed

- Removed PSP-related support value `.global.podSecurityStandards.enforced`. Kyverno `PolicyException`s are now created by default.

### Fixed

- Fix GS polex names to be unique.

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


[Unreleased]: https://github.com/giantswarm/docs-indexer/compare/v4.1.3...HEAD
[4.1.3]: https://github.com/giantswarm/docs-indexer/compare/v4.1.2...v4.1.3
[4.1.2]: https://github.com/giantswarm/docs-indexer/compare/v4.1.1...v4.1.2
[4.1.1]: https://github.com/giantswarm/docs-indexer/compare/v4.1.0...v4.1.1
[4.1.0]: https://github.com/giantswarm/docs-indexer/compare/v4.0.0...v4.1.0
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
