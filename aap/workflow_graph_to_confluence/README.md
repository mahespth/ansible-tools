# AWX / AAP → Confluence Workflow Exporter

Steve Maher.

> **Generate living diagrams of your AWX or Red Hat Automation Platform workflows and publish them to Confluence – automatically.**

This repo contains two Ansible playbooks:

| Playbook | Purpose | Typical schedule |
|----------|---------|------------------|
| **`playbooks/export_workflow_image.yml`** | Render **one** Workflow Job Template (WJT) to **PNG/SVG** and optionally attach it to a Confluence page. | On-demand or whenever that workflow changes |
| **`playbooks/export_all_workflows_to_confluence.yml`** | Discover **all** WJTs, create/update a Confluence page, and embed a diagram for each workflow. | Nightly or after bulk edits |

Both playbooks run perfectly on your laptop (`ansible-playbook …`) **or** inside AWX/AAP as a Job Template.

---

## 1. Prerequisites

| Requirement | Notes |
|-------------|-------|
| **Ansible 2.12+** | AWX/AAP already bundles this. |
| **Graphviz** (`dot` binary) | `sudo dnf install graphviz` / `brew install graphviz`<br>Must also be present in your Execution Environment. |
| **community.general** collection | `ansible-galaxy collection install community.general` |
| **AWX/AAP OAuth Token** | Create under **_Users → Tokens_** (keep the string handy). |
| **Confluence credentials** | Either **username + password** or a **Personal Access Token**. |

---

## 2. Directory layout

```
repo-root/
├── playbooks/
│ ├── export_workflow_image.yml
│ └── export_all_workflows_to_confluence.yml
├── templates/
│ └── workflow.dot.j2
└── vars/
└── main.yml # (optional) shared defaults
```


> Feel free to rename folders; just update the `src:` and `vars_files:` paths inside the playbooks.


## 3. Common variable reference

Place these in `vars/main.yml`, pass with `--extra-vars`, or set them as AWX **Prompt-on-launch** fields.

| Variable | Meaning |
|----------|---------|
| `awx_host` | Base URL of your AWX/AAP instance – **no trailing slash**. |
| `awx_oauthtoken` | OAuth token value. Recommended: inject via environment variable `AWX_TOKEN`. |
| `graph_render_format` | `png` (default) or `svg`. |
| `tmp_dir` | Working folder inside the controller / container. |
| Confluence-specific → | |
| `confluence_base_url` | e.g. `https://confluence.example.com` |
| `confluence_user` / `confluence_token` | Credentials (use env vars `CONFLUENCE_USER` & `CONFLUENCE_TOKEN`). |
| `confluence_space` | Target space key, e.g. `DEV`. |

---

## 4. `export_workflow_image.yml` – single workflow

### Required variables

| Variable | One of two is enough | Example |
|----------|----------------------|---------|
| `workflow_id` | **OR** | `42` |
| `workflow_name` | | `Nightly Build` |

### Optional variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `attach_to_confluence` | `false` | Upload the image to Confluence. |
| `confluence_page_id` | – | The page that should receive the attachment. |

### Run it locally

```bash
export AWX_TOKEN=***
ansible-playbook playbooks/export_workflow_image.yml \
  --extra-vars '{
    "awx_host":"https://awx.example.com",
    "workflow_name":"Nightly Build",
    "graph_render_format":"svg"
  }'

```


