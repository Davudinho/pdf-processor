import concurrent.futures
import requests
import time
import unittest

BASE_URL = "http://localhost:5000"

class TestConcurrencyStress(unittest.TestCase):
    """
    Testet, wie der Server reagiert, wenn sehr viele Anfragen gleichzeitig eintreffen.
    Deckt fehlendes Queue-Management bzw. unlimitierte Thread-Spawns auf.
    """
    
    def simulate_agent_task(self, user_id):
        """Sendet einen einzelnen Task an den Agenten."""
        try:
            response = requests.post(
                f"{BASE_URL}/agent/task", 
                json={"task": f"Dummy Aufgabe von User {user_id}. Bitte sofort abarbeiten."},
                timeout=5
            )
            return response.status_code
        except Exception as e:
            return "Timeout/Error"

    def test_concurrent_agent_tasks(self):
        """Sendet 20 Agenten-Tasks gleichzeitig an den Server."""
        try:
            requests.get(BASE_URL, timeout=2)
        except requests.exceptions.ConnectionError:
            self.skipTest("Server läuft nicht auf localhost:5000.")

        NUM_CONCURRENT_USERS = 20
        results = []
        
        print(f"\n[Stress Test] Sende {NUM_CONCURRENT_USERS} parallele Tasks an den Agenten...")
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_CONCURRENT_USERS) as executor:
            # Starte alle Requests gleichzeitig
            futures = [executor.submit(self.simulate_agent_task, i) for i in range(NUM_CONCURRENT_USERS)]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
                
        duration = time.time() - start_time
        print(f"[Stress Test] Fertig in {duration:.2f} Sekunden.")
        
        # Auswertung
        success_count = results.count(200)
        error_count = len(results) - success_count
        
        print(f"Erfolgreich angenommen (200 OK): {success_count}")
        print(f"Abgelehnt / Timeout: {error_count}")
        
        # HINWEIS: Solange wir `threading.Thread` ohne Limit in app.py verwenden, 
        # wird der lokale PC das locker schaffen. Auf Render.com mit 512MB RAM 
        # würden 20 parallele Python-Agent-Threads jedoch sofort zum "Out of Memory" (OOM) führen!
        if success_count == NUM_CONCURRENT_USERS:
            print("✓ Server hat alle angenommen. (WARNUNG: Auf kleinen Servern droht OOM ohne Queue!)")
        else:
            print(f"SCHWACHSTELLE: Der Server ist unter der Last zusammengebrochen ({error_count} Fehler).")

if __name__ == "__main__":
    unittest.main()
