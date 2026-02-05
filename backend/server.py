from fastapi import (
    FastAPI,
    APIRouter,
    Depends,
    HTTPException,
    Request,
    UploadFile,
    File,
    Query,
    Body,
)
from starlette.middleware.cors import CORSMiddleware
from typing import List
import logging
from pathlib import Path

from config import settings
from database import postgres
from models import *
from ldap_auth import ldap_manager
from auth import generate_access_token, get_current_user
from file_operations import FileManager
from permissions import permission_manager, PermissionLevel
from ldap3.core.exceptions import LDAPException

# -------------------------------------------------
# Logging
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# -------------------------------------------------
# App
# -------------------------------------------------
app = FastAPI(title="Secure Vault File Manager", version="1.0.0")
api_router = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# File Manager (INSTANCE HERE ✅)
# -------------------------------------------------
file_manager = FileManager()

# -------------------------------------------------
# Helpers
# -------------------------------------------------
def get_db_user_id(username: str) -> int:
    with postgres.get_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (username,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="User not found in database")
        return row["id"]


def log_audit(user_id: int, action: str, resource: str = None, ip: str = None):
    try:
        with postgres.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO audit_logs (user_id, action, resource, ip_address)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, action, resource, ip),
            )
    except Exception as e:
        logger.error(f"Audit log failed: {e}")


def get_or_create_user(
    username: str,
    display_name: str,
    email: str,
    ad_groups: List[str],
    is_admin: bool,
) -> int:
    ad_groups = ad_groups or []

    with postgres.get_cursor() as cursor:
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (username,),
        )
        row = cursor.fetchone()

        if row:
            user_id = row["id"]
            cursor.execute(
                """
                UPDATE users
                SET display_name = %s,
                    email = %s,
                    ad_groups = %s::text[],
                    is_admin = %s,
                    last_login = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (display_name, email, ad_groups, is_admin, user_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO users (username, display_name, email, ad_groups, is_admin)
                VALUES (%s, %s, %s, %s::text[], %s)
                RETURNING id
                """,
                (username, display_name, email, ad_groups, is_admin),
            )
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=500, detail="User creation failed")
            user_id = row["id"]

        return user_id


def ensure_user_storage(username: str):
    user_root = Path(settings.storage_root) / username
    user_root.mkdir(mode=0o750, parents=True, exist_ok=True)
    return user_root

# -------------------------------------------------
# Auth
# -------------------------------------------------
@api_router.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserCredentials, request: Request):
    try:
        if not ldap_manager.authenticate_user(
            credentials.username, credentials.password
        ):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_details = ldap_manager.get_user_details(credentials.username)
        if not user_details:
            raise HTTPException(status_code=401, detail="User not found")

        user_id = get_or_create_user(
            username=user_details["username"],
            display_name=user_details.get("displayName"),
            email=user_details.get("email"),
            ad_groups=user_details.get("groups", []),
            is_admin=user_details.get("is_admin", False),
        )

        ensure_user_storage(user_details["username"])

        token = generate_access_token(user_details)
        log_audit(user_id, "LOGIN", ip=request.client.host)

        return TokenResponse(
            access_token=token,
            user=UserInfo(
                id=user_id,
                username=user_details["username"],
                display_name=user_details.get("displayName"),
                email=user_details.get("email"),
                ad_groups=user_details.get("groups", []),
                is_admin=user_details.get("is_admin", False),
            ),
        )

    except LDAPException:
        raise HTTPException(status_code=503, detail="Directory unavailable")

# -------------------------------------------------
# File APIs (MATCHES new file_operations.py ✅)
# -------------------------------------------------
@api_router.get("/files")
async def list_files(
    path: str = Query("/", description="Directory path"),
    current_user: dict = Depends(get_current_user),
):
    username = current_user["username"]
    user_id = get_db_user_id(username)

    return await file_manager.list_directory(
        path=path,
        user_id=user_id,
        username=username,
    )



