# Secure Vault File Manager - Setup Instructions

## Overview
A production-ready file and folder management application with Active Directory authentication, built with React + FastAPI + PostgreSQL.

## Architecture

### Backend (FastAPI)
- **LDAPS Authentication**: Integrates with Microsoft Active Directory for user authentication
- **File Operations**: Create, upload, download, rename, delete, move, copy files and folders
- **Sharing & ACL**: Share files with other AD users with permission levels (Read, Read+Write, Full Control)
- **Admin Dashboard**: User management, storage stats, audit logs
- **Security**: CSRF protection, file validation, audit logging, session management

### Frontend (React)
- **Modern UI**: Clean, minimal design following Swiss enterprise aesthetic
- **File Explorer**: Grid/list views, drag-and-drop upload, breadcrumb navigation
- **Context Menu**: Right-click actions for file operations
- **Sharing Interface**: Share files with AD users
- **Admin Panel**: User management and system statistics

### Database
- **PostgreSQL**: User mappings, file metadata, shares/ACLs, audit logs
- **MongoDB**: Sessions and temporary data

## Configuration Required

### 1. Active Directory / LDAP Setup
Update `/app/backend/.env` with your AD server details:

```env
LDAPS_SERVER=your-ad-server.company.com
LDAPS_PORT=636
LDAPS_BASE_DN=DC=company,DC=com
LDAP_BIND_DN=CN=ServiceAccount,CN=Users,DC=company,DC=com
LDAP_BIND_PASSWORD=YourServiceAccountPassword
LDAPS_VALIDATE_CERT=True
LDAPS_CA_CERT_PATH=/path/to/ca-certificate.pem
```

### 2. Admin Groups
Configure AD groups that should have admin access in `.env`:
```env
# Users in these groups will get admin privileges
ADMIN_GROUPS=SECURE-VAULT-ADMINS,Domain Admins
```

### 3. Storage Configuration
The application stores files at:
```
/data/secure-vault
```

File size limit: **500MB per file** (configurable in `.env`)

### 4. Database Setup

**PostgreSQL** (recommended for production):
```bash
# Create database
createdb securevault

# Update .env
POSTGRES_URL=postgresql://user:password@localhost:5432/securevault
```

## Key Features Implemented

### Authentication & Authorization ✓
- [x] LDAPS authentication with Active Directory
- [x] JWT token-based sessions
- [x] Role-based access control (Admin/User)
- [x] AD group membership extraction
- [x] Session timeout and reauthentication

### File Management ✓
- [x] Create folders
- [x] Upload files (drag-and-drop)
- [x] Download files
- [x] Rename files/folders
- [x] Delete files/folders
- [x] Move files/folders
- [x] Copy files/folders
- [x] File metadata tracking
- [x] Search functionality

###Collaboration & Sharing ✓
- [x] Share files/folders with AD users
- [x] Permission levels (Read, Read+Write, Full Control)
- [x] "Shared with me" view
- [x] Share management

### Admin Features ✓
- [x] User list and management
- [x] Storage usage statistics
- [x] Audit log viewer
- [x] System health monitoring

### Security ✓
- [x] HTTPS ready
- [x] CSRF protection
- [x] File upload validation (size, type)
- [x] Directory traversal prevention
- [x] Audit logging for all operations
- [x] Secure credential management

### UI/UX ✓
- [x] Modern, responsive design
- [x] File explorer with grid/list views
- [x] Breadcrumb navigation
- [x] Right-click context menus
- [x] Drag-and-drop uploads
- [x] Real-time file operations
- [x] Toast notifications
- [x] Loading states and error handling

## Important Notes for Production

### LDAP Connection
The application requires a working LDAP/Active Directory connection. For testing without AD:
1. Use a mock LDAP server like [ldap-test-server](https://github.com/rroemhild/docker-test-openldap)
2. Or modify `ldap_auth.py` to use a local user database for testing

### Security Checklist
- [ ] Configure SSL/TLS certificates for LDAPS
- [ ] Set strong JWT_SECRET_KEY in production
- [ ] Enable LDAPS_VALIDATE_CERT in production
- [ ] Configure proper CORS_ORIGINS
- [ ] Set up firewall rules
- [ ] Regular security audits of audit logs
- [ ] Implement backup strategy for `/data/secure-vault`

### File System Permissions
Ensure the application has proper permissions:
```bash
sudo chown -R appuser:appuser /data/secure-vault
sudo chmod 755 /data/secure-vault
```

### Environment Variables
Never commit `.env` files to version control. Use secrets management in production.

## API Endpoints

### Authentication
- `POST /api/auth/login` - Authenticate with AD credentials
- `GET /api/auth/me` - Get current user info

### File Operations
- `GET /api/files?path=/` - List files in directory
- `POST /api/files/folder` - Create folder
- `POST /api/files/upload` - Upload file
- `GET /api/files/download?path=/file.txt` - Download file
- `PUT /api/files/rename` - Rename file/folder
- `DELETE /api/files/delete?path=/file.txt` - Delete file/folder
- `PUT /api/files/move` - Move file/folder
- `PUT /api/files/copy` - Copy file/folder

### Sharing
- `POST /api/shares` - Share file with user
- `GET /api/shares/with-me` - Get files shared with me
- `DELETE /api/shares/{id}` - Remove share

### Admin
- `GET /api/admin/users` - List all users (admin only)
- `GET /api/admin/stats` - Get storage statistics (admin only)
- `GET /api/admin/audit-logs` - View audit logs (admin only)

### Search
- `GET /api/search?query=filename` - Search files

## Testing

Once AD/LDAP is configured:

1. Login with AD credentials
2. Create folders
3. Upload files
4. Share with another AD user
5. Check admin dashboard (if admin user)
6. Review audit logs

## Next Steps

To deploy this application to production:

1. **Configure Active Directory connection** with proper credentials and certificates
2. **Set up PostgreSQL database** for production use
3. **Configure reverse proxy** (Nginx) with SSL/TLS
4. **Set up monitoring** and alerting
5. **Implement backup strategy** for file storage and database
6. **Configure email notifications** for file sharing events
7. **Set up log aggregation** for security monitoring

## Tech Stack

- **Frontend**: React 19, Tailwind CSS, Shadcn UI, Lucide Icons, React Router, Axios
- **Backend**: FastAPI, Python 3.11, ldap3, psycopg2, aiofiles
- **Database**: PostgreSQL (metadata), MongoDB (sessions)
- **Authentication**: LDAPS (Active Directory)
- **Storage**: Local filesystem (`/data/secure-vault`)

## File Structure

```
/app/
├── backend/
│   ├── server.py           # Main FastAPI application
│   ├── config.py           # Configuration management
│   ├── database.py         # Database connections
│   ├── models.py           # Pydantic models
│   ├── ldap_auth.py        # LDAP authentication
│   ├── auth.py             # JWT token management
│   ├── file_operations.py  # File system operations
│   └── .env                # Environment variables
└── frontend/
    ├── src/
    │   ├── pages/          # Page components
    │   ├── components/     # Reusable components
    │   ├── lib/            # Utilities and API client
    │   └── contexts/       # React contexts
    └── public/
```

## Support

For issues related to:
- **LDAP connection**: Check firewall, certificates, and service account permissions
- **File operations**: Verify filesystem permissions and storage path
- **Performance**: Monitor database queries and file operations in audit logs
