#!/usr/bin/env python

import sys
from opensearchpy import OpenSearch
from nest.nest import parse_query
import json
import argparse


def search(
    index: str, query_string: str, dump: bool = False, source_includes: str = ""
) -> None:
    client = OpenSearch(
        hosts=[{"host": "localhost", "port": 9200}],
        http_auth=None,  # For testing on localhost without security
        use_ssl=False,  # Disable SSL for local testing
        verify_certs=False,
    )

    try:
        es_query = parse_query(query_string)
        if dump:
            maybe_source_includes = (
                f"?_source_includes={source_includes}" if source_includes else ""
            )
            print(
                f"GET {index}/_search{maybe_source_includes} \n{json.dumps({'query': es_query}, indent=2)}"
            )
            return

        response = client.search(
            index=index, body={"query": es_query}, _source_includes=source_includes
        )
        print(json.dumps(response))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Search OpenSearch index")
    parser.add_argument("index", help="Index to search")
    parser.add_argument("query", help="Search query")
    parser.add_argument("-i", "--includes", help="Source includes")
    parser.add_argument(
        "-d", "--dump", action="store_true", help="Dump query instead of executing"
    )

    args = parser.parse_args()
    search(args.index, args.query, args.dump, args.includes)


if __name__ == "__main__":
    main()
