# Secure Vault ACL / Permission System

## Overview
Application-layer Access Control List (ACL) system enforcing permissions at the database/API level, independent of Linux filesystem permissions.

## Permission Levels

### 1. READ
- View file/folder metadata
- Download files
- Copy files (creates new copy owned by copier)

### 2. WRITE
- All READ permissions, plus:
- Rename files/folders
- Move files/folders
- Upload new files to shared folders

### 3. FULL
- All WRITE permissions, plus:
- Delete files/folders
- Share with other users/groups
- Modify permissions

## Permission Enforcement

### Owner Permissions
- File/folder owners automatically have FULL permission
- Cannot be revoked or modified

### Shared Permissions
Permissions can be granted to:
- **Individual AD Users**: By username
- **AD Groups**: By group name (all group members inherit permission)

### Priority
When a user has multiple permission paths (direct + group), the highest permission level applies.

## File Operations & Required Permissions

| Operation | Required Permission | Notes |
|-----------|-------------------|-------|
| List files | READ (or ownership) | Shows owned + shared files |
| Download | READ | Enforced on each file |
| Copy | READ | Creates new file owned by copier |
| Upload | WRITE on parent folder | - |
| Rename | WRITE | - |
| Move | WRITE | - |
| Delete | FULL | - |
| Share | FULL | Can share with read/write/full |
| Unshare | FULL (or share creator) | - |

## Folder Permission Behavior (v1)

### NO INHERITANCE IN v1
- Permissions are granted per file/folder individually
- Sharing a folder does NOT automatically share its contents
- Each file/folder requires explicit permission grant

### Example:
```
User A shares /Projects/Design with User B (READ)
→ User B can see /Projects/Design folder
→ User B CANNOT see files inside unless explicitly shared
```

### Rationale:
- Simpler initial implementation
- Clearer permission model
- No cascading permission updates
- Easier audit trail

### Future Enhancement (v2+):
- Optional recursive permission grants
- Folder permission inheritance for new files
- Bulk permission management

## Shared File Visibility

### Discovery
- Shared files appear in:
  1. Regular file listings (GET /api/files?path=/) alongside owned files
  2. "Shared with me" endpoint (GET /api/shares/with-me)

### Path Resolution
- Shared files are accessed via their original paths
- Physical files remain in owner's storage: `/data/secure-vault/{owner}/...`
- Users with READ+ permission can access via API using the original path

### Example:
```
Owner: alice
File: /data/secure-vault/alice/reports/Q4.pdf
Path in DB: /reports/Q4.pdf

Bob (shared with READ) can:
- See file in: GET /api/files?path=/reports
- Download via: GET /api/files/download?path=/reports/Q4.pdf

System resolves to alice's storage automatically.
```

## AD Group Integration

### Group Resolution
- User's AD groups extracted during JWT token creation
- Groups stored in JWT token payload
- Passed to all permission checks

### Group Sharing
```
Share /ProjectX with group "Engineering" (WRITE)
→ All users in "Engineering" AD group get WRITE permission
→ Group membership changes don't require re-sharing
→ Evaluated at request time via JWT groups
```

## Audit Logging

All permission-related operations are logged:

| Action | Details Logged |
|--------|---------------|
| SHARE | Actor, file path, target (user/group), permission level |
| UNSHARE | Actor, file path, target removed |
| PERMISSION_DENIED | Actor, file path, attempted operation |

Audit logs stored in `audit_logs` table with:
- user_id
- action
- resource (file path)
- ip_address
- details (JSON with specifics)
- timestamp

## Database Schema

### file_permissions table
```sql
CREATE TABLE file_permissions (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES files(id) ON DELETE CASCADE,
    shared_by_user_id INTEGER REFERENCES users(id),
    shared_with_user_id INTEGER REFERENCES users(id),
    shared_with_group VARCHAR(255),
    permission_level VARCHAR(50), -- 'read', 'write', 'full'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT chk_share_target CHECK (
        (shared_with_user_id IS NOT NULL AND shared_with_group IS NULL) OR
        (shared_with_user_id IS NULL AND shared_with_group IS NOT NULL)
    )
);
```

### Indexes
- `idx_permissions_file` - Fast lookup by file
- `idx_permissions_user` - Fast lookup by shared_with_user
- `idx_permissions_group` - Fast lookup by shared_with_group
- Unique constraints prevent duplicate shares

## Security Considerations

### What ACL DOES:
- ✓ Enforces who can read/write/delete at API level
- ✓ Prevents unauthorized API access to files
- ✓ Logs all permission changes
- ✓ Supports enterprise AD integration

### What ACL DOES NOT:
- ✗ Does NOT enforce Linux filesystem permissions
- ✗ Does NOT prevent direct disk access (requires OS-level security)
- ✗ Does NOT encrypt files at rest (separate feature)

### Production Recommendations:
1. Run backend with restricted service account
2. Set `/data/secure-vault` with strict OS permissions (700)
3. Regular audit log reviews
4. Consider filesystem encryption (LUKS/dm-crypt)
5. Database connection over SSL
6. Rate limiting on share endpoints

## API Reference

### Share File
```
POST /api/shares
{
  "file_path": "/documents/report.pdf",
  "shared_with_username": "bob",  // OR
  "shared_with_group": "Managers",
  "permission": "read"  // read | write | full
}
```

### Unshare File
```
DELETE /api/shares/{permission_id}
```

### List File Shares
```
GET /api/shares/file?file_path=/documents/report.pdf
```

### Get Shared With Me
```
GET /api/shares/with-me
```

## Implementation Notes

### PermissionManager (`permissions.py`)
- Centralized permission checking logic
- Methods: `check_permission()`, `share_file()`, `unshare_file()`
- Called by all file operations

### FileManager (`file_operations.py`)
- File operations first check permissions via PermissionManager
- Operations use owner's filesystem path for shared files
- DB updates use file_id (not owner_id filter) after permission check

### Server Endpoints (`server.py`)
- All endpoints pass `user_groups` from JWT to operations
- Enhanced audit logging on all share operations
- No direct SQL for permission checks (uses PermissionManager)

## Testing Checklist

- [ ] Share file with user (read/write/full)
- [ ] Share folder with AD group
- [ ] Shared file appears in recipient's listing
- [ ] Permission enforcement (read vs write vs full)
- [ ] Group member can access group-shared file
- [ ] Owner can always perform all operations
- [ ] Non-owner with FULL can delete
- [ ] Non-owner with WRITE can rename but not delete
- [ ] Non-owner with READ can download but not modify
- [ ] Audit logs contain all share operations
- [ ] Unshare removes access
- [ ] Multiple permission sources (highest wins)
