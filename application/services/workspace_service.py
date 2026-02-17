"""
Workspace Service

Manages multiple working directories (workspaces) for the user.
Allows adding, removing, and switching between different folders on the server.
"""

import os
import logging
from typing import List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import json

from domain.value_objects.project_path import ProjectPath

logger = logging.getLogger(__name__)


@dataclass
class Workspace:
    """Represents a workspace (working directory)"""
    id: str
    name: str
    path: str
    is_default: bool = False
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class WorkspaceService:
    """
    Service for managing multiple workspaces.

    Features:
    - Add any folder as a workspace
    - Switch between workspaces
    - Persist workspace list
    - Quick access to recent workspaces
    """

    def __init__(self, storage_path: str = "data/workspaces.json"):
        # Initialize default workspaces dynamically based on OS
        root_path = ProjectPath.ROOT
        self.DEFAULT_WORKSPACES = {
            root_path: "Projects",
            os.path.dirname(root_path) if root_path != "/" else "/": "Root",
            "/app": "App",
            "/tmp": "Temp" if os.name != 'nt' else os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp")
        }

    def __init__(self, storage_path: str = "data/workspaces.json"):
        self.storage_path = storage_path
        self._workspaces: dict[str, Workspace] = {}
        self._current_workspace_id: Optional[str] = None
        self._load_workspaces()

    def _load_workspaces(self):
        """Load workspaces from storage"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for ws_data in data.get('workspaces', []):
                        ws = Workspace(**ws_data)
                        self._workspaces[ws.id] = ws
                    self._current_workspace_id = data.get('current_workspace_id')
                logger.info(f"Loaded {len(self._workspaces)} workspaces")
            except Exception as e:
                logger.error(f"Error loading workspaces: {e}")
                self._init_default_workspaces()
        else:
            self._init_default_workspaces()

    def _save_workspaces(self):
        """Save workspaces to storage"""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            data = {
                'workspaces': [asdict(ws) for ws in self._workspaces.values()],
                'current_workspace_id': self._current_workspace_id
            }
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving workspaces: {e}")

    def _init_default_workspaces(self):
        """Initialize with default workspaces"""
        for path, name in self.DEFAULT_WORKSPACES.items():
            if os.path.exists(path):
                self.add_workspace(path, name, is_default=True)
        # Set first workspace as current
        if self._workspaces:
            self._current_workspace_id = list(self._workspaces.keys())[0]
        self._save_workspaces()

    def add_workspace(self, path: str, name: Optional[str] = None, is_default: bool = False) -> Optional[Workspace]:
        """
        Add a new workspace.

        Args:
            path: Folder path
            name: Display name (optional, defaults to folder name)
            is_default: Whether this is a default workspace

        Returns:
            Created workspace or None if invalid path
        """
        # Validate path
        if not os.path.isdir(path):
            logger.warning(f"Cannot add workspace: {path} is not a valid directory")
            return None

        # Normalize path
        path = os.path.normpath(os.path.abspath(path))

        # Check if already exists
        for ws in self._workspaces.values():
            if ws.path == path:
                logger.info(f"Workspace already exists: {path}")
                return ws

        # Generate ID
        ws_id = f"ws_{len(self._workspaces)}_{int(datetime.now().timestamp())}"

        # Use folder name if no name provided
        if not name:
            name = os.path.basename(path) or path

        workspace = Workspace(
            id=ws_id,
            name=name,
            path=path,
            is_default=is_default
        )

        self._workspaces[ws_id] = workspace
        self._save_workspaces()

        logger.info(f"Added workspace: {name} at {path}")
        return workspace

    def remove_workspace(self, workspace_id: str) -> bool:
        """
        Remove a workspace.

        Args:
            workspace_id: Workspace ID to remove

        Returns:
            True if removed, False if not found or is default
        """
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return False

        if ws.is_default:
            logger.warning(f"Cannot remove default workspace: {ws.name}")
            return False

        del self._workspaces[workspace_id]

        # If current workspace was removed, switch to another
        if self._current_workspace_id == workspace_id:
            self._current_workspace_id = next(iter(self._workspaces.keys()), None)

        self._save_workspaces()
        logger.info(f"Removed workspace: {ws.name}")
        return True

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        """Get workspace by ID"""
        return self._workspaces.get(workspace_id)

    def get_current_workspace(self) -> Optional[Workspace]:
        """Get currently active workspace"""
        if self._current_workspace_id:
            return self._workspaces.get(self._current_workspace_id)
        return None

    def get_current_path(self) -> str:
        """Get current workspace path or default"""
        ws = self.get_current_workspace()
        if ws:
            return ws.path
        return ProjectPath.ROOT  # Fallback

    def set_current_workspace(self, workspace_id: str) -> bool:
        """
        Set current workspace.

        Args:
            workspace_id: Workspace ID to switch to

        Returns:
            True if switched, False if not found
        """
        if workspace_id not in self._workspaces:
            return False

        self._current_workspace_id = workspace_id
        self._save_workspaces()

        ws = self._workspaces[workspace_id]
        logger.info(f"Switched to workspace: {ws.name} at {ws.path}")
        return True

    def list_workspaces(self) -> List[Workspace]:
        """List all workspaces"""
        return list(self._workspaces.values())

    def get_workspace_by_path(self, path: str) -> Optional[Workspace]:
        """Find workspace by path"""
        path = os.path.normpath(os.path.abspath(path))
        for ws in self._workspaces.values():
            if ws.path == path:
                return ws
        return None

    def rename_workspace(self, workspace_id: str, new_name: str) -> bool:
        """
        Rename a workspace.

        Args:
            workspace_id: Workspace ID
            new_name: New display name

        Returns:
            True if renamed, False if not found
        """
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return False

        ws.name = new_name
        self._save_workspaces()
        return True
