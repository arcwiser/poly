import json
import hashlib
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, Tuple


class ClientAPI:
    def __init__(self, server_url: str, api_token: str):
        self.server_url = server_url.rstrip("/")
        self.api_token = api_token

    def _make_request(
        self,
        method: str,
        path: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bytes, Dict[str, str]]:
        url = f"{self.server_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")

        req = urllib.request.Request(
            url, data=body, headers=headers, method=method
        )

        try:
            resp = urllib.request.urlopen(req, timeout=120)
            response_headers = dict(resp.headers)
            response_body = resp.read()
            return response_body, response_headers
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            try:
                error_detail = json.loads(error_body)
                detail = error_detail.get("detail", error_body)
            except json.JSONDecodeError:
                detail = error_body
            raise APIError(
                f"HTTP {e.code}: {detail}"
            ) from e
        except urllib.error.URLError as e:
            raise APIError(
                f"Connection failed: {e.reason}"
            ) from e

    def health_check(self) -> Dict[str, Any]:
        body, _ = self._make_request("GET", "/health")
        return json.loads(body)

    def server_info(self) -> Dict[str, Any]:
        body, _ = self._make_request("GET", "/info")
        return json.loads(body)

    def request_build(
        self,
        seed: int,
        project: str = "hello-world",
        optimization: str = "O2",
        transformations: Optional[list] = None,
    ) -> Dict[str, Any]:
        payload = {
            "project": project,
            "seed": seed,
            "optimization": optimization,
        }
        if transformations is not None:
            payload["transformations"] = transformations

        artifact_bytes, headers = self._make_request(
            "POST", "/build", payload
        )

        manifest_json = headers.get("X-Build-Manifest", "{}")
        manifest = json.loads(manifest_json)

        return {
            "artifact_bytes": artifact_bytes,
            "manifest": manifest,
            "build_id": headers.get("X-Build-ID", ""),
            "seed": int(headers.get("X-Build-Seed", "0")),
            "elapsed": float(headers.get("X-Build-Elapsed", "0")),
        }


class APIError(Exception):
    pass
