import dlt
from dlt.sources.rest_api import rest_api_source

source = rest_api_source({
    "client": {
        "base_url": "https://pokeapi.co/api/v2",
        "paginator": {
            "type": "json_link",
            "next_url_path": "next"
        },
    },
    "resource_defaults": {
        "endpoint": {
            "data_selector": "results",
            "params": {
                "limit": 100
            }
        }
    },
    "resources": [
        "pokemon",
        "type"
    ],
}).add_limit(3) # cap pages for a faster demo

pipeline = dlt.pipeline(
    pipeline_name = "pokeapi",
    destination = dlt.destinations.duckdb(
        "warehouse/elt.duckdb"
    ),
    dataset_name = "raw"
)

print(pipeline.run(source))