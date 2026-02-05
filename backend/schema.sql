-- Secure Vault Database Schema
-- PostgreSQL 15+

-- ================================================================
-- USERS TABLE
-- ================================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255),
    email VARCHAR(255),
    ad_groups TEXT[] DEFAULT '{}',
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);

-- ================================================================
-- FILES TABLE
-- ================================================================
CREATE TABLE IF NOT EXISTS files (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename VARCHAR(500) NOT NULL,
    path TEXT NOT NULL,
    parent_path TEXT NOT NULL,
    is_folder BOOLEAN DEFAULT FALSE,
    size BIGINT DEFAULT 0,
    mime_type VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_files_owner ON files(owner_id);
CREATE INDEX idx_files_path ON files(path);
CREATE INDEX idx_files_parent_path ON files(parent_path);
CREATE UNIQUE INDEX idx_files_owner_path ON files(owner_id, path);

-- ================================================================
-- FILE_PERMISSIONS (ACL) TABLE
-- Application-layer permission enforcement
-- ================================================================
CREATE TABLE IF NOT EXISTS file_permissions (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    shared_by_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    shared_with_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    shared_with_group VARCHAR(255),
    permission_level VARCHAR(50) NOT NULL CHECK (permission_level IN ('read', 'write', 'full')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure either user OR group is specified, not both
    CONSTRAINT chk_share_target CHECK (
        (shared_with_user_id IS NOT NULL AND shared_with_group IS NULL) OR
        (shared_with_user_id IS NULL AND shared_with_group IS NOT NULL)
    )
);

CREATE INDEX idx_permissions_file ON file_permissions(file_id);
CREATE INDEX idx_permissions_user ON file_permissions(shared_with_user_id);
CREATE INDEX idx_permissions_group ON file_permissions(shared_with_group);
CREATE UNIQUE INDEX idx_permissions_unique_user ON file_permissions(file_id, shared_with_user_id) 
    WHERE shared_with_user_id IS NOT NULL;
CREATE UNIQUE INDEX idx_permissions_unique_group ON file_permissions(file_id, shared_with_group) 
    WHERE shared_with_group IS NOT NULL;

-- ================================================================
-- AUDIT_LOGS TABLE
-- ================================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource TEXT,
    ip_address INET,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp DESC);

-- ================================================================
-- HELPER FUNCTIONS
-- ================================================================

-- Function to get effective permissions for a user on a file
-- Returns highest permission level: full > write > read
CREATE OR REPLACE FUNCTION get_user_file_permission(
    p_user_id INTEGER,
    p_file_id INTEGER,
    p_user_groups TEXT[]
) RETURNS VARCHAR AS $$
DECLARE
    v_permission VARCHAR(50);
BEGIN
    -- Check if user is owner
    IF EXISTS (
        SELECT 1 FROM files 
        WHERE id = p_file_id AND owner_id = p_user_id
    ) THEN
        RETURN 'full';
    END IF;
    
    -- Check direct user permissions
    SELECT permission_level INTO v_permission
    FROM file_permissions
    WHERE file_id = p_file_id 
      AND shared_with_user_id = p_user_id
    ORDER BY 
        CASE permission_level
            WHEN 'full' THEN 3
            WHEN 'write' THEN 2
            WHEN 'read' THEN 1
        END DESC
    LIMIT 1;
    
    IF v_permission IS NOT NULL THEN
        RETURN v_permission;
    END IF;
    
    -- Check group permissions
    SELECT permission_level INTO v_permission
    FROM file_permissions
    WHERE file_id = p_file_id 
      AND shared_with_group = ANY(p_user_groups)
    ORDER BY 
        CASE permission_level
            WHEN 'full' THEN 3
            WHEN 'write' THEN 2
            WHEN 'read' THEN 1
        END DESC
    LIMIT 1;
    
    RETURN v_permission;
END;
$$ LANGUAGE plpgsql;
