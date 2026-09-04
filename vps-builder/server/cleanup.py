import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_TEMP_DIR = "/tmp/polylab"


def cleanup_workspace(build_id: str):
    workspace = Path(BASE_TEMP_DIR) / build_id
    if workspace.exists():
        shutil.rmtree(workspace, ignore_errors=True)
        logger.info(f"Cleaned up workspace: {workspace}")


def cleanup_all():
    base = Path(BASE_TEMP_DIR)
    if base.exists():
        shutil.rmtree(base, ignore_errors=True)
        logger.info(f"Cleaned up all workspaces: {base}")
