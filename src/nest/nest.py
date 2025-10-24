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

    start = directives:directive_list expr:expr $ ;

    directive_list
        = {directive}
        ;

    directive
        = '@' key:directive_key '=' value:directive_value
        ;

    directive_key
        = /[a-zA-Z_][a-zA-Z0-9_.]+/
        ;

    directive_value
        = /[^\s]+/
        ;

    expr
        = or_expr
        ;

    or_expr
        = left:and_expr rest:{'OR' right:and_expr}
        ;

    and_expr
        = left:tilde_expr rest:{'AND' right:tilde_expr}
        ;

    tilde_expr
        = left:not_expr rest:{'~' right:not_expr}
        ;

    not_expr
        = 'NOT' not_expr
        | primary
        ;

    primary
        = '(' ~ @:expr ')'
        | nested_query
        | basic_match
        | keyword_sequence
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
        = expr
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
        = grouped_match
        | field ':' value
        | field:field ':' range:range_value
        ;

    grouped_match
        = field:field ':' '(' group:expr ')'
        ;

    keyword_query
        = /[^\s:>()[\]{}+]+/
        ;

    keyword_sequence
        = first:keyword rest:{keyword}
        ;

    keyword
        = !("AND" | "OR" | "NOT") /[^\s:>()[\]{}+~]+/
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
        ast_json = asjson(ast)
        directives_list = (
            ast_json.get("directives", []) if isinstance(ast_json, dict) else []
        )
        directives = {
            item["key"]: item["value"]
            for item in directives_list
            if isinstance(item, dict)
        }
        expr = ast_json.get("expr") if isinstance(ast_json, dict) else ast_json
        return ast_to_es(expr, directives)
    except FailedParse as e:
        logger.error(f"Failed to parse query: {query_string}")
        error_msg = str(e)
        if "expecting one of" in error_msg:
            raise ValueError(
                f"Invalid query format. Query must start with a field name or keyword. Got: {query_string}"
            ) from e
        raise ValueError(f"Invalid query string: {query_string}. {error_msg}") from e


def ast_to_es(ast: Any, directives: Dict[str, str] | None = None) -> Dict[str, Any]:
    """
    Converts an abstract syntax tree (AST) into an Elasticsearch-compatible JSON query.

    Args:
        ast (Any): The abstract syntax tree to convert.

    Returns:
        Dict[str, Any]: The Elasticsearch-compatible JSON query.
    """
    if not ast:
        return {}

    directives = directives or {}

    QUERY_STRING_OPTION_KEYS = {
        "default_field",
        "default_operator",
        "analyzer",
        "quote_analyzer",
        "allow_leading_wildcard",
        "auto_generate_synonyms_phrase_query",
        "fields",
    }

    def unwrap(node: Any) -> Any:
        while (
            isinstance(node, dict)
            and set(node.keys()) <= {"left", "rest"}
            and (not node.get("rest"))
            and "left" in node
        ):
            node = node["left"]
        return node

    def simplify(node: Any) -> Any:
        node = unwrap(node)

        if isinstance(node, dict):
            if "first" in node:
                tokens = [node["first"], *(node.get("rest") or [])]
                tokens = [t for t in tokens if t is not None]
                if len(tokens) == 1:
                    return tokens[0]
                return tokens

            if "path" in node and "query" in node:
                return {"path": node["path"], "query": simplify(node["query"])}

            if "field" in node and "group" in node:
                return {"field": node["field"], "group": simplify(node["group"])}

            if "field" in node and "range" in node:
                return {"field": node["field"], "range": simplify(node["range"])}

            if "left" in node:
                left_expr = simplify(node["left"])
                rest_entries = node.get("rest") or []
                result_expr = left_expr
                for entry in rest_entries:
                    if not entry:
                        continue
                    if isinstance(entry, list) and len(entry) == 2:
                        operator, operand = entry
                        result_expr = [result_expr, operator, simplify(operand)]
                    else:
                        result_expr = [result_expr, simplify(entry)]
                return result_expr

            return {key: simplify(value) for key, value in node.items()}

        if isinstance(node, list):
            return [simplify(item) for item in node]

        return node

    def apply_query_string_options(query: Dict[str, Any]) -> Dict[str, Any]:
        options: Dict[str, Any] = {}
        for key in QUERY_STRING_OPTION_KEYS:
            if key not in directives:
                continue
            value = directives[key]
            if key == "fields":
                # Split comma separated fields, ignoring empty parts.
                parsed_fields = [f.strip() for f in value.split(",") if f.strip()]
                if parsed_fields:
                    options[key] = parsed_fields
                continue
            options[key] = value
        if not options:
            return {"query_string": query}
        return {"query_string": {**query, **options}}

    def create_match(field: str, value: str) -> Dict[str, Any]:
        return {"match": {field: value}}

    def create_exists(field: str) -> Dict[str, Any]:
        return {"exists": {"field": field}}

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
        if "exists" in query:
            exists_field = query["exists"].get("field")
            return {"exists": {"field": prefix_field(exists_field)}}
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
                if field == "_exists_":
                    return create_exists(value)
                return create_match(field, value)
            case ["NOT", sub_expr]:
                return create_bool_query("NOT", [process_expr(sub_expr)])
            case [field, ">", nested_expr]:
                return create_nested_query(field, process_expr(nested_expr))
            case {"path": path, "query": nested_expr}:
                return create_nested_query(path, process_expr(nested_expr))
            case {"first": first, "rest": rest}:
                tokens = [first, *(rest or [])]
                if not tokens:
                    return {}
                if len(tokens) == 1:
                    return apply_query_string_options({"query": tokens[0]})
                # Treat space-separated keywords as a single query_string expression.
                combined = " ".join(tokens)
                return apply_query_string_options({"query": combined})
            case {"field": field, "group": group_expr}:

                def apply_group(expr):
                    if isinstance(expr, str):
                        return [field, ":", expr]
                    if isinstance(expr, tuple):
                        expr = list(expr)
                    if isinstance(expr, list):
                        if not expr:
                            return expr
                        if len(expr) == 2 and expr[0] == "NOT":
                            return ["NOT", apply_group(expr[1])]
                        if len(expr) == 3 and expr[1] in {"AND", "OR", "~"}:
                            return [
                                apply_group(expr[0]),
                                expr[1],
                                apply_group(expr[2]),
                            ]
                        return [apply_group(item) for item in expr]
                    return expr

                return process_expr(apply_group(group_expr))
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
            case list() as items if all(isinstance(item, str) for item in items):
                combined = " ".join(items)
                return apply_query_string_options({"query": combined})
            case str():
                return apply_query_string_options({"query": expr})
            case _:
                logger.warning(f"Unrecognized expression: {expr}")
                return expr

    simplified_ast = simplify(ast)
    return process_expr(simplified_ast)


if __name__ == "__main__":
    # Example usage
    example_query = "@default_field=title (gender:female OR authors>(gender:female ~ NOT _exists_:type)) AND (texttype:(diktsamling OR dikt)) AND ((export>type:pdf AND license:pd) OR mediatype:pdf)"
    es_query = parse_query(example_query)
    import json

    print(json.dumps(es_query, indent=2))
