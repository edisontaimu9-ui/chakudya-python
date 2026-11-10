import os

from chakudya import ChakudyaApiError, ChakudyaClient

# export CHAKUDYA_KEY="cnr_..."   then:   python examples/basic.py
cnr = ChakudyaClient(api_key=os.environ.get("CHAKUDYA_KEY"))

try:
    print(cnr.foods.search(q="maize"))
    print(cnr.growth.assess(sex="female", age_months=12, weight_kg=9))
    print(cnr.dri.list(life_stage="female_19_30"))
except ChakudyaApiError as e:
    print("API error", e.status, e.message)
