import unittest
from flask import Flask, g
from nest.middleware import flask_query_parser_middleware, use_flask_query_parser
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from nest.middleware import FastAPIQueryParserMiddleware, use_fastapi_query_parser

class FlaskMiddlewareTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        flask_query_parser_middleware(self.app)

        @self.app.route('/search/<other_param>')
        @use_flask_query_parser
        def search(other_param, parsed_query):
            assert other_param == '1234'
            if parsed_query:
                return parsed_query
            return {"error": "Invalid query"}

        self.client = self.app.test_client()

    def test_flask_query_parser_middleware(self):
        response = self.client.get('/search/1234?query=field:value')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"match": {"field": "value"}})

    def test_flask_query_parser_middleware_invalid_query(self):
        response = self.client.get('/search/1234?query=>invalid')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"error": "Invalid query"})

class FastAPIMiddlewareTestCase(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.add_middleware(FastAPIQueryParserMiddleware)

        @self.app.get('/search')
        @use_fastapi_query_parser
        async def search(request: Request, parsed_query: dict = None):
            if parsed_query:
                return parsed_query
            return {"error": "Invalid query"}

        self.client = TestClient(self.app)

    def test_fastapi_query_parser_middleware(self):
        response = self.client.get('/search?query=field:value')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"match": {"field": "value"}})

    def test_fastapi_query_parser_middleware_invalid_query(self):
        response = self.client.get('/search?query=>invalid')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"error": "Invalid query"})

if __name__ == '__main__':
    unittest.main()
