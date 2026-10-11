"""Print the OpenAPI spec, the input for the frontend's generated API client.

Usage: python -m app.export_openapi > openapi.json
"""

import json

from app.main import app

if __name__ == "__main__":
    print(json.dumps(app.openapi(), indent=2))
