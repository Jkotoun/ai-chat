"""Print the OpenAPI spec, the input for the frontend's generated API client.

Usage: python -m app.export_openapi > openapi.json
"""

import json

from app.main import create_app

if __name__ == "__main__":
    print(json.dumps(create_app().openapi(), indent=2))
