# Design

Each indexer is thought to work on its own index, where all indices use the same schema. This allows for independend indexing lifecycles per content source/type, but also for search queries spanning multiple indexes (e. g. docs and handbook).

For example, for docs content (coming from a HUGO site), we use the `hugo` subcommand and configure it with the right source git repository (giantswarm/docs) to index to an index with a unique name.

The indexers are designed to be executed as recurring batch jobs (Kubernetes Cronjob).

When executed, the first task is to determine whether the existing search index is up-to-date. We use the index name for that. The index name is a combination of a static prefix, e. g. `docs-`, and a string representing the state. For the `hugo` indexer, this string is the latest commit SHA seen in the source git repository. For the `blog` indexer, it is the date and time of the last modfication seen in blog articles.

For example, the index name

    docs-0e45d8fc48a949604a8c8b2820fb3c61b67d15ae

indicates that the index represents the docs repository as of commit [0e45d8fc4...](https://github.com/giantswarm/docs/commit/0e45d8fc48a949604a8c8b2820fb3c61b67d15ae).

If the index is seen to be up-to-date with the source, nothing else is done and the command finishes with a success exit code.

If the index does not yet exist, or if the index state differs from the source state, a new index is created using the naming convention described above, and all source documents are indexed into that new index.

A change to the index settings or to a mapping does not make an index out of date, because neither takes part in the state string. An existing, complete index stays as it is, so `docs`, `handbook` and `intranet` keep their current schema until the next commit to their source repository. The `blog` index picks a new schema up as soon as an article changes. To apply a schema change at once, delete the index the alias points at. The next run finds no index for the current state and builds it again with the new schema. Note that the alias is deleted along with the index, so that source is missing from search results until the run finishes.

Finally, once writing to the new index is finished, an index alias will be created. For example, for the index named `docs-0e45d8fc...` an alias `docs` is created. If an alias with the same name existed before (which should be the normal case), the alias is replaced with one pointing to the new index. Outdated indexes (those without an alias) are finally deleted.

The index aliases are crucial to allow for query API calls to remain unchanged while the index names change frequently.
