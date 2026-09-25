# test_nested_vars.py

from nested_vars import LookupModule

variables = {
    "workflow": {
        "start": {
            "name": "Start Environment",
            "nodes": [
                {"identifier": "start_db"},
                {"identifier": "start_app"},
            ],
        }
    }
}

plugin = LookupModule()

tests = [
    "workflow",
    "workflow.start",
    "workflow.start.name",
    "workflow.start.nodes",
    "workflow.start.nodes.0.identifier",
]

for test in tests:
    try:
        result = plugin.run([test], variables=variables)
        print(f"{test} -> {result}")
    except Exception as exc:
        print(f"{test} -> ERROR: {type(exc).__name__}: {exc}")
