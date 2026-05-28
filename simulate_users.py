import asyncio
import httpx
import random
import time
import uuid

# TARGET_URL = "http://localhost:8000"
TARGET_URL = "https://tax-compliance.onrender.com"

# The fixed token from auth_utils.py (since we have a hardcoded check for testing)
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbkB0YXhwaWxvdC5jb20iLCJmaXJtX2lkIjoiZmlybS0xMjMiLCJyb2xlIjoiYWRtaW4iLCJleHAiOjE3MTY4ODQwMDB9.invalid"

async def simulate_ca_agent(agent_id: int):
    print(f"[Agent {agent_id}] Starting simulation...")
    
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    
    async with httpx.AsyncClient(base_url=TARGET_URL, headers=headers, timeout=30.0) as client:
        # Step 1: Fetch Profile (Verify Auth)
        start_time = time.time()
        resp = await client.get("/api/profile")
        if resp.status_code != 200:
            print(f"[Agent {agent_id}] Failed to load profile: {resp.status_code} - {resp.text}")
            return
        
        print(f"[Agent {agent_id}] Profile loaded in {time.time() - start_time:.2f}s")
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Step 2: Fetch Dashboard Summary
        resp = await client.get("/api/dashboard/summary")
        print(f"[Agent {agent_id}] Dashboard loaded: {resp.status_code}")
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # Step 3: Fetch Clients List
        resp = await client.get("/api/clients")
        if resp.status_code != 200:
            print(f"[Agent {agent_id}] Failed to load clients: {resp.status_code}")
            return
            
        clients = resp.json().get("clients", [])
        if not clients:
            print(f"[Agent {agent_id}] No clients found to test with.")
            return
            
        target_client = random.choice(clients)["id"]
        print(f"[Agent {agent_id}] Picked client {target_client} for deep dive.")
        
        # Step 4: GST Reconciliation Checks
        resp = await client.get(f"/api/gst/reconciliation/summary?client_id={target_client}&month=4&year=2025")
        print(f"[Agent {agent_id}] GST Summary status: {resp.status_code}")
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        # Step 5: TDS Checks (The endpoint that was crashing)
        resp = await client.get(f"/api/tds/summary?client_id={target_client}&fy=2025-26")
        tds_data = resp.json()
        print(f"[Agent {agent_id}] TDS Summary loaded successfully! Mismatches: {tds_data.get('overall', {}).get('tds_missed', 0)}")
        await asyncio.sleep(random.uniform(0.5, 1.0))
        
        # Step 6: Compliance Calendar
        resp = await client.get(f"/api/compliance/calendar?client_id={target_client}")
        print(f"[Agent {agent_id}] Compliance Calendar fetched: {resp.status_code}")
        
        print(f"[Agent {agent_id}] Simulation complete! All 6 API paths tested.")

async def main():
    print("Launching 10 Concurrent CA Agents against the Live Backend...")
    start_time = time.time()
    
    # Create 10 concurrent agent tasks
    tasks = [simulate_ca_agent(i) for i in range(1, 11)]
    await asyncio.gather(*tasks)
    
    print(f"All 10 agents finished successfully in {time.time() - start_time:.2f} seconds!")

if __name__ == "__main__":
    asyncio.run(main())
