# aap-tui

A Textual-based TUI for user-facing operations on Ansible Automation Platform (AAP) / AWX 2.5 Controller.

## Features (initial)
- View job details and stream live logs
- Basic controller client
- DTOs using Pydantic v2

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
aap-tui job 1234 --base https://controller.example.com/api/v2 --token $AWX_TOKEN
```
