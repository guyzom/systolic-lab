from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from systolic_lab.server import Handler, request_simulation


class QuietHandler(Handler):
    def log_message(self, *args):
        pass


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_static_assets_and_live_api(self):
        for path in ("/", "/app.js", "/style.css", "/favicon.svg"):
            with urlopen(self.url + path) as response:
                self.assertEqual(response.status, 200)
                self.assertGreater(len(response.read()), 100)
        with urlopen(self.url + "/api/simulate?demo=1&rows=2&cols=2&bandwidth=8&latency=1") as response:
            data = json.load(response)
            self.assertEqual(data["result"], [[58, 64], [139, 154]])
            self.assertEqual(len(data["frames"]), 11)

    def test_http_errors_are_explicit(self):
        for path, code in (("/api/simulate?bandwidth=0", 400), ("/api/simulate?m=abc", 400),
                           ("/api/simulate?m=33", 400), ("/api/simulate?m=2&m=3", 400),
                           ("/api/simulate?unknown=1", 400), ("/../simulator.py", 404)):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                urlopen(self.url + path)
            self.assertEqual(error.exception.code, code)

    def test_summary_api_and_capacity_error(self):
        data = request_simulation({"demo": ["1"], "trace": ["0"]})
        self.assertEqual(data["frames"], [])
        self.assertTrue(data["verified"])
        with self.assertRaisesRegex(ValueError, "scratchpad"):
            request_simulation({"demo": ["1"], "scratchpad": ["1"]})


if __name__ == "__main__":
    unittest.main()
