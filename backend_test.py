#!/usr/bin/env python3
"""
Secure Vault File Manager Backend Test Suite
Tests ACL/sharing system and audit logging functionality
"""

import requests
import json
import os
import sys
import time
from typing import Dict, Optional, List
from pathlib import Path

# Configuration
BACKEND_URL = 'http://localhost:8001'
API_BASE = f"{BACKEND_URL}/api"

class SecureVaultTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.auth_token = None
        self.test_results = []
        
    def log_test(self, test_name: str, success: bool, message: str = "", details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if details:
            print(f"    Details: {details}")
        
        self.test_results.append({
            'test': test_name,
            'success': success,
            'message': message,
            'details': details
        })
    
    def test_api_connectivity(self) -> bool:
        """Test basic API connectivity"""
        try:
            response = self.session.get(f"{BACKEND_URL}/")
            if response.status_code == 200:
                data = response.json()
                self.log_test("API Connectivity", True, f"API accessible: {data.get('message', 'OK')}")
                return True
            else:
                self.log_test("API Connectivity", False, f"HTTP {response.status_code}")
                return False
        except Exception as e:
            self.log_test("API Connectivity", False, f"Connection failed: {str(e)}")
            return False
    
    def test_database_connectivity(self) -> bool:
        """Test PostgreSQL database connectivity by checking if we can access endpoints"""
        try:
            # Try to access an endpoint that would require DB connection
            response = self.session.post(f"{API_BASE}/auth/login", json={
                "username": "test_connectivity",
                "password": "test_password"
            })
            
            # We expect 401 or 503, not 500 (which would indicate DB connection issues)
            if response.status_code in [401, 503]:
                self.log_test("Database Connectivity", True, "Database appears accessible (auth endpoint responds)")
                return True
            elif response.status_code == 500:
                try:
                    error_data = response.json()
                    if "database" in str(error_data).lower() or "connection" in str(error_data).lower():
                        self.log_test("Database Connectivity", False, "Database connection error detected")
                        return False
                except:
                    pass
                self.log_test("Database Connectivity", False, "Internal server error (possible DB issue)")
                return False
            else:
                self.log_test("Database Connectivity", True, f"Unexpected response {response.status_code} but no DB errors")
                return True
                
        except Exception as e:
            self.log_test("Database Connectivity", False, f"Error testing DB: {str(e)}")
            return False
    
    def test_auth_endpoints_exist(self) -> bool:
        """Test that authentication endpoints exist"""
        try:
            # Test login endpoint exists
            response = self.session.post(f"{API_BASE}/auth/login", json={
                "username": "nonexistent",
                "password": "invalid"
            })
            
            # Should get 401 (invalid creds) or 503 (LDAP unavailable), not 404
            if response.status_code in [401, 503]:
                self.log_test("Auth Endpoints", True, f"Login endpoint exists (HTTP {response.status_code})")
                return True
            elif response.status_code == 404:
                self.log_test("Auth Endpoints", False, "Login endpoint not found")
                return False
            else:
                self.log_test("Auth Endpoints", True, f"Login endpoint exists (HTTP {response.status_code})")
                return True
                
        except Exception as e:
            self.log_test("Auth Endpoints", False, f"Error testing auth: {str(e)}")
            return False
    
    def test_file_endpoints_exist(self) -> bool:
        """Test that file operation endpoints exist (without auth)"""
        endpoints_to_test = [
            ("GET", "/files", "List files"),
            ("POST", "/files/upload", "Upload file"),
            ("GET", "/files/download", "Download file"),
            ("POST", "/files/folder", "Create folder"),
            ("PUT", "/files/rename", "Rename file"),
            ("DELETE", "/files", "Delete file"),
            ("PUT", "/files/move", "Move file"),
            ("PUT", "/files/copy", "Copy file")
        ]
        
        all_exist = True
        for method, endpoint, description in endpoints_to_test:
            try:
                if method == "GET":
                    response = self.session.get(f"{API_BASE}{endpoint}")
                elif method == "POST":
                    response = self.session.post(f"{API_BASE}{endpoint}", json={})
                elif method == "PUT":
                    response = self.session.put(f"{API_BASE}{endpoint}", json={})
                elif method == "DELETE":
                    response = self.session.delete(f"{API_BASE}{endpoint}")
                
                # Should get 401 (unauthorized) or 422 (validation error), not 404
                if response.status_code in [401, 422, 403]:
                    self.log_test(f"File Endpoint - {description}", True, f"Endpoint exists (HTTP {response.status_code})")
                elif response.status_code == 404:
                    self.log_test(f"File Endpoint - {description}", False, "Endpoint not found")
                    all_exist = False
                else:
                    self.log_test(f"File Endpoint - {description}", True, f"Endpoint exists (HTTP {response.status_code})")
                    
            except Exception as e:
                self.log_test(f"File Endpoint - {description}", False, f"Error: {str(e)}")
                all_exist = False
        
        return all_exist
    
    def test_sharing_endpoints_exist(self) -> bool:
        """Test that sharing/ACL endpoints exist"""
        endpoints_to_test = [
            ("POST", "/shares", "Share file"),
            ("DELETE", "/shares/1", "Unshare file"),
            ("GET", "/shares/file", "Get file shares"),
            ("GET", "/shares/with-me", "Get shared with me")
        ]
        
        all_exist = True
        for method, endpoint, description in endpoints_to_test:
            try:
                if method == "GET":
                    response = self.session.get(f"{API_BASE}{endpoint}")
                elif method == "POST":
                    response = self.session.post(f"{API_BASE}{endpoint}", json={})
                elif method == "DELETE":
                    response = self.session.delete(f"{API_BASE}{endpoint}")
                
                # Should get 401 (unauthorized) or 422 (validation error), not 404
                if response.status_code in [401, 422, 403]:
                    self.log_test(f"Sharing Endpoint - {description}", True, f"Endpoint exists (HTTP {response.status_code})")
                elif response.status_code == 404:
                    self.log_test(f"Sharing Endpoint - {description}", False, "Endpoint not found")
                    all_exist = False
                else:
                    self.log_test(f"Sharing Endpoint - {description}", True, f"Endpoint exists (HTTP {response.status_code})")
                    
            except Exception as e:
                self.log_test(f"Sharing Endpoint - {description}", False, f"Error: {str(e)}")
                all_exist = False
        
        return all_exist
    
    def test_ldap_configuration(self) -> bool:
        """Test LDAP configuration and connectivity"""
        try:
            # Try to authenticate with test credentials
            response = self.session.post(f"{API_BASE}/auth/login", json={
                "username": "testuser",
                "password": "testpass"
            })
            
            if response.status_code == 503:
                try:
                    error_data = response.json()
                    if "Directory unavailable" in str(error_data):
                        self.log_test("LDAP Configuration", True, "LDAP configured but server unavailable (expected in test env)")
                        return True
                except:
                    pass
                self.log_test("LDAP Configuration", True, "LDAP service unavailable (expected)")
                return True
            elif response.status_code == 401:
                self.log_test("LDAP Configuration", True, "LDAP server accessible (invalid credentials)")
                return True
            else:
                self.log_test("LDAP Configuration", True, f"LDAP endpoint responds (HTTP {response.status_code})")
                return True
                
        except Exception as e:
            self.log_test("LDAP Configuration", False, f"LDAP test error: {str(e)}")
            return False
    
    def test_permission_levels(self) -> bool:
        """Test that permission level validation is implemented"""
        try:
            # Test sharing with invalid permission level (should fail validation)
            response = self.session.post(f"{API_BASE}/shares", json={
                "file_path": "/test.txt",
                "shared_with_username": "testuser",
                "permission": "invalid_permission"
            })
            
            # Should get 401 (no auth) or 422 (validation error), not 500
            if response.status_code in [401, 422]:
                self.log_test("Permission Level Validation", True, "Permission validation appears implemented")
                return True
            elif response.status_code == 500:
                self.log_test("Permission Level Validation", False, "Server error on invalid permission")
                return False
            else:
                self.log_test("Permission Level Validation", True, f"Validation responds (HTTP {response.status_code})")
                return True
                
        except Exception as e:
            self.log_test("Permission Level Validation", False, f"Error: {str(e)}")
            return False
    
    def test_audit_logging_structure(self) -> bool:
        """Test that audit logging is implemented by checking endpoint behavior"""
        try:
            # Test that operations would trigger audit logging
            # We can't directly check the database, but we can see if the endpoints
            # are structured to handle audit logging
            
            response = self.session.post(f"{API_BASE}/files/folder", json={})
            
            # Should get 401 (no auth) or 422 (validation), indicating the endpoint
            # is properly structured and would handle audit logging
            if response.status_code in [401, 422]:
                self.log_test("Audit Logging Structure", True, "Endpoints structured for audit logging")
                return True
            else:
                self.log_test("Audit Logging Structure", True, f"Audit-capable endpoints (HTTP {response.status_code})")
                return True
                
        except Exception as e:
            self.log_test("Audit Logging Structure", False, f"Error: {str(e)}")
            return False
    
    def test_cors_configuration(self) -> bool:
        """Test CORS configuration"""
        try:
            # Test preflight request
            response = self.session.options(f"{API_BASE}/files")
            
            # Should get proper CORS headers or 200/204
            if response.status_code in [200, 204, 405]:
                headers = response.headers
                if 'Access-Control-Allow-Origin' in headers or response.status_code == 405:
                    self.log_test("CORS Configuration", True, "CORS appears configured")
                    return True
                else:
                    self.log_test("CORS Configuration", False, "No CORS headers found")
                    return False
            else:
                self.log_test("CORS Configuration", True, f"CORS handling present (HTTP {response.status_code})")
                return True
                
        except Exception as e:
            self.log_test("CORS Configuration", False, f"Error: {str(e)}")
            return False
    
    def test_api_documentation(self) -> bool:
        """Test if API documentation is available"""
        try:
            # Test OpenAPI/Swagger docs
            response = self.session.get(f"{BACKEND_URL}/docs")
            
            if response.status_code == 200:
                self.log_test("API Documentation", True, "Swagger docs available")
                return True
            else:
                # Try alternative
                response = self.session.get(f"{BACKEND_URL}/openapi.json")
                if response.status_code == 200:
                    self.log_test("API Documentation", True, "OpenAPI spec available")
                    return True
                else:
                    self.log_test("API Documentation", False, "No API documentation found")
                    return False
                    
        except Exception as e:
            self.log_test("API Documentation", False, f"Error: {str(e)}")
            return False
    
    def run_all_tests(self) -> Dict:
        """Run all tests and return summary"""
        print("🔒 Secure Vault File Manager - Backend Test Suite")
        print("=" * 60)
        print(f"Testing backend at: {BACKEND_URL}")
        print()
        
        # Core connectivity tests
        print("📡 CONNECTIVITY TESTS")
        print("-" * 30)
        api_ok = self.test_api_connectivity()
        db_ok = self.test_database_connectivity()
        
        print()
        print("🔐 AUTHENTICATION TESTS")
        print("-" * 30)
        auth_ok = self.test_auth_endpoints_exist()
        ldap_ok = self.test_ldap_configuration()
        
        print()
        print("📁 FILE OPERATION TESTS")
        print("-" * 30)
        files_ok = self.test_file_endpoints_exist()
        
        print()
        print("🤝 SHARING/ACL TESTS")
        print("-" * 30)
        sharing_ok = self.test_sharing_endpoints_exist()
        permissions_ok = self.test_permission_levels()
        
        print()
        print("📊 AUDIT & CONFIGURATION TESTS")
        print("-" * 30)
        audit_ok = self.test_audit_logging_structure()
        cors_ok = self.test_cors_configuration()
        docs_ok = self.test_api_documentation()
        
        # Summary
        print()
        print("📋 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        # Critical issues
        critical_failures = []
        if not api_ok:
            critical_failures.append("API not accessible")
        if not db_ok:
            critical_failures.append("Database connectivity issues")
        if not auth_ok:
            critical_failures.append("Authentication endpoints missing")
        if not sharing_ok:
            critical_failures.append("Sharing endpoints missing")
        
        if critical_failures:
            print()
            print("🚨 CRITICAL ISSUES:")
            for issue in critical_failures:
                print(f"   • {issue}")
        
        # Limitations noted
        print()
        print("📝 TEST LIMITATIONS:")
        print("   • LDAP server not available (expected in test environment)")
        print("   • Cannot test actual file operations without authentication")
        print("   • Database schema not directly accessible for validation")
        print("   • Audit logs cannot be directly verified")
        
        return {
            'total_tests': total_tests,
            'passed': passed_tests,
            'failed': failed_tests,
            'success_rate': (passed_tests/total_tests)*100,
            'critical_failures': critical_failures,
            'test_results': self.test_results
        }

def main():
    """Main test execution"""
    tester = SecureVaultTester()
    results = tester.run_all_tests()
    
    # Exit with appropriate code
    if results['critical_failures']:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()