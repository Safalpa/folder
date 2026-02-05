import ssl
import logging
from typing import Optional, Dict, Any
from ldap3 import Server, Connection, Tls, ALL
from ldap3.core.exceptions import LDAPException, LDAPBindError, LDAPSocketOpenError
from config import settings

logger = logging.getLogger(__name__)


class LDAPAuthManager:
    """Manages LDAPS authentication with Active Directory"""

    def __init__(self):
        self.server = self._initialize_server()

    # ──────────────────────────────
    # Server / TLS setup
    # ──────────────────────────────
    def _initialize_server(self) -> Server:
        try:
            tls_config = Tls(
                validate=ssl.CERT_REQUIRED if settings.ldaps_validate_cert else ssl.CERT_NONE,
                version=ssl.PROTOCOL_TLS,
                ca_certs_file=settings.ldaps_ca_cert_path if settings.ldaps_validate_cert else None,
            )

            server = Server(
                host=settings.ldaps_server,
                port=settings.ldaps_port,
                use_ssl=True,
                tls=tls_config,
                get_info=ALL,
                connect_timeout=10,
            )

            logger.info(
                f"LDAPS server configured: {settings.ldaps_server}:{settings.ldaps_port}"
            )
            return server

        except Exception as e:
            logger.error(f"Failed to configure LDAPS server: {e}")
            raise

    # ──────────────────────────────
    # Service bind (search)
    # ──────────────────────────────
    def _get_connection(self) -> Connection:
        try:
            return Connection(
                server=self.server,
                user=settings.ldap_bind_dn,
                password=settings.ldap_bind_password,
                auto_bind=True,
                raise_exceptions=True,
            )
        except LDAPBindError as e:
            raise LDAPException(f"LDAP service bind failed: {e}")
        except LDAPSocketOpenError as e:
            raise LDAPException(f"Cannot connect to LDAPS server: {e}")
        except Exception as e:
            raise LDAPException(f"LDAP connection error: {e}")

    # ──────────────────────────────
    # User search
    # ──────────────────────────────
    def search_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        conn = None
        try:
            conn = self._get_connection()
            search_filter = settings.user_search_filter.format(username=username)

            conn.search(
                search_base=settings.ldaps_base_dn,
                search_filter=search_filter,
                attributes=[
                    "sAMAccountName",
                    "displayName",
                    "mail",
                    "givenName",
                    "sn",
                    "distinguishedName",
                    "memberOf",
                ],
            )

            if not conn.entries:
                return None

            entry = conn.entries[0]

            return {
                "dn": entry.entry_dn,
                "attributes": entry.entry_attributes_as_dict,
            }

        finally:
            if conn:
                conn.unbind()

    # ──────────────────────────────
    # Password verification
    # ──────────────────────────────
    def authenticate_user(self, username: str, password: str) -> bool:
        user_data = self.search_user_by_username(username)
        if not user_data:
            logger.warning(f"User not found: {username}")
            return False

        user_dn = user_data["dn"]

        try:
            user_conn = Connection(
                server=self.server,
                user=user_dn,
                password=password,
                auto_bind=True,
                raise_exceptions=True,
            )
            user_conn.unbind()
            logger.info(f"User authenticated: {username}")
            return True

        except LDAPBindError:
            logger.warning(f"Invalid credentials for: {username}")
            return False

    # ──────────────────────────────
    # Helper: safe attribute extraction
    # ──────────────────────────────
    @staticmethod
    def _safe_attr(attrs: Dict[str, Any], key: str):
        value = attrs.get(key)
        if isinstance(value, list) and value:
            return value[0]
        return None

    # ──────────────────────────────
    # Full user details (FIXED & SAFE)
    # ──────────────────────────────
    def get_user_details(self, username: str) -> Optional[Dict[str, Any]]:
        user_data = self.search_user_by_username(username)
        if not user_data:
            return None

        user_dn = user_data["dn"]
        attrs = user_data["attributes"]

        # Extract memberOf safely
        member_of = attrs.get("memberOf", [])
        if isinstance(member_of, str):
            member_of = [member_of]

        group_names = [
            g.split(",")[0].replace("CN=", "") for g in member_of
        ]

        is_admin = any(
            admin_group in group_names
            for admin_group in settings.admin_groups
        )

        return {
            "username": username,
            "distinguishedName": user_dn,
            "displayName": self._safe_attr(attrs, "displayName"),
            "email": self._safe_attr(attrs, "mail"),
            "givenName": self._safe_attr(attrs, "givenName"),
            "surname": self._safe_attr(attrs, "sn"),
            "groups": group_names,
            "is_admin": is_admin,
        }


ldap_manager = LDAPAuthManager()
