from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ──────────────────────────────
    # Application basics
    # ──────────────────────────────
    app_name: str = "Secure Vault File Manager"
    debug: bool = False

    # ──────────────────────────────
    # Database
    # ──────────────────────────────
    postgres_url: str = Field(..., description="PostgreSQL connection string")
    mongo_url: str = Field(..., description="MongoDB connection string")
    db_name: str = Field(..., description="MongoDB database name")

    # ──────────────────────────────
    # LDAPS / Active Directory
    # ──────────────────────────────
    ldaps_server: str = Field(..., description="Samba AD DC hostname (dc01.ryzen.local)")
    ldaps_port: int = Field(default=636, description="LDAPS port (636)")
    ldaps_base_dn: str = Field(..., description="LDAP base DN (DC=ryzen,DC=local)")

    ldap_bind_dn: str = Field(
        ..., description="Service account DN (CN=svc_securevault,CN=Users,DC=ryzen,DC=local)"
    )
    ldap_bind_password: str = Field(..., description="Service account password")

    ldaps_validate_cert: bool = Field(default=True, description="Validate LDAPS certificate")
    ldaps_ca_cert_path: str = Field(
        default="/usr/local/share/ca-certificates/ryzen-ad-ca.crt",
        description="Path to trusted Samba AD CA certificate",
    )

    # ──────────────────────────────
    # LDAP Search Configuration
    # ──────────────────────────────
    # IMPORTANT: Samba AD works best with simple sAMAccountName searches
    user_search_filter: str = "(sAMAccountName={username})"

    # Admin groups (matched by CN contains)
    admin_groups: List[str] = Field(
        default_factory=lambda: ["SECURE-VAULT-ADMINS", "Domain Admins"]
    )

    # ──────────────────────────────
    # Storage Configuration
    # ──────────────────────────────
    storage_root: str = Field(default="/data/secure-vault")
    max_file_size: int = Field(
        default=500 * 1024 * 1024, description="500MB in bytes"
    )

    # ──────────────────────────────
    # Security
    # ──────────────────────────────
    jwt_secret_key: str = Field(..., description="JWT secret key")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # ──────────────────────────────
    # CORS
    # ──────────────────────────────
    cors_origins: str = "*"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
