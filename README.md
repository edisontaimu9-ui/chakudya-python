# chakudya-sdk (Python)

Python client for the **Chakudya Nutrition Registry (CNR)**, the open food and clinical nutrition API at `api.chakudya.xyz`. Same routes as the JavaScript and Dart SDKs (API 1.83.0): 64 namespaces, about 320 methods. No dependencies (standard library only), Python 3.8+.

## Install

```
pip install git+https://github.com/edisontaimu9-ui/chakudya-python.git
```

## Use

```python
import os
from chakudya import ChakudyaClient, ChakudyaApiError

cnr = ChakudyaClient(api_key=os.environ["CHAKUDYA_KEY"])

cnr.foods.search(q="maize")
cnr.growth.assess(sex="female", age_months=12, weight_kg=9)
cnr.dri.list(life_stage="female_19_30")
cnr.activity_energy.calculate({"sex": "female", "age_months": 12})   # POST body
```

Rules for every method:

- Names are snake_case: `bmiForAge` becomes `cnr.bmi_for_age`.
- Path parameters are positional: `cnr.foods.get(9)`.
- GET and DELETE: keyword arguments become the query string.
- POST, PUT and PATCH: the JSON body is the next positional argument (or `body=...`); other keyword arguments become the query string.
- The result is the decoded `data` field (a `dict` or `list`), or text for CSV exports.
- Errors raise `ChakudyaApiError` with `.status`, `.message` and `.body`. Timeouts and network failures have `.status == 0`.
- Anything not covered: `cnr.get("/path", a=1)`, `cnr.post("/path", {...})`, or `cnr.request(method, path, params, body)`.

Typed helpers: `foods`, `exchange`, `renal` and `formulas` (list, get, create, update, replace, remove), `foods.autocomplete`, `packaged`, `rag.retrieve`, `memory.write` and `memory.recall`.

Find what exists with `print(cnr.growth)` or `dir(cnr.foods)`.

## Keys

Use a **consumer** key for apps and scripts. Admin routes (`cnr.admin...`) need the admin key; never put that in a client app. Read keys from an environment variable, not from your code.

## Smoke test

```
CHAKUDYA_KEY="cnr_..." python examples/smoke.py
```

## Tests and regenerating

```
python -m unittest discover -s tests
python tool/generate.py     # after copying a new methods.json from the JS SDK
```

MIT licence.
