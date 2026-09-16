#!/usr/bin/env python3
import json
import logging
import sys

import requests
from airbyte_cdk.sources.streams.http.auth import TokenAuthenticator

from source_yandex_metrica.source import SourceYandexMetrica
from source_yandex_metrica.streams import Sessions

config = json.load(open(sys.argv[1]))
src = SourceYandexMetrica()
config = dict(config)
config["end_date"] = src.get_end_date(config=config)
print("dates", config["start_date"], config["end_date"])
auth = TokenAuthenticator(token=config.get("auth_token"))
print("auth header", auth.get_auth_header())
stream = Sessions(authenticator=auth, config=config)
fields = ",".join(stream.get_request_fields())
url = f"{stream.url_base}{stream.counter_id}/logrequests/evaluate"
params = {
    "date1": config.get("start_date"),
    "date2": config.get("end_date"),
    "source": "visits",
    "fields": fields,
}
headers = dict(stream.request_headers(stream_state={}), **auth.get_auth_header())
resp = requests.get(url, headers=headers, params=params, timeout=60)
print("status", resp.status_code)
print(resp.text[:500])
