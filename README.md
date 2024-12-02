# Nest Query Parser

A parser for a query language that converts to Elasticsearch queries. This module provides functionality to parse queries with nested expressions, boolean operations, and range queries into Elasticsearch-compatible JSON.

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
```
