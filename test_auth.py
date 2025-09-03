#!/usr/bin/env python3
"""
Test script for JWT authentication
Run this after starting the server to test the authentication flow
"""

import requests
import json

# Configuration
BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin123"

def test_login():
    """Test the login endpoint"""
    print("🔐 Testing login endpoint...")
    
    login_data = {
        "username": USERNAME,
        "password": PASSWORD
    }
    
    try:
        response = requests.post(f"{BASE_URL}/login", json=login_data)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            token_data = response.json()
            print("✅ Login successful!")
            print(f"Token: {token_data['access_token'][:50]}...")
            print(f"Token Type: {token_data['token_type']}")
            print(f"Expires In: {token_data['expires_in']} seconds")
            return token_data['access_token']
        else:
            print(f"❌ Login failed: {response.text}")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Make sure the server is running on localhost:8000")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def test_protected_endpoint(token):
    """Test a protected endpoint with the JWT token"""
    print("\n🔒 Testing protected endpoint...")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    try:
        response = requests.get(f"{BASE_URL}/health", headers=headers)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Protected endpoint accessible!")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"❌ Protected endpoint failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def test_unprotected_endpoint():
    """Test accessing a protected endpoint without authentication"""
    print("\n🚫 Testing unprotected access...")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 401:
            print("✅ Authentication properly required!")
        else:
            print(f"❌ Expected 401, got {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("🧪 JWT Authentication Test Suite")
    print("=" * 40)
    
    # Test login
    token = test_login()
    
    if token:
        # Test protected endpoint with token
        test_protected_endpoint(token)
        
        # Test protected endpoint without token
        test_unprotected_endpoint()
        
        print("\n✅ All tests completed!")
    else:
        print("\n❌ Cannot proceed without valid token")

if __name__ == "__main__":
    main()
