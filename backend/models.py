from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class UserCredentials(BaseModel):
    username: str
    password: str

class UserInfo(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    ad_groups: List[str] = []
    is_admin: bool = False

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo

class FileMetadata(BaseModel):
    id: int
    file_path: str
    filename: str
    file_type: Optional[str] = None
    size: int
    owner_id: int
    parent_path: Optional[str] = None
    is_folder: bool
    created_at: datetime
    modified_at: datetime
    permissions: Optional[str] = None
    owner_name: Optional[str] = None

class FileCreate(BaseModel):
    filename: str
    parent_path: str = "/"
    is_folder: bool = False

class FileOperation(BaseModel):
    source_path: str
    destination_path: Optional[str] = None
    new_name: Optional[str] = None

class ShareCreate(BaseModel):
    file_path: str
    shared_with_username: Optional[str] = None
    shared_with_group: Optional[str] = None
    permission: str = "read"  # read, write, full

class ShareInfo(BaseModel):
    id: int
    file_path: Optional[str] = None
    filename: Optional[str] = None
    shared_by: str
    shared_with_username: Optional[str] = None
    shared_with_group: Optional[str] = None
    permission_level: str
    created_at: datetime

class AuditLog(BaseModel):
    id: int
    username: str
    action: str
    resource: Optional[str] = None
    details: Optional[str] = None
    timestamp: datetime

class StorageStats(BaseModel):
    total_files: int
    total_size: int
    user_count: int
    recent_activity: int
