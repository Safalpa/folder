import os
import shutil
import aiofiles
import mimetypes
import logging
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import UploadFile, HTTPException
from config import settings
from database import postgres
from permissions import permission_manager, PermissionLevel

logger = logging.getLogger(__name__)

class FileManager:
    """
    Manages file system operations and metadata
    USER-ISOLATED: /data/secure-vault/<username>/
    """

    def __init__(self):
        self.storage_root = Path(settings.storage_root)
        self.max_file_size = settings.max_file_size
        self.storage_root.mkdir(parents=True, exist_ok=True)

    # ------------------ helpers ------------------

    def _normalize_path(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        normalized = os.path.normpath(path)
        if ".." in normalized or not normalized.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid path")
        return normalized

    def _user_root(self, username: str) -> Path:
        root = self.storage_root / username
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _get_absolute_path(self, username: str, relative_path: str) -> Path:
        normalized = self._normalize_path(relative_path)
        user_root = self._user_root(username)
        abs_path = user_root / normalized.lstrip("/")
        abs_path.resolve().relative_to(user_root.resolve())
        return abs_path

    def get_file_type(self, file_path: Path) -> str:
        mime, _ = mimetypes.guess_type(str(file_path))
        return mime or "application/octet-stream"

    def _check_permission(
        self,
        file_id: int,
        user_id: int,
        required_permission: str,
        user_groups: List[str] = None
    ) -> bool:
        """Check if user has required permission on file"""
        has_permission = permission_manager.check_permission(
            user_id=user_id,
            file_id=file_id,
            required_permission=required_permission,
            user_groups=user_groups or []
        )
        if not has_permission:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied: {required_permission} permission required"
            )
        return True

    def _get_file_id_and_owner(self, path: str, username: str) -> Optional[Dict]:
        """Get file ID and owner info from database"""
        with postgres.get_cursor() as cursor:
            # First try to find by exact path match
            cursor.execute(
                """
                SELECT f.id, f.owner_id, u.username as owner_username
                FROM files f
                JOIN users u ON f.owner_id = u.id
                WHERE f.path = %s AND u.username = %s
                """,
                (path, username)
            )
            row = cursor.fetchone()
            return row if row else None

    # ------------------ operations ------------------

    async def create_folder(self, path: str, owner_id: int, username: str) -> Dict:
        path = self._normalize_path(path)
        abs_path = self._get_absolute_path(username, path)

        if abs_path.exists():
            raise HTTPException(status_code=400, detail="Folder already exists")

        abs_path.mkdir(parents=True)

        parent_path = "/" if path.count("/") == 1 else path.rsplit("/", 1)[0]

        with postgres.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO files
                (owner_id, filename, path, parent_path, is_folder)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING *
                """,
                (owner_id, abs_path.name, path, parent_path),
            )
            return cursor.fetchone()

    async def upload_file(
        self,
        file: UploadFile,
        parent_path: str,
        owner_id: int,
        username: str,
    ) -> Dict:
        parent_path = self._normalize_path(parent_path)
        file_path = f"{parent_path.rstrip('/')}/{file.filename}"
        abs_path = self._get_absolute_path(username, file_path)

        file.file.seek(0, os.SEEK_END)
        size = file.file.tell()
        file.file.seek(0)

        if size > self.max_file_size:
            raise HTTPException(status_code=413, detail="File too large")

        abs_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(abs_path, "wb") as f:
            await f.write(await file.read())

        mime_type = self.get_file_type(abs_path)

        with postgres.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO files
                (owner_id, filename, path, parent_path, is_folder, size, mime_type)
                VALUES (%s, %s, %s, %s, FALSE, %s, %s)
                RETURNING *
                """,
                (owner_id, file.filename, file_path, parent_path, size, mime_type),
            )
            return cursor.fetchone()

    async def list_directory(self, path: str, user_id: int, username: str) -> List[Dict]:
        path = self._normalize_path(path)

        # Ensure folder exists on disk
        abs_path = self._get_absolute_path(username, path)
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="Directory not found")

        with postgres.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM files
                WHERE parent_path = %s AND owner_id = %s
                ORDER BY is_folder DESC, filename ASC
                """,
                (path, user_id),
            )
            return cursor.fetchall()

    async def rename_file(
        self,
        old_path: str,
        new_name: str,
        user_id: int,
        username: str,
        user_groups: List[str] = None
    ) -> Dict:
        old_path = self._normalize_path(old_path)
        
        # Get file info and check permission
        file_info = self._get_file_id_and_owner(old_path, username)
        if file_info:
            # File exists, check permission
            self._check_permission(
                file_id=file_info['id'],
                user_id=user_id,
                required_permission=PermissionLevel.WRITE,
                user_groups=user_groups
            )
        
        abs_old = self._get_absolute_path(username, old_path)

        if not abs_old.exists():
            raise HTTPException(status_code=404, detail="Not found")

        parent_path = "/" if old_path.count("/") == 1 else old_path.rsplit("/", 1)[0]
        new_path = f"{parent_path}/{new_name}"
        abs_old.rename(self._get_absolute_path(username, new_path))

        with postgres.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE files
                SET filename=%s, path=%s
                WHERE path=%s AND owner_id=%s
                RETURNING *
                """,
                (new_name, new_path, old_path, user_id),
            )
            return cursor.fetchone()

    async def delete_file(
        self,
        path: str,
        user_id: int,
        username: str,
        user_groups: List[str] = None
    ) -> bool:
        path = self._normalize_path(path)
        
        # Get file info and check permission
        file_info = self._get_file_id_and_owner(path, username)
        if file_info:
            # File exists, check permission (need FULL for delete)
            self._check_permission(
                file_id=file_info['id'],
                user_id=user_id,
                required_permission=PermissionLevel.FULL,
                user_groups=user_groups
            )
        
        abs_path = self._get_absolute_path(username, path)

        if abs_path.exists():
            if abs_path.is_dir():
                shutil.rmtree(abs_path)
            else:
                abs_path.unlink()

        with postgres.get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM files WHERE path=%s AND owner_id=%s",
                (path, user_id),
            )
        return True

    async def move_file(
        self,
        source_path: str,
        dest_parent: str,
        user_id: int,
        username: str,
    ) -> Dict:
        source_path = self._normalize_path(source_path)
        dest_parent = self._normalize_path(dest_parent)

        src_abs = self._get_absolute_path(username, source_path)
        dest_path = f"{dest_parent}/{src_abs.name}"
        dest_abs = self._get_absolute_path(username, dest_path)

        dest_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_abs), str(dest_abs))

        with postgres.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE files
                SET path=%s, parent_path=%s
                WHERE path=%s AND owner_id=%s
                RETURNING *
                """,
                (dest_path, dest_parent, source_path, user_id),
            )
            return cursor.fetchone()

    async def copy_file(
        self,
        source_path: str,
        dest_parent: str,
        user_id: int,
        username: str,
    ) -> Dict:
        source_path = self._normalize_path(source_path)
        dest_parent = self._normalize_path(dest_parent)

        src_abs = self._get_absolute_path(username, source_path)
        dest_path = f"{dest_parent}/{src_abs.name}"
        dest_abs = self._get_absolute_path(username, dest_path)

        if src_abs.is_dir():
            shutil.copytree(src_abs, dest_abs)
            size = 0
            mime = None
            is_folder = True
        else:
            shutil.copy2(src_abs, dest_abs)
            size = dest_abs.stat().st_size
            mime = self.get_file_type(dest_abs)
            is_folder = False

        with postgres.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO files
                (owner_id, filename, path, parent_path, is_folder, size, mime_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (user_id, src_abs.name, dest_path, dest_parent, is_folder, size, mime),
            )
            return cursor.fetchone()
