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

        @self.app.route("/search/<other_param>")
        @use_flask_query_parser
        def search(other_param, parsed_query):
            assert other_param == "1234"
            if parsed_query:
                return parsed_query
            return {"error": "Invalid query"}

        self.client = self.app.test_client()

    def test_flask_query_parser_middleware(self):
        response = self.client.get("/search/1234?query=field:value")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"match": {"field": "value"}})

    def test_flask_query_parser_middleware_invalid_query(self):
        response = self.client.get("/search/1234?query=>invalid")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"error": "Invalid query"})


class FastAPIMiddlewareTestCase(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.add_middleware(FastAPIQueryParserMiddleware)

        @self.app.get("/search")
        @use_fastapi_query_parser
        async def search(request: Request, parsed_query: dict = None):
            if parsed_query:
                return parsed_query
            return {"error": "Invalid query"}

        @self.app.get("/search-alt")
        @use_fastapi_query_parser
        async def search_alt(request: Request, parsed_query: dict = None):
            if parsed_query:
                return parsed_query
            return {"error": "Invalid query"}

        self.client = TestClient(self.app)

    def test_fastapi_query_parser_middleware(self):
        response = self.client.get("/search?query=field:value")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"match": {"field": "value"}})

    def test_fastapi_query_parser_middleware_invalid_query(self):
        response = self.client.get("/search?query=>invalid")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"error": "Invalid query"})

    def test_fastapi_query_parser_middleware_url_encoded_nested_query(self):
        # Test that URL-encoded query parameter is properly decoded and translated
        # q=authors%3E(authors.surname:Strindberg+~+(NOT+authors.type:editor))
        # decodes to: authors>(authors.surname:Strindberg ~ (NOT authors.type:editor))
        response = self.client.get(
            "/search?query=authors%3E(authors.surname:Strindberg+~+(NOT+authors.type:editor))"
        )
        expected = {
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
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

    def test_fastapi_query_parser_middleware_multiple_endpoints(self):
        response_primary = self.client.get("/search?query=field:value")
        response_secondary = self.client.get("/search-alt?query=title:roman")
        response_primary_again = self.client.get("/search?query=genre:drama")

        self.assertEqual(response_primary.status_code, 200)
        self.assertEqual(response_primary.json(), {"match": {"field": "value"}})

        self.assertEqual(response_secondary.status_code, 200)
        self.assertEqual(response_secondary.json(), {"match": {"title": "roman"}})

        self.assertEqual(response_primary_again.status_code, 200)
        self.assertEqual(response_primary_again.json(), {"match": {"genre": "drama"}})

    def test_use_fastapi_query_parser_requires_request_kwarg(self):
        app = FastAPI()
        app.add_middleware(FastAPIQueryParserMiddleware)

        @app.get("/missing-request")
        @use_fastapi_query_parser
        async def missing_request_endpoint(parsed_query: dict = None):
            return {"parsed_query": parsed_query}

        client = TestClient(app)
        with self.assertRaises(RuntimeError) as cm:
            client.get("/missing-request?query=field:value")
        self.assertIn(
            "requires the decorated function to accept a FastAPI Request",
            str(cm.exception),
        )


if __name__ == "__main__":
    unittest.main()
