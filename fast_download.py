import os
import sys
import threading
import urllib.request
import zipfile
import time
from tqdm import tqdm

URL = "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"
OUTPUT = "minidev.zip"
NUM_CHUNKS = 8

def get_file_size(url):
    req = urllib.request.Request(url, method='HEAD')
    with urllib.request.urlopen(req) as resp:
        return int(resp.headers['Content-Length'])

def download_chunk(url, start, end, chunk_id, part_file, progress_dict, lock):
    expected_size = end - start + 1
    existing = os.path.getsize(part_file) if os.path.exists(part_file) else 0
    
    if existing >= expected_size:
        with lock:
            progress_dict['downloaded'] += expected_size
        return

    actual_start = start + existing
    with lock:
        progress_dict['downloaded'] += existing
        
    headers = {'Range': f'bytes={actual_start}-{end}'}
    req = urllib.request.Request(url, headers=headers)
    
    with urllib.request.urlopen(req) as resp, open(part_file, 'ab') as f:
        while True:
            data = resp.read(65536)
            if not data:
                break
            f.write(data)
            with lock:
                progress_dict['downloaded'] += len(data)

def extract_all():
    print(f"Extracting {OUTPUT} into mini_dev_databases/...")
    target_dir = "mini_dev_databases"
    os.makedirs(target_dir, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, 'r') as zip_ref:
        zip_ref.extractall("temp_extracted")
        
    # Di chuyển các thư mục CSDL vào mini_dev_databases
    extracted_root = "temp_extracted"
    for root, dirs, files in os.walk(extracted_root):
        for d in dirs:
            sqlite_candidate = os.path.join(root, d, f"{d}.sqlite")
            if os.path.exists(sqlite_candidate):
                dst = os.path.join(target_dir, d)
                if not os.path.exists(dst):
                    import shutil
                    shutil.move(os.path.join(root, d), dst)
                    print(f"  [+] Extracted DB: {d}")
    print("All databases extracted successfully!")

def main():
    if os.path.exists(OUTPUT):
        print(f"{OUTPUT} already exists. Extracting...")
        extract_all()
        return

    total_size = get_file_size(URL)
    print(f"Total size: {total_size / (1024*1024):.2f} MB. Using {NUM_CHUNKS} threads (Supports Auto-Resume).")
    
    chunk_size = total_size // NUM_CHUNKS
    threads = []
    part_files = []
    progress_dict = {'downloaded': 0}
    lock = threading.Lock()
    
    for i in range(NUM_CHUNKS):
        start = i * chunk_size
        end = (start + chunk_size - 1) if i < NUM_CHUNKS - 1 else total_size - 1
        part_file = f"{OUTPUT}.part{i}"
        part_files.append(part_file)
        t = threading.Thread(target=download_chunk, args=(URL, start, end, i, part_file, progress_dict, lock))
        threads.append(t)
        t.start()
        
    with tqdm(total=total_size, unit='B', unit_scale=True, desc="Multi-part Download") as pbar:
        last = 0
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
            with lock:
                curr = progress_dict['downloaded']
            pbar.update(curr - last)
            last = curr
        with lock:
            curr = progress_dict['downloaded']
        pbar.update(curr - last)
        
    for t in threads:
        t.join()
        
    print("Combining parts...")
    with open(OUTPUT, 'wb') as out_f:
        for part in part_files:
            with open(part, 'rb') as in_f:
                while True:
                    buf = in_f.read(1024*1024)
                    if not buf:
                        break
                    out_f.write(buf)
            os.remove(part)
    print("Download and combination complete!")
    extract_all()

if __name__ == "__main__":
    main()
