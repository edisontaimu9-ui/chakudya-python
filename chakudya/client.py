import json
import keyword
import re
import socket
import urllib.error
import urllib.parse
import urllib.request

from .errors import ChakudyaApiError
from .routes import GENERATED_ROUTES

DEFAULT_BASE_URL = "https://api.chakudya.xyz"
__version__ = "1.0.0"

_PATH_PARAM = re.compile(r"\{\w+\}")


def _snake(name):
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower()


def _safe(name):
    return name + "_" if keyword.iskeyword(name) else name


def _enc(value):
    if value is None or value == "":
        raise ValueError("missing path parameter")
    return urllib.parse.quote(str(value), safe="")


class Namespace:
    """A group of routes, for example `cnr.foods`."""

    def __init__(self, name):
        self._name = name

    def __repr__(self):
        methods = sorted(k for k in vars(self) if not k.startswith("_"))
        return f"<Namespace {self._name}: {', '.join(methods)}>"


class ChakudyaClient:
    """Client for the Chakudya Nutrition Registry (CNR) API.

        cnr = ChakudyaClient(api_key="cnr_...")
        cnr.foods.search(q="maize")
        cnr.growth.assess(sex="female", age_months=12, weight_kg=9)
        cnr.activity_energy.calculate({"sex": "female", ...})

    Rules for every method:
      * path parameters are positional:        cnr.foods.get(9)
      * GET / DELETE: keyword arguments become the query string
      * POST / PUT / PATCH: pass the JSON body as the next positional argument
        (or body=...); other keyword arguments become the query string
      * the result is the decoded "data" field (dict or list), or text for CSV exports
      * errors raise ChakudyaApiError
    Method and namespace names are snake_case (bmiForAge -> bmi_for_age).
    """

    def __init__(self, base_url=DEFAULT_BASE_URL, api_key=None, login_token=None, timeout=20):
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key
        self.login_token = login_token  # only /developer/... routes use it
        self.timeout = timeout

        self._build_hand_written()
        for ns_name, methods in GENERATED_ROUTES.items():
            ns = self._namespace(ns_name)
            for method_name, route in methods.items():
                attr = _safe(_snake(method_name))
                if not hasattr(ns, attr):  # hand-written methods win
                    setattr(ns, attr, self._route(route, f"{ns_name}.{method_name}"))
        self.pediatric = self.paediatric  # the API accepts both spellings

    # ---- low level -------------------------------------------------------------------

    def request(self, method, path, params=None, body=None):
        """Send one request and return the decoded `data` field."""
        url = self.base_url + path
        query = {}
        for k, v in (params or {}).items():
            if v is None or v == "":
                continue
            if isinstance(v, bool):
                v = "true" if v else "false"
            elif isinstance(v, (list, tuple)):
                v = ",".join(str(x) for x in v)
            query[k] = v
        if query:
            url += "?" + urllib.parse.urlencode(query)

        headers = {
            "Accept": "application/json",
            # Cloudflare can reject the default "Python-urllib" agent.
            "User-Agent": f"chakudya-python/{__version__}",
        }
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode("utf-8")
        token = self.login_token if (path.startswith("/developer") and self.login_token) else self.api_key
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as res:
                status, ctype, raw = res.status, res.headers.get("Content-Type", ""), res.read()
        except urllib.error.HTTPError as e:
            status, ctype, raw = e.code, e.headers.get("Content-Type", "") if e.headers else "", e.read()
        except (socket.timeout, TimeoutError):
            raise ChakudyaApiError(f"Request timed out after {self.timeout}s", 0) from None
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)):
                raise ChakudyaApiError(f"Request timed out after {self.timeout}s", 0) from None
            raise ChakudyaApiError(f"Network error: {e.reason}", 0) from None

        text = raw.decode("utf-8", errors="replace")
        decoded = None
        if "json" in ctype or re.match(r"^\s*[\[{]", text):
            try:
                decoded = json.loads(text)
            except ValueError:
                decoded = None
        obj = decoded if isinstance(decoded, dict) else None

        if not (200 <= status < 300) or (obj and obj.get("status") == "error"):
            msg = (obj or {}).get("message") or (obj or {}).get("error") or f"Request failed ({status})"
            raise ChakudyaApiError(str(msg), status, decoded if decoded is not None else text)
        if decoded is None:
            return text
        if obj is not None and "data" in obj:
            return obj["data"]
        return decoded

    def get(self, path, **params):
        return self.request("GET", path, params=params)

    def post(self, path, body=None, **params):
        return self.request("POST", path, params=params, body=body)

    def put(self, path, body=None, **params):
        return self.request("PUT", path, params=params, body=body)

    def patch(self, path, body=None, **params):
        return self.request("PATCH", path, params=params, body=body)

    def delete(self, path, **params):
        return self.request("DELETE", path, params=params)

    def root(self):
        """GET / (API index, no key needed)."""
        return self.get("/")

    # ---- route building -------------------------------------------------------------

    def _namespace(self, name):
        attr = _safe(_snake(name))
        ns = getattr(self, attr, None)
        if ns is None:
            ns = Namespace(attr)
            setattr(self, attr, ns)
        return ns

    def _route(self, route, label):
        method, path = route.split(" ")
        n = len(_PATH_PARAM.findall(path))
        has_body = method in ("POST", "PUT", "PATCH")

        def call(*args, **query):
            if len(args) < n:
                raise TypeError(f"{label} ({route}) needs {n} path argument(s), got {len(args)}")
            it = iter(args[:n])
            url = _PATH_PARAM.sub(lambda _: _enc(next(it)), path)
            extra = list(args[n:])
            if has_body:
                body = extra.pop(0) if extra else query.pop("body", None)
            else:
                body = None
            if extra and isinstance(extra[0], dict):  # a params dict passed positionally
                query = {**extra[0], **query}
            return self.request(method, url, params=query or None, body=body)

        call.__name__ = _snake(label.split(".")[-1])
        call.__doc__ = route
        return call

    def _build_hand_written(self):
        def crud(ns, base, put=True):
            ns.list = lambda **q: self.get(base, **q)
            ns.get = lambda id: self.get(f"{base}/{_enc(id)}")
            ns.create = lambda body: self.post(base, body)
            ns.update = lambda id, body: self.patch(f"{base}/{_enc(id)}", body)
            ns.remove = lambda id: self.delete(f"{base}/{_enc(id)}")
            if put:
                ns.replace = lambda id, body: self.put(f"{base}/{_enc(id)}", body)

        self.foods = Namespace("foods")
        crud(self.foods, "/foods")
        self.foods.lookup = lambda **q: self.get("/foods/lookup", **q)
        self.foods.autocomplete = lambda q, max_results=4: self.get("/foods/autocomplete", q=q, max_results=max_results)
        self.foods.categories = lambda: self.get("/foods/categories")

        for name in ("exchange", "renal", "formulas"):
            ns = Namespace(name)
            crud(ns, f"/{name}")
            setattr(self, name, ns)

        self.packaged = Namespace("packaged")
        self.packaged.list = lambda **q: self.get("/packaged", **q)
        self.packaged.submit = lambda body: self.post("/packaged/submit", body)
        self.packaged.scan = lambda images: self.post("/packaged/scan", {"images": images})
        self.packaged.update = lambda id, body: self.patch(f"/packaged/{_enc(id)}", body)
        self.packaged.remove = lambda id: self.delete(f"/packaged/{_enc(id)}")

        self.rag = Namespace("rag")
        self.rag.retrieve = lambda query, context="both", top_k=5: self.post(
            "/rag/retrieve", {"query": query, "context": context, "top_k": top_k})
        self.rag.ingest = lambda body: self.post("/rag/ingest", body)  # admin

        self.memory = Namespace("memory")

        def memory_write(session_id, content, kind="fact", patient_label=None):
            body = {"session_id": session_id, "content": content, "kind": kind}
            if patient_label is not None:
                body["patient_label"] = patient_label
            return self.post("/memory/write", body)

        self.memory.write = memory_write
        self.memory.recall = lambda session_id, query, top_k=5: self.post(
            "/memory/recall", {"session_id": session_id, "query": query, "top_k": top_k})
        self.memory.consolidate = lambda session_id: self.post("/memory/consolidate", {"session_id": session_id})  # admin
