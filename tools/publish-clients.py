"""Fetch a bounded transfer manifest, verify signatures, then publish assets."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPO = 'dawvia/dawvia'


def gh(*args):
    try:
        return json.loads(subprocess.check_output(['gh', *args], text=True, stderr=subprocess.PIPE))
    except subprocess.CalledProcessError as error:
        raise RuntimeError('GitHub API: ' + error.stderr.strip()) from error


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(data, signature, directory):
    if len(signature) != 384:
        raise ValueError('Invalid RSA signature length')
    (directory / 'signature').write_bytes(signature)
    subprocess.run(['openssl', 'dgst', '-sha256', '-verify', str(ROOT / 'release-public.pem'),
                    '-signature', str(directory / 'signature')], input=data, check=True,
                   stdout=subprocess.DEVNULL)


def main():
    items = json.loads((ROOT / 'release-transfer.json').read_text())
    with tempfile.TemporaryDirectory() as temporary:
        staged = []
        for item in items:
            revision, target = item['source_sha'], item['platform']
            if not re.fullmatch('[a-f0-9]{40}', revision) or target not in ('darwin-arm64', 'linux-amd64', 'linux-arm64'):
                raise ValueError('Invalid client identity')
            directory = Path(temporary) / target; directory.mkdir()
            archive_name = 'dawvia-' + target + '.tar.gz'
            if set(item['files']) != {archive_name, 'SHA256SUMS', 'SHA256SUMS.sig'}:
                raise ValueError('Only signed public client files may be transferred')
            for name, expected in item['files'].items():
                if not re.fullmatch('[a-f0-9]{64}', expected):
                    raise ValueError('Invalid digest')
                url = item['transfer_url'] + '/' + name
                if not url.startswith('https://dawvia.com/downloads/computer/transfer-'):
                    raise ValueError('Unapproved transfer location')
                path = directory / name
                subprocess.run(['curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
                                '--retry', '3', '--connect-timeout', '15', '--max-time', '300', url, '-o', str(path)], check=True)
                if digest(path) != expected:
                    raise ValueError('Transferred asset hash mismatch: ' + name)
            sums = (directory / 'SHA256SUMS').read_bytes()
            verify(sums, (directory / 'SHA256SUMS.sig').read_bytes(), directory)
            if sums != (digest(directory / archive_name) + '  ' + archive_name + '\n').encode():
                raise ValueError('Aggregate checksum mismatch')
            with tarfile.open(directory / archive_name) as archive:
                members = archive.getmembers()
                if [m.name for m in members] != ['dawvia', 'SHA256SUMS', 'SHA256SUMS.sig'] or not all(m.isfile() for m in members):
                    raise ValueError('Unsafe archive members')
                binary = archive.extractfile('dawvia').read()
                manifest = archive.extractfile('SHA256SUMS').read()
                verify(manifest, archive.extractfile('SHA256SUMS.sig').read(), directory)
                expected = ('# dawvia-client-v1 ' + revision + ' ' + target + '\n' +
                            hashlib.sha256(binary).hexdigest() + '  dawvia\n').encode()
                if manifest != expected:
                    raise ValueError('Signed binary identity mismatch')
            staged.append((item, directory))
            print('::notice title=Verified client::' + target + ' ' + revision, flush=True)
        # No external mutation until every platform has passed verification.
        for item, directory in staged:
            tag = 'client-' + item['source_sha']
            releases = gh('api', 'repos/' + REPO + '/releases?per_page=100')
            matches = [r for r in releases if r['tag_name'] == tag]
            if not matches:
                subprocess.run(['gh', 'release', 'create', tag, '--repo', REPO, '--draft', '--title',
                                'Dawvia ' + item['platform'] + ' — signed distribution', '--notes',
                                'Signed distribution of the existing public client. Original source: ' + item['source_sha'] +
                                '. Executable bytes are unchanged; RSA/SHA256 signatures protect distribution.'], check=True)
                matches = [r for r in gh('api', 'repos/' + REPO + '/releases?per_page=100') if r['tag_name'] == tag]
            release = sorted(matches, key=lambda r: (not r['draft'], r['id']))[-1]
            existing = {a['name']: a for a in release['assets']}
            for name, expected in item['files'].items():
                if name in existing:
                    if existing[name].get('digest') != 'sha256:' + expected or existing[name]['state'] != 'uploaded':
                        raise ValueError('Refusing to overwrite a mismatched published asset')
                    continue
                endpoint = 'https://uploads.github.com/repos/' + REPO + '/releases/' + str(release['id']) + '/assets?name=' + name
                asset = gh('api', '--method', 'POST', endpoint, '--header', 'Content-Type: application/octet-stream',
                           '--input', str(directory / name))
                if asset['state'] != 'uploaded' or asset.get('digest') != 'sha256:' + expected:
                    raise ValueError('GitHub did not persist the expected asset')
                print('UPLOADED', tag, name, asset['size'], flush=True)
            if release['draft']:
                subprocess.run(['gh', 'release', 'edit', tag, '--repo', REPO, '--draft=false', '--latest=false'], check=True)
            print('PUBLISHED', 'https://github.com/' + REPO + '/releases/tag/' + tag, flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('::error title=Client publication failed::' + str(error).replace('\n', '%0A'), flush=True)
        raise
