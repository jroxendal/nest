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

## Flask Middleware Usage

To use the Flask middleware, add the `flask_query_parser_middleware` to your Flask app and use the `use_flask_query_parser` decorator for your endpoint:

```python
from flask import Flask, jsonify, g
from nest.middleware import flask_query_parser_middleware, use_flask_query_parser

app = Flask(__name__)
flask_query_parser_middleware(app)

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
app.add_middleware(FastAPIQueryParserMiddleware)

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
