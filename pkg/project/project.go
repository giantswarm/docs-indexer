package project

var (
	description        = "Indexes content for the search engine in docs.giantswarm.io"
	gitSHA             = "n/a"
	name        string = "docs-indexer"
	source      string = "https://github.com/giantswarm/docs-indexer"
	version            = "3.5.0"
)

func Description() string {
	return description
}

func GitSHA() string {
	return gitSHA
}

func Name() string {
	return name
}

func Source() string {
	return source
}

func Version() string {
	return version
}
