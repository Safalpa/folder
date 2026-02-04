import os
import shutil
import aiofiles
import magic
import logging
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime, timezone
from fastapi import UploadFile, HTTPException
from config import settings
from database import postgres

logger = logging.getLogger(__name__)

class FileManager:
    """Manages file system operations and metadata"""
    
    def __init__(self):
        self.storage_root = Path(settings.storage_root)
        self.max_file_size = settings.max_file_size
        
        # Ensure storage root exists
        self.storage_root.mkdir(parents=True, exist_ok=True)
    
    def _normalize_path(self, path: str) -> str:
        """Normalize path and prevent directory traversal"""
        if not path.startswith('/'):
            path = '/' + path
        
        # Remove any .. or dangerous patterns
        normalized = os.path.normpath(path)
        if '..' in normalized or not normalized.startswith('/'):
            raise HTTPException(status_code=400, detail="Invalid path")
        
        return normalized
    
    def _get_absolute_path(self, relative_path: str) -> Path:
        """Convert relative path to absolute system path"""
        normalized = self._normalize_path(relative_path)
        abs_path = self.storage_root / normalized.lstrip('/')
        
        # Ensure path is within storage root
        try:
            abs_path.resolve().relative_to(self.storage_root.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Path outside storage root")
        
        return abs_path
    
    def get_file_type(self, file_path: Path) -> str:
        """Detect file type using magic"""
        try:
            mime = magic.Magic(mime=True)
            return mime.from_file(str(file_path))
        except:
            return "application/octet-stream"
    
    async def create_folder(self, path: str, owner_id: int) -> Dict:
        """Create a new folder"""
        abs_path = self._get_absolute_path(path)
        
        if abs_path.exists():
            raise HTTPException(status_code=400, detail="Folder already exists")
        
        abs_path.mkdir(parents=True, exist_ok=True)
        
        # Save metadata to database
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO files (file_path, filename, file_type, size, owner_id, parent_path, is_folder)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, file_path, filename, size, owner_id, is_folder, created_at, modified_at
            """, (path, abs_path.name, 'folder', 0, owner_id, str(Path(path).parent), True))
            result = cursor.fetchone()
        
        return dict(result)
    
    async def upload_file(self, file: UploadFile, parent_path: str, owner_id: int) -> Dict:
        """Upload a file"""
        # Validate file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > self.max_file_size:
            raise HTTPException(status_code=413, detail=f"File too large. Max size: {self.max_file_size} bytes")
        
        # Create destination path
        file_path = f"{parent_path.rstrip('/')}/{file.filename}"
        abs_path = self._get_absolute_path(file_path)
        
        # Ensure parent directory exists
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save file
        async with aiofiles.open(abs_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Detect file type
        file_type = self.get_file_type(abs_path)
        
        # Save metadata
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO files (file_path, filename, file_type, size, owner_id, parent_path, is_folder)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, file_path, filename, file_type, size, owner_id, is_folder, created_at, modified_at
            """, (file_path, file.filename, file_type, file_size, owner_id, parent_path, False))
            result = cursor.fetchone()
        
        return dict(result)
    
    async def list_directory(self, path: str, user_id: int) -> List[Dict]:
        """List files and folders in directory"""
        normalized_path = self._normalize_path(path)
        
        with postgres.get_cursor() as cursor:
            # Get files owned by user or shared with user
            cursor.execute("""
                SELECT DISTINCT f.*, u.username as owner_name, s.permission
                FROM files f
                LEFT JOIN users u ON f.owner_id = u.id
                LEFT JOIN shares s ON f.id = s.file_id AND s.shared_with = %s
                WHERE (f.parent_path = %s AND f.owner_id = %s) OR (f.parent_path = %s AND s.shared_with = %s)
                ORDER BY f.is_folder DESC, f.filename ASC
            """, (user_id, normalized_path, user_id, normalized_path, user_id))
            results = cursor.fetchall()
        
        return [dict(row) for row in results]
    
    async def rename_file(self, old_path: str, new_name: str, user_id: int) -> Dict:
        """Rename a file or folder"""
        old_abs_path = self._get_absolute_path(old_path)
        
        if not old_abs_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        parent = old_abs_path.parent
        new_abs_path = parent / new_name
        
        # Rename on filesystem
        old_abs_path.rename(new_abs_path)
        
        # Update database
        new_path = f"{Path(old_path).parent}/{new_name}"
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                UPDATE files SET file_path = %s, filename = %s, modified_at = CURRENT_TIMESTAMP
                WHERE file_path = %s AND owner_id = %s
                RETURNING id, file_path, filename, size, owner_id, is_folder, created_at, modified_at
            """, (new_path, new_name, old_path, user_id))
            result = cursor.fetchone()
        
        return dict(result) if result else None
    
    async def delete_file(self, path: str, user_id: int) -> bool:
        """Delete a file or folder"""
        abs_path = self._get_absolute_path(path)
        
        if not abs_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Delete from filesystem
        if abs_path.is_dir():
            shutil.rmtree(abs_path)
        else:
            abs_path.unlink()
        
        # Delete from database
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM files WHERE file_path = %s AND owner_id = %s
            """, (path, user_id))
        
        return True
    
    async def move_file(self, source_path: str, dest_parent: str, user_id: int) -> Dict:
        """Move file or folder to new location"""
        source_abs = self._get_absolute_path(source_path)
        dest_path = f"{dest_parent.rstrip('/')}/{source_abs.name}"
        dest_abs = self._get_absolute_path(dest_path)
        
        if not source_abs.exists():
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Move on filesystem
        dest_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_abs), str(dest_abs))
        
        # Update database
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                UPDATE files SET file_path = %s, parent_path = %s, modified_at = CURRENT_TIMESTAMP
                WHERE file_path = %s AND owner_id = %s
                RETURNING id, file_path, filename, size, owner_id, is_folder, created_at, modified_at
            """, (dest_path, dest_parent, source_path, user_id))
            result = cursor.fetchone()
        
        return dict(result) if result else None
    
    async def copy_file(self, source_path: str, dest_parent: str, user_id: int) -> Dict:
        """Copy file or folder to new location"""
        source_abs = self._get_absolute_path(source_path)
        dest_path = f"{dest_parent.rstrip('/')}/{source_abs.name}"
        dest_abs = self._get_absolute_path(dest_path)
        
        if not source_abs.exists():
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Copy on filesystem
        dest_abs.parent.mkdir(parents=True, exist_ok=True)
        if source_abs.is_dir():
            shutil.copytree(str(source_abs), str(dest_abs))
        else:
            shutil.copy2(str(source_abs), str(dest_abs))
        
        # Create metadata entry
        file_size = dest_abs.stat().st_size if dest_abs.is_file() else 0
        file_type = self.get_file_type(dest_abs) if dest_abs.is_file() else 'folder'
        
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO files (file_path, filename, file_type, size, owner_id, parent_path, is_folder)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, file_path, filename, size, owner_id, is_folder, created_at, modified_at
            """, (dest_path, dest_abs.name, file_type, file_size, user_id, dest_parent, dest_abs.is_dir()))
            result = cursor.fetchone()
        
        return dict(result)

file_manager = FileManager()
