"""Repository trees are immutable manifests; only branch refs move.

Every upload/folder/edit/delete produces a snapshot with a guarded parent.
Raw file bytes remain downloadable even when a research parser extracts a
different representation. File artifacts are pinned to commits in each tree.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import PurePosixPath

from ..core.ids import new_id
from ..core.objects.store import RefConflictError
from ..ingestion import pipeline
from ..ingestion.parsers import ParseError, parse
from ..retrieval.indexer import get_indexer

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_BATCH_BYTES = 64 * 1024 * 1024


class RepositoryError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def normalize_path(value: str, allow_root: bool = False) -> str:
    value = value.replace('\\', '/').strip()
    if not value and allow_root:
        return ''
    parts = [part for part in value.split('/') if part not in ('', '.')]
    if (not parts or value.startswith('/') or ':' in parts[0]
            or any(part == '..' or any(ord(char) < 32 for char in part) for part in parts)):
        raise RepositoryError(400, 'BAD_PATH', 'Use a repository-relative path without traversal or control characters.')
    if len(value) > 1024 or any(len(part) > 255 for part in parts):
        raise RepositoryError(400, 'BAD_PATH', 'Repository path is too long.')
    return '/'.join(parts)


def now():
    return datetime.now(UTC).isoformat()


class Repositories:
    def __init__(self, store):
        self.store = store

    def _repository(self, repository_id):
        row = self.store.db.execute(
            "SELECT id,title FROM artifacts WHERE id=? AND kind='repository' "
            "AND id NOT IN (SELECT artifact_id FROM tombstones)", (repository_id,),
        ).fetchone()
        if row is None:
            raise RepositoryError(404, 'REPOSITORY_NOT_FOUND', 'Repository does not exist.')
        return row

    def list(self):
        with self.store._lock:
            rows = list(self.store.db.execute(
                "SELECT id,title,created_at FROM artifacts WHERE kind='repository' "
                "AND id NOT IN (SELECT artifact_id FROM tombstones) ORDER BY created_at DESC,id"))
            return [{'id': rid, 'name': title, 'created_at': created,
                     'branches': [{'name': branch, 'head': head} for branch, head in self.store.db.execute(
                         'SELECT name,head FROM refs WHERE artifact_id=? ORDER BY name', (rid,))]}
                    for rid, title, created in rows]

    def create(self, name, user):
        name = name.strip()
        if not name or len(name) > 120:
            raise RepositoryError(400, 'BAD_NAME', 'Repository name must contain 1–120 characters.')
        rid = new_id('repo_')
        with self.store._tx() as db:
            db.execute('INSERT INTO artifacts(id,kind,title,created_at) VALUES (?,?,?,?)',
                       (rid, 'repository', name, now()))
            self._save(rid, 'main', {'version': 1, 'folders': [], 'files': {}}, None, 'Create repository', user)
        return self.snapshot(rid)

    def _tree(self, rid, branch='main', commit=None):
        self._repository(rid)
        cid = commit or self.store.head(branch, rid)
        row = self.store.db.execute('SELECT root_hash FROM commits WHERE id=? AND artifact_id=?', (cid, rid)).fetchone()
        if row is None:
            raise RepositoryError(404, 'COMMIT_NOT_FOUND', 'Repository branch or commit does not exist.')
        return cid, json.loads(self.store.get_blob(row[0]))

    def snapshot(self, rid, branch='main', commit=None):
        with self.store._lock:
            cid, tree = self._tree(rid, branch, commit)
            _, name = self._repository(rid)
            entries = [{'path': path, 'type': 'folder'} for path in tree['folders']]
            entries.extend({'path': path, 'type': 'file', **metadata} for path, metadata in tree['files'].items())
            return {'id': rid, 'name': name, 'branch': branch, 'commit_id': cid,
                    'entries': sorted(entries, key=lambda entry: entry['path']),
                    'branches': [{'name': name, 'head': head} for name, head in self.store.db.execute(
                        'SELECT name,head FROM refs WHERE artifact_id=? ORDER BY name', (rid,))]}

    def _current(self, rid, branch, expected):
        cid, tree = self._tree(rid, branch)
        if expected is None or cid != expected:
            raise RefConflictError('Repository changed; reload before saving this operation.')
        return cid, tree

    def _save(self, rid, branch, tree, parent, message, user):
        if not message.strip():
            raise RepositoryError(400, 'MESSAGE_REQUIRED', 'A commit message is required.')
        tree['folders'] = sorted(set(tree['folders']))
        root = self.store.put_blob('repository', json.dumps(tree, sort_keys=True, separators=(',', ':')).encode())
        return self.store.commit([parent] if parent else [], root, rid, message.strip(), user,
                                 branch=branch, expected_head=parent, kind='repository')

    def _folders(self, tree, path):
        parts = path.split('/')
        for depth in range(1, len(parts) + 1):
            folder = '/'.join(parts[:depth])
            if folder in tree['files']:
                raise RepositoryError(409, 'PATH_EXISTS', f'A file already occupies {folder}.')
            if folder not in tree['folders']:
                tree['folders'].append(folder)

    def folder(self, rid, path, branch, expected, message, user):
        path = normalize_path(path)
        with self.store._tx():
            parent, tree = self._current(rid, branch, expected)
            if path in tree['folders']:
                raise RepositoryError(409, 'PATH_EXISTS', 'Folder already exists.')
            self._folders(tree, path)
            self._save(rid, branch, tree, parent, message, user)
        return self.snapshot(rid, branch)

    def _file_kind(self, filename, data, requested):
        if requested and requested != 'auto':
            return requested
        suffix = PurePosixPath(filename).suffix.lower()
        if suffix == '.pdf':
            return 'pdf'
        if suffix == '.zip':
            return 'codebase'
        if suffix in ('.md', '.markdown'):
            return 'markdown'
        try:
            data.decode('utf-8')
            return 'plaintext'
        except UnicodeDecodeError:
            return 'binary'

    def _import(self, rid, branch, path, data, requested, user):
        kind = self._file_kind(path, data, requested)
        if kind == 'binary':
            units = []
        else:
            units = parse(kind, PurePosixPath(path).name, data)
        raw_hash = self.store.put_blob('raw', data)
        source_id = new_id('src_')
        self.store.db.execute('INSERT INTO sources VALUES (?,?,?,?,?)', (source_id, kind, path, now(), user))
        artifacts = []
        child_branch = f'repository/{rid}/{branch}'
        for unit in units:
            aid = new_id('art_')
            root = pipeline._store_unit(self.store, unit)
            self.store.db.execute('INSERT INTO artifacts VALUES (?,?,?,?,?)', (aid, unit.kind, unit.title, source_id, now()))
            pipeline._add_edge(self.store.db, 'source', source_id, 'artifact', aid, 'imported_as')
            cid = self.store.commit([], root, aid, f'Import {path}', user, branch=child_branch, kind=unit.kind)
            if unit.claims:
                pipeline.write_claims(self.store, aid, cid, unit.claims, source_id)
            pipeline._add_edge(self.store.db, 'artifact', aid, 'version', cid, 'has_version')
            get_indexer(self.store, enable_vectors=False).reindex(cid, branch=child_branch)
            artifacts.append({'artifact_id': aid, 'commit_id': cid, 'kind': unit.kind, 'branch': child_branch})
        return {'raw_hash': raw_hash, 'size': len(data), 'kind': artifacts[0]['kind'] if artifacts else 'binary',
                'artifacts': artifacts, 'editable': len(data) <= MAX_FILE_BYTES and kind in ('markdown', 'plaintext', 'md', 'txt')}

    def upload(self, rid, uploads, folder, branch, expected, message, user, requested='auto'):
        folder = normalize_path(folder, allow_root=True)
        if not uploads or len(uploads) > 50 or sum(len(data) for _, data in uploads) > MAX_BATCH_BYTES:
            raise RepositoryError(413, 'BATCH_LIMIT', 'Upload 1–50 files totalling at most 64 MiB.')
        names = [normalize_path(f'{folder}/{normalize_path(name)}' if folder else name) for name, _ in uploads]
        if len(set(names)) != len(names):
            raise RepositoryError(409, 'DUPLICATE_PATH', 'Two uploaded files have the same repository path.')
        with self.store._tx():
            parent, tree = self._current(rid, branch, expected)
            for path, (_, data) in zip(names, uploads, strict=True):
                if len(data) > MAX_FILE_BYTES:
                    raise RepositoryError(413, 'FILE_LIMIT', 'Each file must be at most 16 MiB.')
                if path in tree['folders']:
                    raise RepositoryError(409, 'PATH_EXISTS', f'A folder already occupies {path}.')
                if '/' in path:
                    self._folders(tree, path.rsplit('/', 1)[0])
                tree['files'][path] = self._import(rid, branch, path, data, requested, user)
            self._save(rid, branch, tree, parent, message, user)
        return self.snapshot(rid, branch)

    def file(self, rid, path, branch='main', commit=None):
        path = normalize_path(path)
        with self.store._lock:
            _, tree = self._tree(rid, branch, commit)
            entry = tree['files'].get(path)
            if entry is None:
                raise RepositoryError(404, 'FILE_NOT_FOUND', 'File does not exist at this revision.')
            return entry, self.store.get_blob(entry['raw_hash'])

    def edit(self, rid, path, content, branch, expected, message, user):
        path = normalize_path(path)
        data = content.encode('utf-8')
        if len(data) > MAX_FILE_BYTES:
            raise RepositoryError(413, 'FILE_LIMIT', 'File exceeds 16 MiB.')
        with self.store._tx():
            parent, tree = self._current(rid, branch, expected)
            entry = tree['files'].get(path)
            if entry is None or not entry['editable']:
                raise RepositoryError(400, 'NOT_EDITABLE', 'Select an editable text file.')
            reference = entry['artifacts'][0]
            aid, previous = reference['artifact_id'], reference['commit_id']
            child_branch = f'repository/{rid}/{branch}'
            current = self.store.head(child_branch, aid)
            if current is None:
                self.store.create_branch(child_branch, aid, previous)
            elif current != previous:
                raise RefConflictError('This file has an unpublished live revision; publish or reload it before editing.')
            root = self.store.put_blob(entry['kind'], data)
            cid = self.store.commit([previous], root, aid, message, user, branch=child_branch,
                                    expected_head=previous, kind=entry['kind'])
            reference.update(commit_id=cid, branch=child_branch)
            entry.update(raw_hash=self.store.put_blob('raw', data), size=len(data))
            get_indexer(self.store, enable_vectors=False).reindex(cid, branch=child_branch)
            self._save(rid, branch, tree, parent, message, user)
        return self.snapshot(rid, branch)

    def delete_entry(self, rid, path, branch, expected, message, user):
        path = normalize_path(path)
        with self.store._tx():
            parent, tree = self._current(rid, branch, expected)
            if path not in tree['files'] and path not in tree['folders']:
                raise RepositoryError(404, 'PATH_NOT_FOUND', 'Path does not exist.')
            tree['files'] = {key: value for key, value in tree['files'].items() if key != path and not key.startswith(path + '/')}
            tree['folders'] = [key for key in tree['folders'] if key != path and not key.startswith(path + '/')]
            self._save(rid, branch, tree, parent, message, user)
        return self.snapshot(rid, branch)

    def create_branch(self, rid, name, from_commit):
        name = name.strip()
        if not name or len(name) > 100 or any(ord(char) < 33 for char in name):
            raise RepositoryError(400, 'BAD_BRANCH', 'Use a branch name of 1–100 non-whitespace characters.')
        with self.store._tx():
            self._tree(rid, commit=from_commit)
            self.store.create_branch(name, rid, from_commit)
        return self.snapshot(rid, name)

    def history(self, rid, branch='main'):
        with self.store._lock:
            self._repository(rid)
            return self.store.history(rid, branch)

    def prepare_live(self, rid, path, branch, expected):
        path = normalize_path(path)
        with self.store._tx():
            _, tree = self._current(rid, branch, expected)
            entry = tree['files'].get(path)
            if not entry or not entry['editable'] or len(entry['artifacts']) != 1:
                raise RepositoryError(400, 'NOT_EDITABLE', 'Live editing requires a text file.')
            reference = dict(entry['artifacts'][0])
            child_branch = f'repository/{rid}/{branch}'
            if self.store.head(child_branch, reference['artifact_id']) is None:
                self.store.create_branch(child_branch, reference['artifact_id'], reference['commit_id'])
            reference['branch'] = child_branch
            return reference

    def publish_live(self, rid, path, branch, expected, message, user):
        from ..provenance.service import ancestors

        path = normalize_path(path)
        with self.store._tx():
            parent, tree = self._current(rid, branch, expected)
            entry = tree['files'].get(path)
            if not entry or not entry['editable'] or len(entry['artifacts']) != 1:
                raise RepositoryError(400, 'NOT_EDITABLE', 'Select a text file with a live commit.')
            reference = entry['artifacts'][0]
            child_branch = f'repository/{rid}/{branch}'
            latest = self.store.head(child_branch, reference['artifact_id'])
            if latest is None or latest == reference['commit_id']:
                raise RepositoryError(409, 'NO_NEW_COMMIT', 'Commit the live draft before publishing its file version.')
            if reference['commit_id'] not in ancestors(self.store, latest):
                raise RefConflictError('The live branch diverged from this file version; reconcile it before publishing.')
            root = self.store.db.execute('SELECT root_hash FROM commits WHERE id=? AND artifact_id=?',
                                         (latest, reference['artifact_id'])).fetchone()
            data = self.store.get_blob(root[0])
            if len(data) > MAX_FILE_BYTES:
                raise RepositoryError(413, 'FILE_LIMIT', 'Live file exceeds 16 MiB.')
            reference.update(commit_id=latest, branch=child_branch)
            entry.update(raw_hash=self.store.put_blob('raw', data), size=len(data))
            self._save(rid, branch, tree, parent, message, user)
        return self.snapshot(rid, branch)
