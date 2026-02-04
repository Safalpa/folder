from fastapi import FastAPI, APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.middleware.cors import CORSMiddleware
from typing import List, Optional
import logging
from pathlib import Path
from datetime import datetime, timezone
import os

from config import settings
from database import postgres, mongo_db
from models import *
from ldap_auth import ldap_manager
from auth import generate_access_token, get_current_user, require_admin
from file_operations import file_manager
from ldap3.core.exceptions import LDAPException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Secure Vault File Manager", version="1.0.0")

# API Router with /api prefix
api_router = APIRouter(prefix="/api")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.cors_origins.split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)


# Utility function to log audit trail
def log_audit(user_id: int, action: str, resource: str = None, details: str = None, ip: str = None):
    """Log audit trail to database"""
    try:
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO audit_logs (user_id, action, resource, details, ip_address)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, action, resource, details, ip))
    except Exception as e:
        logger.error(f"Failed to log audit: {e}")


# Get or create user in database
def get_or_create_user(username: str, display_name: str, email: str, ad_groups: List[str], is_admin: bool) -> int:
    """Get or create user in database, return user_id"""
    with postgres.get_cursor() as cursor:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        result = cursor.fetchone()
        
        if result:
            user_id = result['id']
            # Update user info
            cursor.execute("""
                UPDATE users 
                SET display_name = %s, email = %s, ad_groups = %s, is_admin = %s, last_login = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (display_name, email, ad_groups, is_admin, user_id))
        else:
            # Create new user
            cursor.execute("""
                INSERT INTO users (username, display_name, email, ad_groups, is_admin)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (username, display_name, email, ad_groups, is_admin))
            user_id = cursor.fetchone()['id']
        
        return user_id


# Authentication Endpoints
@api_router.post("/auth/login", response_model=TokenResponse, tags=["Authentication"])
async def login(credentials: UserCredentials, request: Request):
    """Authenticate user via LDAPS and return JWT token"""
    try:
        # Authenticate against Active Directory
        if not ldap_manager.authenticate_user(credentials.username, credentials.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Get user details from AD
        user_details = ldap_manager.get_user_details(credentials.username)
        if not user_details:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not retrieve user details"
            )
        
        # Get or create user in database
        user_id = get_or_create_user(
            username=user_details['username'],
            display_name=user_details.get('displayName'),
            email=user_details.get('email'),
            ad_groups=user_details.get('groups', []),
            is_admin=user_details.get('is_admin', False)
        )
        
        # Add user_id to user_details for token
        user_details['user_id'] = user_id
        
        # Generate JWT token
        token = generate_access_token(user_details)
        
        # Log audit
        log_audit(user_id, "LOGIN", ip=request.client.host)
        
        logger.info(f"Login successful: {credentials.username}")
        
        return TokenResponse(
            access_token=token,
            user=UserInfo(
                id=user_id,
                username=user_details['username'],
                display_name=user_details.get('displayName'),
                email=user_details.get('email'),
                ad_groups=user_details.get('groups', []),
                is_admin=user_details.get('is_admin', False)
            )
        )
    
    except LDAPException as e:
        logger.error(f"LDAP error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during login"
        )


@api_router.get("/auth/me", tags=["Authentication"])
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return {
        "username": current_user.get('username'),
        "email": current_user.get('email'),
        "is_admin": current_user.get('is_admin', False),
        "groups": current_user.get('groups', [])
    }


