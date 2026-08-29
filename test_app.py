import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

import os
import time
import shutil

from pathlib import Path
from app.downloader import downloader_service
from app.cleanup import cleanup_expired_files, get_dir_size, get_storage_stats
from app.config import settings

def test_url_extraction():
    print("Testing URL extraction...")
    urls = [
        ("https://www.scribd.com/document/123456789/Sample-Book-Title", "123456789"),
        ("https://www.scribd.com/doc/987654321/Another-Doc", "987654321"),
        ("https://www.scribd.com/embeds/555666777/content", "555666777"),
        ("https://id.scribd.com/document/11223344/Test", "11223344"),
        ("99887766", "99887766")
    ]
    for url, expected_id in urls:
        doc_id = downloader_service.extract_doc_id(url)
        assert doc_id == expected_id, f"Failed for {url}: expected {expected_id}, got {doc_id}"
        print(f"  [OK] '{url}' -> ID: {doc_id}")
    print("URL extraction tests passed!\n")

def test_page_range_parsing():
    print("Testing page range parsing...")
    assert downloader_service.parse_pages_range("all", 10) == list(range(1, 11))
    assert downloader_service.parse_pages_range("1-5", 10) == [1, 2, 3, 4, 5]
    assert downloader_service.parse_pages_range("1,3,7-9", 10) == [1, 3, 7, 8, 9]
    assert downloader_service.parse_pages_range("8-15", 10) == [8, 9, 10]
    print("  [OK] Page range parsing tests passed!\n")

def test_filename_sanitizer():
    print("Testing filename sanitizer...")
    clean = downloader_service.sanitize_filename("Tài Liệu: Lập Trình? <Java> & Python* / 2026")
    assert "?" not in clean and ":" not in clean and "<" not in clean and ">" not in clean
    print(f"  [OK] Cleaned filename: {clean}")
    print("Filename sanitizer tests passed!\n")

def test_cleanup_mechanism():
    print("Testing auto-cleanup mechanism...")
    test_dir = settings.DOWNLOADS_DIR / "test_cleanup_task"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "sample.pdf"
    test_file.write_bytes(b"%PDF-1.4 dummy pdf content for testing")
    
    # Set modification time to 2 hours ago
    two_hours_ago = time.time() - 7200
    os.utime(test_file, (two_hours_ago, two_hours_ago))
    os.utime(test_dir, (two_hours_ago, two_hours_ago))
    
    stats_before = get_storage_stats()
    print(f"  Storage before cleanup: {stats_before['total_items']} items, {stats_before['total_size_bytes']} bytes")
    
    # Run cleanup with 30 min max age
    result = cleanup_expired_files(max_age_minutes=30)
    print(f"  Cleanup result: deleted folders: {result['deleted_folders']}, freed bytes: {result['freed_bytes']}")
    
    assert not test_dir.exists(), "Expired test directory was not cleaned up!"
    print("  [OK] Auto-cleanup test passed!\n")

def test_fastapi_endpoints():
    print("Testing FastAPI app routes & template rendering...")
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    
    # 1. Test GET /
    res = client.get("/")
    assert res.status_code == 200
    assert "Scribd Document Downloader" in res.text
    print("  [OK] GET / rendered HTML successfully!")

    # 2. Test GET /api/storage
    res = client.get("/api/storage")
    assert res.status_code == 200
    assert "cleanup_ttl_minutes" in res.json()
    print("  [OK] GET /api/storage returned JSON stats!")

    # 3. Test POST /api/download with invalid URL
    res = client.post("/api/download", json={"url": "invalid_url_without_id"})
    assert res.status_code == 400
    print("  [OK] POST /api/download validated invalid URL successfully!")

    print("FastAPI endpoints tests passed!\n")

if __name__ == "__main__":
    print("=== STARTING APPLICATION VERIFICATION TESTS ===\n")
    test_url_extraction()
    test_page_range_parsing()
    test_filename_sanitizer()
    test_cleanup_mechanism()
    test_fastapi_endpoints()
    print("=== ALL UNIT TESTS PASSED SUCCESSFULLY! ===")

