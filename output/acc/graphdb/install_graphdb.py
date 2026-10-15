"""Download official portable GraphDB Free and Temurin JRE; retain hashes."""
import concurrent.futures
import hashlib
import json
import pathlib
import urllib.request
import zipfile

BASE = pathlib.Path(__file__).resolve().parent
DOWNLOADS = BASE / 'downloads'
INSTALL = pathlib.Path.home() / 'AppData/Local/Programs/GraphDB-10.6.4'
ITEMS = [
    ('graphdb', 'https://maven.ontotext.com/repository/owlim-releases/com/ontotext/graphdb/graphdb/10.6.4/graphdb-10.6.4-dist.zip', 271396855),
    ('java', 'https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.20.1%2B1/OpenJDK17U-jre_x64_windows_hotspot_17.0.20.1_1.zip', 43780109),
]

def fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'IBC-GraphDB-Setup'}), timeout=90)

def install(item):
    name, url, expected_size = item
    archive = DOWNLOADS / (name + '.zip')
    if not archive.exists() or archive.stat().st_size != expected_size:
        partial = archive.with_suffix('.partial')
        print('Downloading ' + name, flush=True)
        with fetch(url) as response, partial.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if partial.stat().st_size != expected_size:
            raise ValueError('Unexpected download size: ' + name)
        partial.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    verified_checksum = None
    if name == 'java':
        with fetch(url + '.sha256.txt') as response:
            expected_hash = response.read().decode().split()[0]
        if digest.lower() != expected_hash.lower():
            raise ValueError('Java SHA256 mismatch')
        verified_checksum = expected_hash
    destination = INSTALL / name
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError('Unsafe zip member')
        if bad := z.testzip():
            raise ValueError('Archive CRC failure: ' + bad)
        z.extractall(destination)
    print('Installed ' + name, flush=True)
    return {'name': name, 'url': url, 'archive': str(archive), 'bytes': expected_size,
            'sha256': digest, 'publisher_checksum_verified': verified_checksum is not None,
            'destination': str(destination), 'archive_crc_verified': True}

if __name__ == '__main__':
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(install, ITEMS))
    (BASE / 'installation_manifest.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2), flush=True)