# File Management Endpoints
@api_router.get("/files", tags=["Files"])
async def list_files(path: str = "/", current_user: dict = Depends(get_current_user)):
    """List files and folders in directory"""
    try:
        user_id = current_user['user_id']
        files = await file_manager.list_directory(path, user_id)
        return {"files": files, "current_path": path}
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/files/folder", tags=["Files"])
async def create_folder(
    data: FileCreate,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Create a new folder"""
    try:
        user_id = current_user['user_id']
        folder_path = f"{data.parent_path.rstrip('/')}/{data.filename}"
        result = await file_manager.create_folder(folder_path, user_id)
        
        log_audit(user_id, "CREATE_FOLDER", folder_path, ip=request.client.host)
        
        return result
    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/files/upload", tags=["Files"])
async def upload_file(
    file: UploadFile = File(...),
    parent_path: str = "/",
    request: Request = None,
    current_user: dict = Depends(get_current_user)
):
    """Upload a file"""
    try:
        user_id = current_user['user_id']
        result = await file_manager.upload_file(file, parent_path, user_id)
        
        log_audit(user_id, "UPLOAD_FILE", result['file_path'], f"Size: {result['size']}", request.client.host)
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/files/download", tags=["Files"])
async def download_file(path: str, current_user: dict = Depends(get_current_user)):
    """Download a file"""
    try:
        abs_path = file_manager._get_absolute_path(path)
        
        if not abs_path.exists() or abs_path.is_dir():
            raise HTTPException(status_code=404, detail="File not found")
        
        log_audit(current_user['user_id'], "DOWNLOAD_FILE", path)
        
        return FileResponse(
            path=str(abs_path),
            filename=abs_path.name,
            media_type='application/octet-stream'
        )
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.put("/files/rename", tags=["Files"])
async def rename_file(
    data: FileOperation,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Rename a file or folder"""
    try:
        user_id = current_user['user_id']
        result = await file_manager.rename_file(data.source_path, data.new_name, user_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="File not found")
        
        log_audit(user_id, "RENAME", data.source_path, f"New name: {data.new_name}", request.client.host)
        
        return result
    except Exception as e:
        logger.error(f"Error renaming file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/files/delete", tags=["Files"])
async def delete_file(
    path: str,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Delete a file or folder"""
    try:
        user_id = current_user['user_id']
        await file_manager.delete_file(path, user_id)
        
        log_audit(user_id, "DELETE", path, ip=request.client.host)
        
        return {"success": True, "message": "File deleted"}
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.put("/files/move", tags=["Files"])
async def move_file(
    data: FileOperation,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Move file or folder"""
    try:
        user_id = current_user['user_id']
        result = await file_manager.move_file(data.source_path, data.destination_path, user_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="File not found")
        
        log_audit(user_id, "MOVE", data.source_path, f"To: {data.destination_path}", request.client.host)
        
        return result
    except Exception as e:
        logger.error(f"Error moving file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.put("/files/copy", tags=["Files"])
async def copy_file(
    data: FileOperation,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Copy file or folder"""
    try:
        user_id = current_user['user_id']
        result = await file_manager.copy_file(data.source_path, data.destination_path, user_id)
        
        log_audit(user_id, "COPY", data.source_path, f"To: {data.destination_path}", request.client.host)
        
        return result
    except Exception as e:
        logger.error(f"Error copying file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Sharing Endpoints
@api_router.post("/shares", tags=["Sharing"])
async def create_share(
    data: ShareCreate,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Share a file or folder with another user"""
    try:
        user_id = current_user['user_id']
        
        # Get file_id
        with postgres.get_cursor() as cursor:
            cursor.execute("SELECT id FROM files WHERE file_path = %s", (data.file_path,))
            file_result = cursor.fetchone()
            
            if not file_result:
                raise HTTPException(status_code=404, detail="File not found")
            
            file_id = file_result['id']
            
            # Get shared_with user_id
            cursor.execute("SELECT id FROM users WHERE username = %s", (data.shared_with_username,))
            user_result = cursor.fetchone()
            
            if not user_result:
                raise HTTPException(status_code=404, detail="User not found")
            
            shared_with_id = user_result['id']
            
            # Create share
            cursor.execute("""
                INSERT INTO shares (file_id, shared_by, shared_with, permission)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (file_id, user_id, shared_with_id, data.permission))
            
            share_id = cursor.fetchone()['id']
        
        log_audit(user_id, "SHARE", data.file_path, f"With: {data.shared_with_username}, Permission: {data.permission}", request.client.host)
        
        return {"id": share_id, "message": "File shared successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/shares/with-me", tags=["Sharing"])
async def get_shared_with_me(current_user: dict = Depends(get_current_user)):
    """Get files shared with current user"""
    try:
        user_id = current_user['user_id']
        
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                SELECT s.id, f.file_path, f.filename, f.is_folder, f.size, f.file_type,
                       u.username as shared_by, s.permission, s.created_at, f.modified_at
                FROM shares s
                JOIN files f ON s.file_id = f.id
                JOIN users u ON s.shared_by = u.id
                WHERE s.shared_with = %s
                ORDER BY s.created_at DESC
            """, (user_id,))
            results = cursor.fetchall()
        
        return {"shares": [dict(row) for row in results]}
    except Exception as e:
        logger.error(f"Error getting shared files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.delete("/shares/{share_id}", tags=["Sharing"])
async def delete_share(
    share_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Remove a share"""
    try:
        user_id = current_user['user_id']
        
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM shares 
                WHERE id = %s AND (shared_by = %s OR shared_with = %s)
            """, (share_id, user_id, user_id))
        
        log_audit(user_id, "UNSHARE", f"Share ID: {share_id}", ip=request.client.host)
        
        return {"success": True, "message": "Share removed"}
    except Exception as e:
        logger.error(f"Error deleting share: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Admin Endpoints
@api_router.get("/admin/users", tags=["Admin"])
async def get_all_users(current_user: dict = Depends(require_admin)):
    """Get all users (admin only)"""
    try:
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                SELECT id, username, display_name, email, is_admin, created_at, last_login
                FROM users
                ORDER BY last_login DESC NULLS LAST
            """)
            results = cursor.fetchall()
        
        return {"users": [dict(row) for row in results]}
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/admin/stats", tags=["Admin"])
async def get_storage_stats(current_user: dict = Depends(require_admin)):
    """Get storage statistics (admin only)"""
    try:
        with postgres.get_cursor() as cursor:
            # Total files and size
            cursor.execute("SELECT COUNT(*) as total_files, COALESCE(SUM(size), 0) as total_size FROM files")
            files_stats = cursor.fetchone()
            
            # User count
            cursor.execute("SELECT COUNT(*) as user_count FROM users")
            user_stats = cursor.fetchone()
            
            # Recent activity (last 24 hours)
            cursor.execute("SELECT COUNT(*) as recent_activity FROM audit_logs WHERE timestamp > NOW() - INTERVAL '24 hours'")
            activity_stats = cursor.fetchone()
        
        return StorageStats(
            total_files=files_stats['total_files'],
            total_size=files_stats['total_size'],
            user_count=user_stats['user_count'],
            recent_activity=activity_stats['recent_activity']
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/admin/audit-logs", tags=["Admin"])
async def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(require_admin)
):
    """Get audit logs (admin only)"""
    try:
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                SELECT a.id, u.username, a.action, a.resource, a.details, a.ip_address, a.timestamp
                FROM audit_logs a
                JOIN users u ON a.user_id = u.id
                ORDER BY a.timestamp DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            results = cursor.fetchall()
        
        return {"logs": [dict(row) for row in results]}
    except Exception as e:
        logger.error(f"Error getting audit logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Search Endpoint
@api_router.get("/search", tags=["Files"])
async def search_files(
    query: str,
    current_user: dict = Depends(get_current_user)
):
    """Search for files and folders"""
    try:
        user_id = current_user['user_id']
        
        with postgres.get_cursor() as cursor:
            cursor.execute("""
                SELECT f.*, u.username as owner_name
                FROM files f
                LEFT JOIN users u ON f.owner_id = u.id
                WHERE f.owner_id = %s AND f.filename ILIKE %s
                ORDER BY f.is_folder DESC, f.filename ASC
                LIMIT 50
            """, (user_id, f"%{query}%"))
            results = cursor.fetchall()
        
        return {"results": [dict(row) for row in results]}
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check
@api_router.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "Secure Vault File Manager"}


# Include API router
app.include_router(api_router)

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Secure Vault File Manager API", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