@api_router.post("/files/upload")
async def upload_file(
    parent_path: str = Query("/", description="Parent folder"),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_db_user_id(current_user["username"])
    result = await file_manager.upload_file(
        file=file,
        parent_path=parent_path,
        owner_id=user_id,
        username=current_user["username"],
    )
    log_audit(user_id, "UPLOAD", f"{parent_path}/{file.filename}")
    return result


@api_router.post("/files/folder")
async def create_folder(
    path: str = Query(..., description="Folder path"),
    current_user: dict = Depends(get_current_user),
):
    user_id = get_db_user_id(current_user["username"])
    result = await file_manager.create_folder(
        path=path,
        owner_id=user_id,
        username=current_user["username"],
    )
    log_audit(user_id, "CREATE_FOLDER", path)
    return result


@api_router.put("/files/rename")
async def rename_file(
    old_path: str,
    new_name: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = get_db_user_id(current_user["username"])
    result = await file_manager.rename_file(
        old_path=old_path,
        new_name=new_name,
        user_id=user_id,
        username=current_user["username"],
        user_groups=current_user.get("groups", []),
    )
    log_audit(user_id, "RENAME", old_path)
    return result


@api_router.delete("/files")
async def delete_file(
    path: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = get_db_user_id(current_user["username"])
    await file_manager.delete_file(
        path=path,
        user_id=user_id,
        username=current_user["username"],
        user_groups=current_user.get("groups", []),
    )
    log_audit(user_id, "DELETE", path)
    return {"status": "deleted"}


@api_router.put("/files/move")
async def move_file(
    source_path: str,
    dest_parent: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = get_db_user_id(current_user["username"])
    result = await file_manager.move_file(
        source_path=source_path,
        dest_parent=dest_parent,
        user_id=user_id,
        username=current_user["username"],
        user_groups=current_user.get("groups", []),
    )
    log_audit(user_id, "MOVE", source_path)
    return result


@api_router.put("/files/copy")
async def copy_file(
    source_path: str,
    dest_parent: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = get_db_user_id(current_user["username"])
    result = await file_manager.copy_file(
        source_path=source_path,
        dest_parent=dest_parent,
        user_id=user_id,
        username=current_user["username"],
        user_groups=current_user.get("groups", []),
    )
    log_audit(user_id, "COPY", source_path)
    return result

# -------------------------------------------------
# Sharing APIs
# -------------------------------------------------
@api_router.post("/shares")
async def share_file(
    file_path: str = Body(...),
    shared_with_username: str = Body(None),
    shared_with_group: str = Body(None),
    permission: str = Body("read"),
    current_user: dict = Depends(get_current_user),
):
    """Share a file with a user or AD group"""
    user_id = get_db_user_id(current_user["username"])
    
    # Get file ID
    file_id = permission_manager.get_file_id_by_path(file_path, user_id)
    if not file_id:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Create share
    permission_id = permission_manager.share_file(
        file_id=file_id,
        shared_by_user_id=user_id,
        shared_with_username=shared_with_username,
        shared_with_group=shared_with_group,
        permission_level=permission,
    )
    
    # Log audit
    target = shared_with_username or shared_with_group
    log_audit(user_id, "SHARE", f"{file_path} with {target} ({permission})")
    
    return {"id": permission_id, "status": "shared"}


@api_router.delete("/shares/{permission_id}")
async def unshare_file(
    permission_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Remove a file share"""
    user_id = get_db_user_id(current_user["username"])
    
    permission_manager.unshare_file(permission_id, user_id)
    
    log_audit(user_id, "UNSHARE", f"permission_id={permission_id}")
    
    return {"status": "unshared"}


@api_router.get("/shares/file")
async def get_file_shares(
    file_path: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """Get all shares for a specific file"""
    user_id = get_db_user_id(current_user["username"])
    
    # Get file ID
    file_id = permission_manager.get_file_id_by_path(file_path, user_id)
    if not file_id:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Check if user has permission to view shares (must be owner or have full permission)
    effective_perm = permission_manager.get_effective_permission(
        user_id, file_id, current_user.get("groups", [])
    )
    if effective_perm != PermissionLevel.FULL:
        raise HTTPException(status_code=403, detail="Only file owner can view shares")
    
    shares = permission_manager.get_file_shares(file_id)
    return {"shares": shares}


@api_router.get("/shares/with-me")
async def get_shared_with_me(
    current_user: dict = Depends(get_current_user),
):
    """Get all files shared with current user"""
    user_id = get_db_user_id(current_user["username"])
    
    shared_files = permission_manager.get_shared_with_me(
        user_id=user_id,
        user_groups=current_user.get("groups", [])
    )
    
    return {"shared_files": shared_files}

# -------------------------------------------------
# Final
# -------------------------------------------------
app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "Secure Vault File Manager API"}
