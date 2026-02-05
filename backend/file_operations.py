"""
File Operations Manager

FILESYSTEM BEHAVIOR FOR SHARED FILES:
======================================
Physical Storage:
- All files physically stored at: /data/secure-vault/{owner_username}/...
- Shared files remain in owner's storage (NOT copied to recipient)

Path Resolution:
- Database stores logical paths (e.g., /documents/report.pdf)
- Operations resolve to owner's physical path
- Recipients access via same logical path

Example:
--------
Owner: alice, File: /reports/Q4.pdf
Physical: /data/secure-vault/alice/reports/Q4.pdf

Shared with Bob (READ permission):
- Bob sees file in listing: GET /api/files?path=/reports
- Bob downloads: GET /api/files/download?path=/reports/Q4.pdf
- System resolves to alice's physical storage
- No files in /data/secure-vault/bob/reports/

Permission Enforcement:
- FileManager checks ACL via PermissionManager
- Operations use owner's physical path
- Recipients never access files they don't have permission for
"""

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

    def _get_file_id_and_owner(self, path: str, owner_username: str) -> Optional[Dict]:
        """
        Get file ID and owner info from database
        Searches for file by path within the owner's namespace
        """
        with postgres.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT f.id, f.owner_id, u.username as owner_username
                FROM files f
                JOIN users u ON f.owner_id = u.id
                WHERE f.path = %s AND u.username = %s
                """,
                (path, owner_username)
            )
            row = cursor.fetchone()
            return row if row else None
    
    def _get_file_by_path_any_owner(self, path: str) -> Optional[Dict]:
        """
        Get file by path regardless of owner
        Used when accessing shared files
        """
        with postgres.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT f.id, f.owner_id, f.path, f.filename, f.is_folder,
                       u.username as owner_username
                FROM files f
                JOIN users u ON f.owner_id = u.id
                WHERE f.path = %s
                """,
                (path,)
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

    async def list_directory(
        self, 
        path: str, 
        user_id: int, 
        username: str,
        user_groups: List[str] = None
    ) -> List[Dict]:
        """
        List files in directory
        Returns both owned files AND files shared with the user
        
        Note: For shared folders, the physical files exist in the owner's storage,
        but they appear in the user's listing via ACL permissions.
        """
        path = self._normalize_path(path)
        user_groups = user_groups or []

        # Check if this is user's own folder
        abs_path = self._get_absolute_path(username, path)
        is_own_folder = abs_path.exists()
        
        # If not own folder, check if it's a shared folder we have access to
        if not is_own_folder:
            # Check if we have permission to any folder at this path
            with postgres.get_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT f.id, f.owner_id, u.username as owner_username
                    FROM files f
                    JOIN users u ON f.owner_id = u.id
                    JOIN file_permissions fp ON f.id = fp.file_id
                    WHERE f.path = %s AND f.is_folder = TRUE
                      AND (
                        fp.shared_with_user_id = %s
                        OR (fp.shared_with_group = ANY(%s) AND %s)
                      )
                    LIMIT 1
                    """,
                    (path, user_id, user_groups, len(user_groups) > 0)
                )
                shared_folder = cursor.fetchone()
                
                if not shared_folder:
                    raise HTTPException(status_code=404, detail="Directory not found")

        with postgres.get_cursor() as cursor:
            # Get owned files in this path
            cursor.execute(
                """
                SELECT f.*, u.username as owner_username, NULL as shared_permission
                FROM files f
                JOIN users u ON f.owner_id = u.id
                WHERE f.parent_path = %s AND f.owner_id = %s
                ORDER BY f.is_folder DESC, f.filename ASC
                """,
                (path, user_id),
            )
            owned_files = cursor.fetchall()
            
            # Get shared files in this directory (direct user OR group permissions)
            cursor.execute(
                """
                SELECT DISTINCT ON (f.id) f.*, u.username as owner_username, 
                       fp.permission_level as shared_permission
                FROM files f
                JOIN users u ON f.owner_id = u.id
                JOIN file_permissions fp ON f.id = fp.file_id
                WHERE f.parent_path = %s
                  AND f.owner_id != %s
                  AND (
                    fp.shared_with_user_id = %s
                    OR (fp.shared_with_group = ANY(%s) AND %s)
                  )
                ORDER BY f.id, f.is_folder DESC, f.filename ASC
                """,
                (path, user_id, user_id, user_groups, len(user_groups) > 0),
            )
            shared_files = cursor.fetchall()
            
            # Combine and return
            all_files = list(owned_files) + list(shared_files)
            return all_files

    async def rename_file(
        self,
        old_path: str,
        new_name: str,
        user_id: int,
        username: str,
        user_groups: List[str] = None
    ) -> Dict:
        old_path = self._normalize_path(old_path)
        user_groups = user_groups or []
        
        # Get file info - try owned first, then any file
        file_info = self._get_file_id_and_owner(old_path, username)
        if not file_info:
            # Not owned, check if it's a shared file
            file_info = self._get_file_by_path_any_owner(old_path)
        
        if file_info:
            # Check permission (need WRITE to rename)
            self._check_permission(
                file_id=file_info['id'],
                user_id=user_id,
                required_permission=PermissionLevel.WRITE,
                user_groups=user_groups
            )
            
            # Get actual owner's username for file operations
            owner_username = file_info['owner_username']
            owner_id = file_info['owner_id']
        else:
            raise HTTPException(status_code=404, detail="File not found")
        
        abs_old = self._get_absolute_path(owner_username, old_path)

        if not abs_old.exists():
            raise HTTPException(status_code=404, detail="File not found on disk")

        parent_path = "/" if old_path.count("/") == 1 else old_path.rsplit("/", 1)[0]
        new_path = f"{parent_path}/{new_name}"
        abs_new = self._get_absolute_path(owner_username, new_path)
        abs_old.rename(abs_new)

        with postgres.get_cursor() as cursor:
            # Update without owner_id restriction - permission already checked
            cursor.execute(
                """
                UPDATE files
                SET filename=%s, path=%s, modified_at=CURRENT_TIMESTAMP
                WHERE id=%s
                RETURNING *
                """,
                (new_name, new_path, file_info['id']),
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
        user_groups = user_groups or []
        
        # Get file info - try owned first, then any file
        file_info = self._get_file_id_and_owner(path, username)
        if not file_info:
            # Not owned, check if it's a shared file
            file_info = self._get_file_by_path_any_owner(path)
        
        if file_info:
            # Check permission (need FULL to delete)
            self._check_permission(
                file_id=file_info['id'],
                user_id=user_id,
                required_permission=PermissionLevel.FULL,
                user_groups=user_groups
            )
            
            # Get actual owner's username for file operations
            owner_username = file_info['owner_username']
        else:
            raise HTTPException(status_code=404, detail="File not found")
        
        abs_path = self._get_absolute_path(owner_username, path)

        if abs_path.exists():
            if abs_path.is_dir():
                shutil.rmtree(abs_path)
            else:
                abs_path.unlink()

        with postgres.get_cursor() as cursor:
            # Delete without owner_id restriction - permission already checked
            cursor.execute(
                "DELETE FROM files WHERE id=%s",
                (file_info['id'],),
            )
        return True

    async def move_file(
        self,
        source_path: str,
        dest_parent: str,
        user_id: int,
        username: str,
        user_groups: List[str] = None
    ) -> Dict:
        source_path = self._normalize_path(source_path)
        dest_parent = self._normalize_path(dest_parent)
        user_groups = user_groups or []

        # Get file info - try owned first, then any file
        file_info = self._get_file_id_and_owner(source_path, username)
        if not file_info:
            # Not owned, check if it's a shared file
            file_info = self._get_file_by_path_any_owner(source_path)
        
        if file_info:
            # Check permission (need WRITE to move)
            self._check_permission(
                file_id=file_info['id'],
                user_id=user_id,
                required_permission=PermissionLevel.WRITE,
                user_groups=user_groups
            )
            
            # Get actual owner's username for file operations
            owner_username = file_info['owner_username']
        else:
            raise HTTPException(status_code=404, detail="File not found")
        
        src_abs = self._get_absolute_path(owner_username, source_path)
        dest_path = f"{dest_parent}/{src_abs.name}"
        dest_abs = self._get_absolute_path(owner_username, dest_path)

        dest_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_abs), str(dest_abs))

        with postgres.get_cursor() as cursor:
            # Update without owner_id restriction - permission already checked
            cursor.execute(
                """
                UPDATE files
                SET path=%s, parent_path=%s, modified_at=CURRENT_TIMESTAMP
                WHERE id=%s
                RETURNING *
                """,
                (dest_path, dest_parent, file_info['id']),
            )
            return cursor.fetchone()

    async def copy_file(
        self,
        source_path: str,
        dest_parent: str,
        user_id: int,
        username: str,
        user_groups: List[str] = None
    ) -> Dict:
        source_path = self._normalize_path(source_path)
        dest_parent = self._normalize_path(dest_parent)
        user_groups = user_groups or []

        # Get file info - try owned first, then any file
        file_info = self._get_file_id_and_owner(source_path, username)
        if not file_info:
            # Not owned, check if it's a shared file
            file_info = self._get_file_by_path_any_owner(source_path)
        
        if file_info:
            # Check permission (need READ to copy)
            self._check_permission(
                file_id=file_info['id'],
                user_id=user_id,
                required_permission=PermissionLevel.READ,
                user_groups=user_groups
            )
            
            # Get actual owner's username for source file operations
            owner_username = file_info['owner_username']
        else:
            raise HTTPException(status_code=404, detail="File not found")
        
        src_abs = self._get_absolute_path(owner_username, source_path)
        dest_path = f"{dest_parent}/{src_abs.name}"
        # Destination goes to current user's space
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
            # New copy belongs to current user
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
