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
        = expr 'AND' expr
        | expr 'OR' expr
        | 'NOT' expr
        | '(' ~ @:expr ')'
        | nested_query
        | basic_match
        | keyword_query
        ;
    
    nested_query
        = path:field '>' query:nested_target
        ;

    nested_target
        = '(' @:nested_expr ')'
        | basic_match
        ;

    nested_expr
        = expr '~' expr
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

# Precompile the grammar
_PARSER = compile(GRAMMAR)


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
        ast = _PARSER.parse(query_string)
        return ast_to_es(asjson(ast))
    except FailedParse as e:
        logger.error(f"Failed to parse query: {query_string}")
        error_msg = str(e)
        if "expecting one of" in error_msg:
            raise ValueError(
                f"Invalid query format. Query must start with a field name or keyword. Got: {query_string}"
            ) from e
        raise ValueError(f"Invalid query string: {query_string}. {error_msg}") from e


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
        bool_query: Dict[str, Any] = {"bool": {bool_type: queries}}
        if bool_type == "should":
            bool_query["bool"]["minimum_should_match"] = 1
        return bool_query

    def prefix_nested_fields(query: Dict[str, Any], path: str) -> Dict[str, Any]:
        def prefix_field(field_name: str) -> str:
            return (
                field_name
                if field_name.startswith(f"{path}.")
                else f"{path}.{field_name}"
            )

        if "match" in query:
            field, value = next(iter(query["match"].items()))
            return {"match": {prefix_field(field): value}}
        if "range" in query:
            range_body: Dict[str, Any] = {}
            for field, value in query["range"].items():
                range_body[prefix_field(field)] = value
            return {"range": range_body}
        if "bool" in query:
            bool_body: Dict[str, Any] = {}
            for key, value in query["bool"].items():
                if key in {"must", "should", "must_not", "filter"}:
                    bool_body[key] = [prefix_nested_fields(q, path) for q in value]
                else:
                    bool_body[key] = value
            return {"bool": bool_body}
        if "nested" in query:
            return query
        return query

    def create_nested_query(path: str, query: Dict[str, Any]) -> Dict[str, Any]:
        return {"nested": {"path": path, "query": prefix_nested_fields(query, path)}}

    def process_expr(expr: Any) -> Dict[str, Any]:
        match expr:
            case [field, ":", value]:
                return create_match(field, value)
            case ["NOT", sub_expr]:
                return create_bool_query("NOT", [process_expr(sub_expr)])
            case [field, ">", nested_expr]:
                return create_nested_query(field, process_expr(nested_expr))
            case {"path": path, "query": nested_expr}:
                return create_nested_query(path, process_expr(nested_expr))
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
