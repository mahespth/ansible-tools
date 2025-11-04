from typing import Any, Dict, Optional
import httpx

class ControllerClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0, verify_ssl: bool = True):
        self.base = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            verify=verify_ssl,
        )

    def list(self, path: str, **params) -> Dict[str, Any]:
        r = self._client.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def get(self, path: str, **params) -> Dict[str, Any]:
        r = self._client.get(path, params=params)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        r = self._client.post(path, json=json or {})
        r.raise_for_status()
        return r.json()

    # convenience
    def job(self, job_id: int):
        return self.get(f"/jobs/{job_id}/")

    def job_events(self, job_id: int, **params):
        params.setdefault("order_by", "counter")
        params.setdefault("page_size", 200)
        return self.list(f"/jobs/{job_id}/job_events/", **params)

    def job_stdout_txt(self, job_id: int, fmt: str = "txt"):
        r = self._client.get(f"/jobs/{job_id}/stdout/", params={"format": fmt})
        r.raise_for_status()
        return r.text
