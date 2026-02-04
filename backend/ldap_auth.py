import ssl
import logging
from typing import Optional, List, Dict, Any
from ldap3 import Server, Connection, Tls, ALL
from ldap3.core.exceptions import LDAPException, LDAPBindError, LDAPSocketOpenError
from config import settings

logger = logging.getLogger(__name__)

class LDAPAuthManager:
    """Manages LDAPS authentication with Active Directory"""
    
    def __init__(self):
        self.server = self._initialize_server()
    
    def _initialize_server(self) -> Server:
        """Initialize LDAPS server configuration"""
        try:
            tls_config = Tls(
                validate=ssl.CERT_REQUIRED if settings.ldaps_validate_cert else ssl.CERT_NONE,
                version=ssl.PROTOCOL_TLS,
                ca_certs_file=settings.ldaps_ca_cert_path if settings.ldaps_validate_cert else None
            )
            
            server = Server(
                host=settings.ldaps_server,
                port=settings.ldaps_port,
                use_ssl=True,
                tls=tls_config,
                get_info=ALL,
                connect_timeout=10
            )
            
            logger.info(f"LDAPS server configured: {settings.ldaps_server}:{settings.ldaps_port}")
            return server
        except Exception as e:
            logger.error(f"Failed to configure LDAPS server: {e}")
            raise
    
    def _get_connection(self) -> Connection:
        """Establish connection to LDAPS server"""
        try:
            connection = Connection(
                server=self.server,
                user=settings.ldap_bind_dn,
                password=settings.ldap_bind_password,
                auto_bind=True,
                raise_exceptions=True
            )
            return connection
        except LDAPBindError as e:
            logger.error(f"LDAP bind failed: {e}")
            raise LDAPException(f"LDAP authentication failed: {e}")
        except LDAPSocketOpenError as e:
            logger.error(f"Cannot reach LDAPS server: {e}")
            raise LDAPException(f"Cannot connect to LDAPS server: {e}")
        except Exception as e:
            logger.error(f"LDAP connection error: {e}")
            raise LDAPException(f"LDAP connection error: {e}")
    
    def search_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Search for user in Active Directory"""
        conn = None
        try:
            conn = self._get_connection()
            search_filter = settings.user_search_filter.format(username=username)
            
            conn.search(
                search_base=settings.ldaps_base_dn,
                search_filter=search_filter,
                attributes=['sAMAccountName', 'displayName', 'mail', 'givenName', 'sn', 'distinguishedName', 'memberOf']
            )
            
            if conn.entries:
                user_entry = conn.entries[0]
                return {
                    'dn': user_entry.entry_dn,
                    'attributes': user_entry.entry_attributes_as_dict
                }
            return None
        except LDAPException:
            raise
        finally:
            if conn:
                conn.unbind()
    
    def authenticate_user(self, username: str, password: str) -> bool:
        """Authenticate user against Active Directory"""
        try:
            user_data = self.search_user_by_username(username)
            if not user_data:
                logger.warning(f"User not found: {username}")
                return False
            
            user_dn = user_data['dn']
            
            try:
                user_connection = Connection(
                    server=self.server,
                    user=user_dn,
                    password=password,
                    auto_bind=True,
                    raise_exceptions=True
                )
                user_connection.unbind()
                logger.info(f"User authenticated: {username}")
                return True
            except LDAPBindError:
                logger.warning(f"Invalid credentials for: {username}")
                return False
        except LDAPException:
            raise
    
    def get_user_groups(self, user_dn: str) -> List[Dict[str, str]]:
        """Retrieve all groups including nested memberships"""
        conn = None
        try:
            conn = self._get_connection()
            search_filter = settings.group_search_filter.format(user_dn=user_dn)
            
            conn.search(
                search_base=settings.ldaps_base_dn,
                search_filter=search_filter,
                attributes=['cn', 'distinguishedName', 'name']
            )
            
            groups = []
            for entry in conn.entries:
                group_info = {
                    'cn': entry.cn.value if hasattr(entry, 'cn') else None,
                    'distinguishedName': entry.entry_dn,
                    'name': entry.name.value if hasattr(entry, 'name') else None
                }
                groups.append(group_info)
            
            return groups
        except LDAPException:
            raise
        finally:
            if conn:
                conn.unbind()
    
    def get_user_details(self, username: str) -> Optional[Dict[str, Any]]:
        """Get complete user details including groups"""
        try:
            user_data = self.search_user_by_username(username)
            if not user_data:
                return None
            
            user_dn = user_data['dn']
            attributes = user_data['attributes']
            
            groups = self.get_user_groups(user_dn)
            group_names = [g['cn'] for g in groups if g['cn']]
            
            # Check if user is admin
            is_admin = any(admin_group in group_names for admin_group in settings.admin_groups)
            
            return {
                'username': username,
                'distinguishedName': user_dn,
                'displayName': attributes.get('displayName', [None])[0],
                'email': attributes.get('mail', [None])[0],
                'givenName': attributes.get('givenName', [None])[0],
                'surname': attributes.get('sn', [None])[0],
                'groups': group_names,
                'is_admin': is_admin
            }
        except LDAPException:
            raise

ldap_manager = LDAPAuthManager()
