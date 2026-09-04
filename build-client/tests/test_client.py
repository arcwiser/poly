import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from client.api import PolylabClient
from client.verifier import compute_sha256, verify_artifact
from client.report import generate_report
from client.experiments import ExperimentResult


SERVER_URL = os.environ.get("POLYLAB_SERVER", "http://localhost:8000")
API_TOKEN = os.environ.get("POLYLAB_API_TOKEN", "")


def test_api_connection():
    client = PolylabClient(SERVER_URL, API_TOKEN)
    health = client.health()
    assert health.get("status") == "ok"
    print("  API connection: PASS")


def test_server_info():
    client = PolylabClient(SERVER_URL, API_TOKEN)
    info = client.info()
    assert "allowed_projects" in info
    assert "hello-world" in info["allowed_projects"]
    print("  Server info: PASS")


def test_sha256():
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(b"test content")
        path = f.name
    try:
        sha = compute_sha256(path)
        assert len(sha) == 64
        assert verify_artifact(path, sha)
        print("  SHA-256 verification: PASS")
    finally:
        os.unlink(path)


def test_report_generation():
    results = [
        ExperimentResult(seed=1, success=True, sha256="abc123", file_size=1000, text_size=500, test_passed=True),
        ExperimentResult(seed=2, success=True, sha256="def456", file_size=1100, text_size=550, test_passed=True),
    ]
    report = generate_report(results)
    assert "Unique SHA-256 hashes" in report
    assert "2" in report
    print("  Report generation: PASS")


if __name__ == "__main__":
    print("=== Client Unit Tests ===")
    test_sha256()
    test_report_generation()
    print("\nAll client unit tests passed!")
