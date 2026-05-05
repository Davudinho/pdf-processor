import io
import requests
import unittest

BASE_URL = "http://localhost:5000"

class TestSecurityUploads(unittest.TestCase):
    """
    Sicherheits-Tests für den File-Upload.
    Überprüft, ob das System böswillige oder fehlerhafte Uploads korrekt abweist.
    """

    def test_1_fake_pdf_upload(self):
        """Testet, ob eine Textdatei getarnt als .pdf abgelehnt wird."""
        fake_content = b"Dies ist kein PDF, sondern ein potentiell gefaehrliches Skript."
        files = {
            'file': ('malicious.pdf', io.BytesIO(fake_content), 'application/pdf')
        }
        
        try:
            response = requests.post(f"{BASE_URL}/upload", files=files)
            
            # Da PyMuPDF (fitz) fehlschlägt, erwarten wir aktuell zumindest ein 400 oder 500 Error.
            # Besser wäre eine direkte Magic-Byte-Prüfung VOR dem Verarbeiten.
            data = response.json()
            
            if response.status_code == 200 and data.get("success") is True:
                self.fail("SCHWACHSTELLE: Das System hat eine Fake-PDF-Datei erfolgreich akzeptiert und gespeichert!")
            else:
                print("✓ Fake-PDF wurde korrekt abgelehnt.")
                
        except requests.exceptions.ConnectionError:
            self.skipTest("Server läuft nicht auf localhost:5000.")

    def test_2_oversized_payload(self):
        """Testet, ob das 50MB Limit (MAX_CONTENT_LENGTH) durchgesetzt wird."""
        # Generiere 55 MB Dummy-Daten
        # (Dies testet die Flask-Ebene, bevor der Code überhaupt erreicht wird)
        large_content = b"0" * (55 * 1024 * 1024)
        files = {
            'file': ('massive_file.pdf', io.BytesIO(large_content), 'application/pdf')
        }
        
        try:
            response = requests.post(f"{BASE_URL}/upload", files=files)
            
            if response.status_code != 413:
                self.fail(f"SCHWACHSTELLE: System hat 55MB Datei nicht mit 413 blockiert (Status: {response.status_code})")
            else:
                print("✓ 55MB Payload wurde vom Server korrekt mit HTTP 413 abgeblockt.")
                
        except requests.exceptions.ConnectionError:
            self.skipTest("Server läuft nicht auf localhost:5000.")

if __name__ == "__main__":
    print("Starte Security Upload Tests...")
    unittest.main()
