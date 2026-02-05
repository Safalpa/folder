"""
ACL / Permission Management Module
Application-layer permission enforcement for files and folders
"""

import logging
from typing import Optional, List, Dict, Tuple
from fastapi import HTTPException
from database import postgres

logger = logging.getLogger(__name__)


class PermissionLevel:
    """Permission level constants"""
    READ = "read"
    WRITE = "write"
    FULL = "full"
    
    @classmethod
    def validate(cls, level: str) -> str:
        """Validate permission level"""
        level = level.lower()
        if level not in [cls.READ, cls.WRITE, cls.FULL]:
            raise ValueError(f"Invalid permission level: {level}")
        return level
    
    @classmethod
    def rank(cls, level: str) -> int:
        """Get numeric rank for permission level"""
        ranks = {cls.READ: 1, cls.WRITE: 2, cls.FULL: 3}
        return ranks.get(level, 0)


class PermissionManager:
    """Manages file/folder permissions and ACLs"""
    
    def __init__(self):
        pass
    
    def check_permission(
        self,
        user_id: int,
        file_id: int,
        required_permission: str,
        user_groups: List[str] = None
    ) -> bool:
        """
        Check if user has required permission on a file/folder
        
        Args:
            user_id: User ID
            file_id: File ID
            required_permission: 'read', 'write', or 'full'
            user_groups: List of AD groups user belongs to
            
        Returns:
            True if user has permission, False otherwise
        """
        user_groups = user_groups or []
        required_permission = PermissionLevel.validate(required_permission)
        
        # Get effective permission
        effective_perm = self.get_effective_permission(user_id, file_id, user_groups)
        
        if not effective_perm:
            return False
        
        # Check if effective permission meets requirement
        return PermissionLevel.rank(effective_perm) >= PermissionLevel.rank(required_permission)
    
    def get_effective_permission(
        self,
        user_id: int,
        file_id: int,
        user_groups: List[str] = None
    ) -> Optional[str]:
        """
        Get the highest effective permission a user has on a file
        
        Returns: 'read', 'write', 'full', or None
        """
        user_groups = user_groups or []
        
        with postgres.get_cursor() as cursor:
            # Check if user is owner (full permission)
            cursor.execute(
                "SELECT owner_id FROM files WHERE id = %s",
                (file_id,)
            )
            row = cursor.fetchone()
            if row and row['owner_id'] == user_id:
                return PermissionLevel.FULL
            
            # Check direct user permissions
            cursor.execute(
                """
                SELECT permission_level
                FROM file_permissions
                WHERE file_id = %s AND shared_with_user_id = %s
                ORDER BY 
                    CASE permission_level
                        WHEN 'full' THEN 3
                        WHEN 'write' THEN 2
                        WHEN 'read' THEN 1
                    END DESC
                LIMIT 1
                """,
                (file_id, user_id)
            )
            row = cursor.fetchone()
            if row:
                return row['permission_level']
            
            # Check group permissions
            if user_groups:
                cursor.execute(
                    """
                    SELECT permission_level
                    FROM file_permissions
                    WHERE file_id = %s AND shared_with_group = ANY(%s)
                    ORDER BY 
                        CASE permission_level
                            WHEN 'full' THEN 3
                            WHEN 'write' THEN 2
                            WHEN 'read' THEN 1
                        END DESC
                    LIMIT 1
                    """,
                    (file_id, user_groups)
                )
                row = cursor.fetchone()
                if row:
                    return row['permission_level']
        
        return None
    
    def share_file(
        self,
        file_id: int,
        shared_by_user_id: int,
        shared_with_username: Optional[str] = None,
        shared_with_group: Optional[str] = None,
        permission_level: str = PermissionLevel.READ
    ) -> int:
        """
        Share a file/folder with a user or group
        
        Args:
            file_id: File ID to share
            shared_by_user_id: User ID sharing the file
            shared_with_username: Username to share with (mutually exclusive with group)
            shared_with_group: AD group to share with (mutually exclusive with username)
            permission_level: 'read', 'write', or 'full'
            
        Returns:
            Permission ID
        """
        permission_level = PermissionLevel.validate(permission_level)
        
        # Validate that either username OR group is specified
        if not shared_with_username and not shared_with_group:
            raise HTTPException(
                status_code=400,
                detail="Must specify either username or group"
            )
        
        if shared_with_username and shared_with_group:
            raise HTTPException(
                status_code=400,
                detail="Cannot specify both username and group"
            )
        
        with postgres.get_cursor() as cursor:
            # Verify file exists and user has permission to share
            cursor.execute(
                "SELECT owner_id FROM files WHERE id = %s",
                (file_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="File not found")
            
            # Check if user has full permission (owner or explicit full permission)
            if row['owner_id'] != shared_by_user_id:
                # Non-owner must have 'full' permission to share
                cursor.execute(
                    """
                    SELECT permission_level
                    FROM file_permissions
                    WHERE file_id = %s AND shared_with_user_id = %s
                    """,
                    (file_id, shared_by_user_id)
                )
                perm_row = cursor.fetchone()
                if not perm_row or perm_row['permission_level'] != PermissionLevel.FULL:
                    raise HTTPException(
                        status_code=403,
                        detail="Only file owner or users with full permission can share"
                    )
            
            # Get shared_with_user_id if username provided
            shared_with_user_id = None
            if shared_with_username:
                cursor.execute(
                    "SELECT id FROM users WHERE username = %s",
                    (shared_with_username,)
                )
                user_row = cursor.fetchone()
                if not user_row:
                    raise HTTPException(
                        status_code=404,
                        detail=f"User '{shared_with_username}' not found"
                    )
                shared_with_user_id = user_row['id']
            
            # Check if permission already exists
            if shared_with_user_id:
                cursor.execute(
                    """
                    SELECT id, permission_level FROM file_permissions
                    WHERE file_id = %s AND shared_with_user_id = %s
                    """,
                    (file_id, shared_with_user_id)
                )
            else:
                cursor.execute(
                    """
                    SELECT id, permission_level FROM file_permissions
                    WHERE file_id = %s AND shared_with_group = %s
                    """,
                    (file_id, shared_with_group)
                )
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing permission
                cursor.execute(
                    """
                    UPDATE file_permissions
                    SET permission_level = %s, created_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    RETURNING id
                    """,
                    (permission_level, existing['id'])
                )
                return existing['id']
            else:
                # Create new permission
                cursor.execute(
                    """
                    INSERT INTO file_permissions
                    (file_id, shared_by_user_id, shared_with_user_id, shared_with_group, permission_level)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (file_id, shared_by_user_id, shared_with_user_id, shared_with_group, permission_level)
                )
                row = cursor.fetchone()
                return row['id']
    
    def unshare_file(
        self,
        permission_id: int,
        user_id: int
    ) -> bool:
        """
        Remove a file share permission
        
        Args:
            permission_id: Permission ID to remove
            user_id: User requesting removal (must be owner or share creator)
            
        Returns:
            True if removed
        """
        with postgres.get_cursor() as cursor:
            # Get permission details
            cursor.execute(
                """
                SELECT fp.*, f.owner_id
                FROM file_permissions fp
                JOIN files f ON fp.file_id = f.id
                WHERE fp.id = %s
                """,
                (permission_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Permission not found")
            
            # Check if user has authority to remove (owner or creator of share)
            if row['owner_id'] != user_id and row['shared_by_user_id'] != user_id:
                # Check if user has full permission
                cursor.execute(
                    """
                    SELECT permission_level FROM file_permissions
                    WHERE file_id = %s AND shared_with_user_id = %s
                    """,
                    (row['file_id'], user_id)
                )
                perm_row = cursor.fetchone()
                if not perm_row or perm_row['permission_level'] != PermissionLevel.FULL:
                    raise HTTPException(
                        status_code=403,
                        detail="Not authorized to remove this share"
                    )
            
            # Remove permission
            cursor.execute(
                "DELETE FROM file_permissions WHERE id = %s",
                (permission_id,)
            )
            return True
    
    def get_file_shares(self, file_id: int) -> List[Dict]:
        """Get all shares for a file"""
        with postgres.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT 
                    fp.id,
                    fp.permission_level,
                    fp.created_at,
                    u_by.username as shared_by,
                    u_with.username as shared_with_username,
                    fp.shared_with_group
                FROM file_permissions fp
                JOIN users u_by ON fp.shared_by_user_id = u_by.id
                LEFT JOIN users u_with ON fp.shared_with_user_id = u_with.id
                WHERE fp.file_id = %s
                ORDER BY fp.created_at DESC
                """,
                (file_id,)
            )
            return cursor.fetchall()
    
    def get_shared_with_me(
        self,
        user_id: int,
        user_groups: List[str] = None
    ) -> List[Dict]:
        """
        Get all files shared with a user (directly or via groups)
        
        Returns list of files with permission info
        """
        user_groups = user_groups or []
        
        with postgres.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT
                    f.id,
                    f.filename,
                    f.path,
                    f.is_folder,
                    f.size,
                    f.mime_type,
                    f.created_at,
                    f.modified_at,
                    u_owner.username as owner_username,
                    u_owner.display_name as owner_display_name,
                    fp.permission_level,
                    fp.id as permission_id
                FROM file_permissions fp
                JOIN files f ON fp.file_id = f.id
                JOIN users u_owner ON f.owner_id = u_owner.id
                WHERE 
                    fp.shared_with_user_id = %s
                    OR (fp.shared_with_group = ANY(%s) AND %s)
                ORDER BY f.modified_at DESC
                """,
                (user_id, user_groups, len(user_groups) > 0)
            )
            return cursor.fetchall()
    
    def get_file_id_by_path(self, path: str, owner_id: int) -> Optional[int]:
        """Get file ID by path and owner"""
        with postgres.get_cursor() as cursor:
            cursor.execute(
                "SELECT id FROM files WHERE path = %s AND owner_id = %s",
                (path, owner_id)
            )
            row = cursor.fetchone()
            return row['id'] if row else None


# Global instance
permission_manager = PermissionManager()
