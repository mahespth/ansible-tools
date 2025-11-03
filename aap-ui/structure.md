aap_tui/
├── pyproject.toml
├── src/
│   └── aap_tui/
│       ├── __init__.py
│       ├── app.py                 # Textual App subclass, routing
│       ├── ui/
│       │   ├── screens/
│       │   │   ├── home.py
│       │   │   ├── list_view.py   # virtualized table
│       │   │   ├── job_detail.py  # stdout/events viewer
│       │   │   └── launch_form.py
│       │   └── widgets/
│       │       ├── sidebar.py
│       │       ├── log_viewer.py
│       │       └── yaml_editor.py
│       ├── services/
│       │   ├── controller.py      # REST client for /api/v2
│       │   ├── eda.py             # optional /api/eda/v1
│       │   └── auth.py            # token mgmt, keyring
│       ├── models/                # pydantic DTOs
│       │   ├── common.py
│       │   ├── jobs.py
│       │   ├── templates.py
│       │   └── inventories.py
│       ├── state/
│       │   ├── config.py          # TOML load/save
│       │   └── cache.py           # sqlite/diskcache
│       └── cli.py                 # entrypoint (typer/click)
└── tests/
    ├── test_api_client.py
    └── test_log_follow.py