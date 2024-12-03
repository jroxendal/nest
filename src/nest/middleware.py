try:
    from flask import request, g
except ImportError:
    request = None
    g = None
from functools import wraps
try:
    from fastapi import Request
except ImportError:
    Request = None
from typing import Callable
from .nest import parse_query

# Flask Middleware
def flask_query_parser_middleware(app, query_param='query'):
    @app.before_request
    def before_request():
        # Store all query parameters
        g.query_args = request.args.to_dict()
        query_string = request.args.get(query_param)
        if query_string:
            try:
                parsed_query = parse_query(query_string)
                g.parsed_query = parsed_query
            except ValueError as e:
                g.parsed_query = None

# FastAPI Middleware
class FastAPIQueryParserMiddleware:
    def __init__(self, app, query_param='query'):
        self.app = app
        self.query_param = query_param

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            request = Request(scope, receive)
            query_string = request.query_params.get(self.query_param)
            if query_string:
                try:
                    parsed_query = parse_query(query_string)
                    request.state.parsed_query = parsed_query
                except ValueError as e:
                    request.state.parsed_query = None
        await self.app(scope, receive, send)

# Flask Decorator
def use_flask_query_parser(f: Callable):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if hasattr(g, 'parsed_query'):
            kwargs['parsed_query'] = g.parsed_query
        if hasattr(g, 'query_args'):
            # Add all query parameters except the parsed one
            query_args = g.query_args.copy()
            query_args.pop('query', None)  # Remove the special query parameter
            kwargs.update(query_args)
        return f(*args, **kwargs)
    return decorated_function

# FastAPI Decorator
def use_fastapi_query_parser(f: Callable):
    @wraps(f)
    async def decorated_function(*args, **kwargs):
        request = kwargs.get('request')
        if request and hasattr(request.state, 'parsed_query'):
            kwargs['parsed_query'] = request.state.parsed_query
        return await f(*args, **kwargs)
    return decorated_function
