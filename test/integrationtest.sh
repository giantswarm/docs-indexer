#!/bin/bash

# Exit on error
set -e

# Make sure the sitesearch container is clean and up
docker compose down
docker compose up -d sitesearch

sleep 10

declare -a arr=("docs" "intranet" "blog")

for i in "${arr[@]}"
do
    docker compose up --menu=false $i-indexer

    # Test result
    RESULT=`curl -sS http://localhost:9200/$i/_search`
    SHARDS=`echo $RESULT | jq ._shards.successful`
    HITS=`echo $RESULT | jq .hits.total`

    if [ "$SHARDS" == "null" ]; then
        echo "No search result for $i"
        exit 1
    fi

    if [[ $SHARDS -eq 0 ]]; then
        echo "No successful shards in $i search"
        exit 1
    else
        echo "Found $SHARDS successful shards in $i search"
    fi

    if [[ $HITS -eq 0 ]]; then
        echo "Zero hits in $i search"
        exit 1
    else
        echo "Found $HITS hits in $i search"
    fi
done
