# NEST

**N**ested **E**lasticsearch **S**yntax **T**ool

A parser for a query language that converts to Elasticsearch queries. This module provides functionality to parse a query_string language but with added support for nested expressions. It intended as a superset, but so far only boolean operations and range queries have been added. 

## Installation

To install the required dependencies, run:

```bash
pip install -r requirements.txt
```

## Usage
Example usage of the parser:

## License
This project is licensed under the MIT License.

## Examples
```python
#Simple Field Value
query_string = "field:value"
es_query = parse_query(query_string)
print(es_query)
# Output: {'match': {'field': 'value'}}

print(parse_query("authors>(authors.surname:Strindberg + (NOT authors.type:editor))"))
#output:
{
    "nested": {
        "path": "authors",
        "query": {
            "bool": {
                "must": [
                    {"match": {"authors.surname": "Strindberg"}},
                    {"bool": {"must_not": [{"match": {"authors.type": "editor"}}]}},
                ]
            }
        },
    }
}
```
