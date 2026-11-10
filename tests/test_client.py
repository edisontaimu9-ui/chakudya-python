import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from chakudya import ChakudyaApiError, ChakudyaClient

SEEN = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, status, body, ctype="application/json"):
        raw = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _handle(self):
        n = int(self.headers.get("Content-Length") or 0)
        SEEN.update(method=self.command, path=self.path, auth=self.headers.get("Authorization"),
                    ua=self.headers.get("User-Agent"), body=self.rfile.read(n).decode() if n else "")
        if self.path.startswith("/admin"):
            return self._send(401, {"status": "error", "message": "API key required"})
        if self.path.startswith("/export/reference"):
            return self._send(200, b"a,b\n1,2", "text/csv")
        if self.path.startswith("/index-plain"):
            return self._send(200, [1, 2, 3])
        self._send(200, {"status": "success", "data": {"echo": self.path}})

    do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _handle


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def make(self, **kw):
        return ChakudyaClient(self.url, api_key="cnr_test", **kw)

    def test_get_query_auth_and_unwrap(self):
        r = self.make().foods.search(q="maize", empty="", flag=True)
        self.assertEqual(r["echo"], "/foods/search?q=maize&flag=true")
        self.assertEqual(SEEN["auth"], "Bearer cnr_test")
        self.assertTrue(SEEN["ua"].startswith("chakudya-python/"))

    def test_snake_case_namespace(self):
        r = self.make().bmi_for_age_under5.classify(sex="girls")
        self.assertEqual(r["echo"], "/bmi-for-age-under-5/classify?sex=girls")

    def test_post_body_positional_and_keyword(self):
        c = self.make()
        c.activity_energy.calculate({"sex": "female"})
        self.assertEqual(SEEN["method"], "POST")
        self.assertEqual(json.loads(SEEN["body"]), {"sex": "female"})
        c.activity_energy.calculate(body={"age": 1}, debug="1")
        self.assertEqual(json.loads(SEEN["body"]), {"age": 1})
        self.assertTrue(SEEN["path"].endswith("?debug=1"))

    def test_path_params_encoded(self):
        self.make().foods.get("a b/c")
        self.assertEqual(SEEN["path"], "/foods/a%20b%2Fc")

    def test_hand_written_helpers(self):
        c = self.make()
        c.foods.autocomplete("mai")
        self.assertEqual(SEEN["path"], "/foods/autocomplete?q=mai&max_results=4")
        c.memory.write("s1", "hello", patient_label="P")
        self.assertEqual(json.loads(SEEN["body"])["patient_label"], "P")
        c.rag.retrieve("anaemia")
        self.assertEqual(json.loads(SEEN["body"]), {"query": "anaemia", "context": "both", "top_k": 5})

    def test_fhir_dollar_paths(self):
        self.make().fhir.condition_diagnose({"x": 1})
        self.assertEqual(SEEN["path"], "/fhir/Condition/$diagnose")

    def test_error_raises(self):
        with self.assertRaises(ChakudyaApiError) as cm:
            self.make().admin.overview()
        self.assertEqual(cm.exception.status, 401)
        self.assertEqual(cm.exception.message, "API key required")

    def test_text_and_plain_json(self):
        c = self.make()
        self.assertEqual(c.export.reference(), "a,b\n1,2")
        self.assertEqual(c.get("/index-plain"), [1, 2, 3])

    def test_missing_path_param(self):
        with self.assertRaises(TypeError):
            self.make().foods.get_convert_by_id()

    def test_network_error_status_zero(self):
        c = ChakudyaClient("http://127.0.0.1:1", api_key="x", timeout=2)
        with self.assertRaises(ChakudyaApiError) as cm:
            c.foods.list()
        self.assertEqual(cm.exception.status, 0)

    def test_pediatric_alias(self):
        c = self.make()
        self.assertIs(c.pediatric, c.paediatric)


if __name__ == "__main__":
    unittest.main()
