import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application basics
    app_name: str = "Secure Vault File Manager"
    debug: bool = False
    
    # Database
    postgres_url: str = Field(..., description="PostgreSQL connection string")
    mongo_url: str = Field(..., description="MongoDB connection string")
    db_name: str = Field(..., description="MongoDB database name")
    
    # LDAPS Connection Settings
    ldaps_server: str = Field(..., description="LDAPS server hostname or IP")
    ldaps_port: int = Field(default=636, description="LDAPS port")
    ldaps_base_dn: str = Field(..., description="LDAP base DN for searches")
    ldap_bind_dn: str = Field(..., description="Service account DN")
    ldap_bind_password: str = Field(..., description="Service account password")
    ldaps_validate_cert: bool = Field(default=False, description="Validate certificate")
    ldaps_ca_cert_path: Optional[str] = Field(default=None)
    
    # LDAP Search Parameters
    user_search_filter: str = "(&(objectClass=person)(sAMAccountName={username}))"
    group_search_filter: str = "(member:1.2.840.113556.1.4.1941:={user_dn})"
    admin_groups: list = Field(default=["SECURE-VAULT-ADMINS", "Domain Admins"])
    
    # Storage Configuration
    storage_root: str = Field(default="/data/secure-vault")
    max_file_size: int = Field(default=500 * 1024 * 1024, description="500MB in bytes")
    
    # Security
    jwt_secret_key: str = Field(..., description="JWT secret key")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS
    cors_origins: str = "*"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
