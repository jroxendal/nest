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

```python
from nest.nest import parse_query

parse_query("field:value")
# {'match': {'field': 'value'}}

# Opt-in flags:
# - use_simple_query_string=True -> emit simple_query_string clauses for lenient parsing
# - escape_special_chars=True -> auto-escape logical NOT ('!') so trailing bangs don't break Lucene parsing
parse_query("kriget är förklarat!", escape_special_chars=True)
# {'query_string': {'query': 'kriget är förklarat\\!'}}
```

### Advanced Parser Options

- `use_simple_query_string`: produce `simple_query_string` clauses instead of `query_string`. Defaults to `False`.
- `escape_special_chars`: automatically escape the logical NOT operator (`!`) inside generated `query_string` clauses. Defaults to `False`, but the middleware examples below show how to enable it globally.

## License
This project is licensed under the MIT License.

## Examples
```python
#Simple Field Value
query_string = "field:value"
es_query = parse_query(query_string)
print(es_query)
# Output: {'match': {'field': 'value'}}

print(parse_query("authors>(surname:Strindberg + (NOT type:editor))"))
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

## Flask Middleware Usage

To use the Flask middleware, add the `flask_query_parser_middleware` to your Flask app and use the `use_flask_query_parser` decorator for your endpoint:

```python
from flask import Flask, jsonify
from nest.middleware import flask_query_parser_middleware, use_flask_query_parser

app = Flask(__name__)
flask_query_parser_middleware(
    app,
    query_param="q",
    escape_special_chars=True,      # ensure trailing ! is escaped for safety
    use_simple_query_string=False,  # flip to True for simple_query_string
)

@app.route('/search')
@use_flask_query_parser
def search(parsed_query):
    if parsed_query:
        return jsonify(parsed_query)
    return jsonify({"error": "Invalid query"})

if __name__ == '__main__':
    app.run()
```

## FastAPI Middleware Usage

To use the FastAPI middleware, add the `FastAPIQueryParserMiddleware` to your FastAPI app and use the `use_fastapi_query_parser` decorator for your endpoint:

```python
from fastapi import FastAPI, Request
from nest.middleware import FastAPIQueryParserMiddleware, use_fastapi_query_parser

app = FastAPI()
app.add_middleware(
    FastAPIQueryParserMiddleware,
    query_param="q",
    escape_special_chars=True,      # opt-in escaping of ! for every request
    use_simple_query_string=False,
)

@app.get('/search')
@use_fastapi_query_parser
async def search(request: Request, parsed_query: dict = None):
    if parsed_query:
        return parsed_query
    return {"error": "Invalid query"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
```
