import os
import sys
import tempfile
import shutil
import subprocess
import glob
import json
import argparse
from pathlib import Path
from multiprocessing import Process, Queue
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

def extract_archives(input_dir, temp_dir):
    """Extract all compressed archives in input_dir to temp_dir. Supports .zip, .tar.gz, .tgz, .tar.bz2, .tar"""
    archives = [f for f in os.listdir(input_dir) if f.endswith((".zip", ".tar.gz", ".tgz", ".tar.bz2", ".tar"))]
    extracted_dirs = []
    for archive in archives:
        archive_path = os.path.join(input_dir, archive)
        extract_path = os.path.join(temp_dir, os.path.splitext(os.path.splitext(archive)[0])[0])
        os.makedirs(extract_path, exist_ok=True)
        if archive.endswith(".zip"):
            shutil.unpack_archive(archive_path, extract_path, 'zip')
        elif archive.endswith((".tar.gz", ".tgz")):
            shutil.unpack_archive(archive_path, extract_path, 'gztar')
        elif archive.endswith(".tar.bz2"):
            shutil.unpack_archive(archive_path, extract_path, 'bztar')
        elif archive.endswith(".tar"):
            shutil.unpack_archive(archive_path, extract_path, 'tar')
        else:
            continue
        extracted_dirs.append(extract_path)
    return extracted_dirs

def run_make_test(dirs):
    """Run 'make test' in each directory in parallel using multiprocessing"""
    def worker(directory, queue):
        try:
            # Call make test TARGET=<directory>
            subprocess.run(["make", "test", f"TARGET={directory}"], cwd=directory, check=True)
            queue.put((directory, True, None))
        except subprocess.CalledProcessError as e:
            queue.put((directory, False, str(e)))

    processes = []
    queue = Queue()
    n = len(dirs)
    bar = tqdm(total=n, desc="Testing", unit="dir") if tqdm else None
    for d in dirs:
        p = Process(target=worker, args=(d, queue))
        p.start()
        processes.append(p)
    completed = 0
    errors = []
    while completed < n:
        directory, success, error = queue.get()
        completed += 1
        if bar:
            bar.update(1)
        if not success:
            errors.append((directory, error))
    for p in processes:
        p.join()
    if bar:
        bar.close()
    for directory, error in errors:
        print(f"Error running make test in {directory}: {error}")

def collect_json_files(dirs):
    """Collect all .json files generated in each directory after make test"""
    json_files = []
    for d in dirs:
        # Find all .json files in the directory (non-recursive)
        files = glob.glob(os.path.join(d, "*.json"))
        json_files.extend(files)
    return json_files

def compact_json_to_jsonl(json_files, output_jsonl):
    """Compact all JSON files into a single JSONL file"""
    with open(output_jsonl, "w") as out:
        for jf in json_files:
            with open(jf, "r") as f:
                try:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            out.write(json.dumps(item) + "\n")
                    else:
                        out.write(json.dumps(data) + "\n")
                except Exception as e:
                    print(f"Error reading {jf}: {e}")

def main():
    parser = argparse.ArgumentParser(description="Extract archives, run make test in each, and collect JSON results.")
    parser.add_argument("input_dir", help="Directory containing compressed archives")
    args = parser.parse_args()
    input_dir = args.input_dir
    if not os.path.isdir(input_dir):
        print(f"Input directory {input_dir} does not exist")
        sys.exit(1)

    repo_root = Path(__file__).parent.resolve()
    with tempfile.TemporaryDirectory() as temp_dir:
        extracted_dirs = extract_archives(input_dir, temp_dir)
        if tqdm and not extracted_dirs:
            print("No archives found to extract.")
        run_make_test(extracted_dirs)
        json_files = collect_json_files(extracted_dirs)
        output_jsonl = repo_root / f"results-{os.path.basename(os.path.normpath(input_dir))}.jsonl"
        compact_json_to_jsonl(json_files, output_jsonl)
        print(f"Results written to {output_jsonl}")
    if tqdm is None:
        print("[INFO] For progress bar support, install tqdm: pip install tqdm")

if __name__ == "__main__":
    main()
