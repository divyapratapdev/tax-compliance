import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000/api"

async def test_backend():
    print("🚀 Starting Backend Integration Test Agent...")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Login
        print("\n🔑 1. Testing Login...")
        resp = await client.post(f"{BASE_URL}/auth/login", data={
            "username": "admin@taxpilot.com",
            "password": "password123"
        })
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Login successful")

        # 2. Profile
        print("\n👤 2. Testing Profile...")
        resp = await client.get(f"{BASE_URL}/profile", headers=headers)
        assert resp.status_code == 200, f"Profile failed: {resp.text}"
        profile = resp.json()
        print("✅ Profile OK:", profile.get("name"))

        # 3. Dashboard
        print("\n📊 3. Testing Dashboard...")
        resp = await client.get(f"{BASE_URL}/dashboard/summary", headers=headers)
        assert resp.status_code == 200, f"Dashboard failed: {resp.text}"
        dash = resp.json()
        print("✅ Dashboard OK. Total Clients:", dash["kpis"]["total_clients"])

        # 4. Clients
        print("\n🏢 4. Testing Clients...")
        resp = await client.get(f"{BASE_URL}/clients", headers=headers)
        assert resp.status_code == 200, f"Clients list failed: {resp.text}"
        clients = resp.json()["clients"]
        print(f"✅ Found {len(clients)} clients")

        if clients:
            c_id = clients[0]["id"]
            resp = await client.get(f"{BASE_URL}/clients/{c_id}", headers=headers)
            assert resp.status_code == 200, f"Client fetch failed: {resp.text}"
            print("✅ Client detail OK")

        # 5. Documents
        print("\n📄 5. Testing Documents...")
        resp = await client.get(f"{BASE_URL}/documents", headers=headers)
        assert resp.status_code == 200, f"Documents list failed: {resp.text}"
        docs = resp.json()["documents"]
        print(f"✅ Found {len(docs)} documents")

        # 6. GST
        print("\n🧾 6. Testing GST...")
        if clients:
            resp = await client.get(f"{BASE_URL}/gst/reconciliation/summary?client_id={c_id}", headers=headers)
            assert resp.status_code == 200, f"GST recon failed: {resp.text}"
            print("✅ GST Recon OK")
            
        resp = await client.get(f"{BASE_URL}/gst/mismatches", headers=headers)
        assert resp.status_code == 200, f"GST mismatches failed: {resp.text}"
        print(f"✅ Found {len(resp.json()['mismatches'])} GST mismatches")

        # 7. TDS
        print("\n💸 7. Testing TDS...")
        resp = await client.get(f"{BASE_URL}/tds/summary", headers=headers)
        assert resp.status_code == 200, f"TDS summary failed: {resp.text}"
        print("✅ TDS Summary OK")
        
        resp = await client.get(f"{BASE_URL}/tds/missed", headers=headers)
        assert resp.status_code == 200, f"TDS missed failed: {resp.text}"
        print(f"✅ Found {len(resp.json()['entries'])} missed TDS entries")

        # 8. Compliance
        print("\n📅 8. Testing Compliance...")
        resp = await client.get(f"{BASE_URL}/compliance/calendar", headers=headers)
        assert resp.status_code == 200, f"Compliance failed: {resp.text}"
        print(f"✅ Found {len(resp.json()['items'])} compliance items")
        
    print("\n🎉 ALL TESTS PASSED! BACKEND IS 100% HEALTHY.")

if __name__ == "__main__":
    asyncio.run(test_backend())
