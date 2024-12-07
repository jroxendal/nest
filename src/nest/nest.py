"""
A parser for a query language that converts to Elasticsearch queries.
This module provides functionality to parse queries with nested expressions,
boolean operations, and range queries into Elasticsearch-compatible JSON.

Example:
    query_string = "authors>(authors.surname:Strindberg + (NOT authors.type:editor))"
    es_query = parse_query(query_string)
    es = Elasticsearch()
    res = es.search(index="my-index", body={"query": es_query})

Author: Johan Roxendal
License: MIT
"""

from tatsu import compile
from tatsu.exceptions import FailedParse
from typing import Dict, Any
from tatsu.util import asjson
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Grammar Features

# We will support:
# 1. Basic Matches: field:value
# 2. Boolean Operators: AND, OR, NOT
# 3. Nested Queries: authors>(surname:Strindberg + (NOT type:editor)) where the plus operator means AND in the context of the nested query
# 4. Range Queries: field:[min TO max] or field:{min TO max}
# 5. Grouping: Parentheses for logical grouping (query)

GRAMMAR = r"""
    @@grammar::Query
    @@whitespace :: /[ \t\n\r]*/

    start = expr $ ;
    
    expr
        = nested_query
        | '(' ~ @:expr ')'
        | expr 'AND' expr
        | expr 'OR' expr
        | 'NOT' expr
        | basic_match
        | keyword_query
        ;
    
    nested_query
        = field '>' nested_expr
        ;

    nested_expr
        = 
        | expr '~' expr
        | '(' ~ @:nested_expr ')'
        | expr
        ;

    datetime_value
        = 'now'
        | /[0-9]{4}-[0-9]{2}-[0-9]{2}/
        | value
        | date_math
        ;

    date_math
        = 'now' [/[+-]/ date_math_value] [/[\/]/ date_math_unit]
        ;

    date_math_value
        = /[0-9]+/
        ;

    date_math_unit
        = 'd' | 'h' | 'm' | 's'
        ;
    
    basic_match
        = field ':' value
        | field:field ':' range:range_value
        ;

    keyword_query
        = /[^:>()[\]{}+]+/
        ;

    field 
        = /[a-zA-Z_][a-zA-Z0-9_.]+/
        ;
    
    range_value
        = '[' gte:datetime_value 'TO' lte:datetime_value ']'
        | '{' gt:datetime_value 'TO' lt:datetime_value '}'
        ;

    
    value
        = /[^\s:>()[\]{}+]+/
        ;
"""


def parse_query(query_string: str) -> Dict[str, Any]:
    """
    Parses a query string into the Elasticsearch Query DSL.

    Args:
        query_string (str): The query string to parse.

    Returns:
        Dict[str, Any]: The Elasticsearch Query DSL.

    Raises:
        ValueError: If the query string cannot be parsed.
    """
    try:
        parser = compile(GRAMMAR)
        ast = parser.parse(query_string)
        return ast_to_es(asjson(ast))
    except FailedParse as e:
        logger.exception(f"Failed to parse query: {query_string}")
        raise ValueError(f"Invalid query string: {query_string}") from e


def ast_to_es(ast: Any) -> Dict[str, Any]:
    """
    Converts an abstract syntax tree (AST) into an Elasticsearch-compatible JSON query.

    Args:
        ast (Any): The abstract syntax tree to convert.

    Returns:
        Dict[str, Any]: The Elasticsearch-compatible JSON query.
    """
    if not ast:
        return {}

    def create_match(field: str, value: str) -> Dict[str, Any]:
        return {"match": {field: value}}

    def create_bool_query(operator: str, queries: list) -> Dict[str, Any]:
        bool_type = {"AND": "must", "~": "must", "OR": "should", "NOT": "must_not"}[
            operator
        ]
        return {"bool": {bool_type: queries}}

    def create_nested_query(path: str, query: Dict[str, Any]) -> Dict[str, Any]:
        return {"nested": {"path": path, "query": query}}

    def process_expr(expr: Any) -> Dict[str, Any]:
        match expr:
            case [field, ":", value]:
                return create_match(field, value)
            case ["NOT", sub_expr]:
                return create_bool_query("NOT", [process_expr(sub_expr)])
            case [field, ">", nested_expr]:
                return create_nested_query(field, process_expr(nested_expr))
            case [sub_expr1, "~", sub_expr2]:
                return {
                    "bool": {"must": [process_expr(sub_expr1), process_expr(sub_expr2)]}
                }
            case [sub_expr1, operator, sub_expr2]:
                return create_bool_query(
                    operator, [process_expr(sub_expr1), process_expr(sub_expr2)]
                )
            case {"field": field, "range": range}:
                return {"range": {field: range}}
            case [sub_expr, []]:
                return process_expr(sub_expr)
            case str():
                return {"query_string": {"query": expr}}
            case _:
                logger.warning(f"Unrecognized expression: {expr}")
                return expr

    return process_expr(ast)


def test_parse_query():
    import json

    assert json.dumps(parse_query("keyword")) == json.dumps(
        {"query_string": {"query": "keyword"}}
    )

    assert json.dumps(parse_query("date:[2022-01-13 TO now]")) == json.dumps(
        {"range": {"date": {"gte": "2022-01-13", "lte": "now"}}}
    )

    # Test simple field value
    assert json.dumps(parse_query("field:value")) == json.dumps(
        {"match": {"field": "value"}}
    )

    assert json.dumps(parse_query("authors>authors.show:false")) == json.dumps(
        {"nested": {"path": "authors", "query": {"match": {"authors.show": "false"}}}}
    )

    # Test nested author query with NOT condition
    assert json.dumps(
        parse_query("authors>(authors.surname:Strindberg ~ (NOT authors.type:editor))")
    ) == json.dumps(
        {
            "nested": {
                "path": "authors",
                "query": {
                    "bool": {
                        "must": [
                            {"match": {"authors.surname": "Strindberg"}},
                            {
                                "bool": {
                                    "must_not": [{"match": {"authors.type": "editor"}}]
                                }
                            },
                        ]
                    }
                },
            }
        }
    )

    # Test AND condition
    assert json.dumps(parse_query("field:value AND field2:value2")) == json.dumps(
        {
            "bool": {
                "must": [
                    {"match": {"field": "value"}},
                    {"match": {"field2": "value2"}},
                ]
            }
        }
    )

    # Test OR with parentheses
    assert json.dumps(
        parse_query("field:value AND (field2:value2 OR field3:value3)")
    ) == json.dumps(
        {
            "bool": {
                "must": [
                    {"match": {"field": "value"}},
                    {
                        "bool": {
                            "should": [
                                {"match": {"field2": "value2"}},
                                {"match": {"field3": "value3"}},
                            ]
                        }
                    },
                ]
            }
        }
    )

    print("All parse query tests passed!")


if __name__ == "__main__":
    test_parse_query()
