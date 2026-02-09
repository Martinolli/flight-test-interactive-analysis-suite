#!/usr/bin/env python3.11
"""
Test CSV upload functionality
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def main():
    print("\n🚀 Testing CSV Upload\n")
    print("=" * 60)
    
    # Step 1: Login
    print("Step 1: Login...")
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "testuser", "password": "testpass123"}
    )
    
    if response.status_code != 200:
        print(f"❌ Login failed: {response.status_code}")
        return
    
    token = response.json()["access_token"]
    print(f"✅ Token obtained: {token[:50]}...")
    
    # Step 2: Upload CSV
    print("\nStep 2: Upload CSV file...")
    headers = {"Authorization": f"Bearer {token}"}
    
    with open("/home/ubuntu/ftias-project/Flight_Test_Data_2025_08_06.csv", "rb") as f:
        files = {"file": ("Flight_Test_Data_2025_08_06.csv", f, "text/csv")}
        response = requests.post(
            f"{BASE_URL}/api/flight-tests/1/upload-csv",
            headers=headers,
            files=files
        )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ CSV uploaded successfully!")
        print(f"   Rows processed: {result.get('rows_processed', 'N/A')}")
        print(f"   Data points created: {result.get('data_points_created', 'N/A')}")
    else:
        print(f"❌ Upload failed")
        try:
            print(f"   Error: {response.json()}")
        except:
            print(f"   Response: {response.text}")
    
    # Step 3: Get data points
    print("\nStep 3: Retrieve data points...")
    response = requests.get(
        f"{BASE_URL}/api/flight-tests/1/data?limit=5",
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        data_points = response.json()
        print(f"✅ Retrieved {len(data_points)} data points (showing first 5)")
        for i, dp in enumerate(data_points[:3], 1):
            print(f"   {i}. Timestamp: {dp['timestamp']}, Value: {dp['value']}")
    else:
        print(f"❌ Failed to retrieve data points")
        try:
            print(f"   Error: {response.json()}")
        except:
            print(f"   Response: {response.text}")
    
    print("\n" + "=" * 60)
    print("✅ CSV Upload Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
