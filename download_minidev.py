import os
import sys
import zipfile
import urllib.request
from tqdm import tqdm

URL = "https://bird-bench.oss-cn-beijing.aliyuncs.com/minidev.zip"
ZIP_PATH = "minidev.zip"

class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)

def download_file(url, output_path):
    print(f"Downloading {url} to {output_path}...")
    with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=output_path) as t:
        urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)

def main():
    if not os.path.exists(ZIP_PATH):
        download_file(URL, ZIP_PATH)
    else:
        print(f"{ZIP_PATH} already exists.")
    
    print("Extracting minidev.zip...")
    extract_dir = "temp_minidev"
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    print(f"Extracted to {extract_dir}.")

if __name__ == "__main__":
    main()
