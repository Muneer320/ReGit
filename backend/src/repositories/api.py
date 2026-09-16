"""HTTP adapter for immutable repository snapshots."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from .service import MAX_BATCH_BYTES, MAX_FILE_BYTES, Repositories, RepositoryError


class CreateRepository(BaseModel):
    name: str


class Change(BaseModel):
    path: str
    branch: str = 'main'
    base_commit: str | None = None
    message: str


class Edit(Change):
    content: str


class Branch(BaseModel):
    name: str
    from_commit: str


def router(get_store, get_user):
    routes = APIRouter(prefix='/api/repositories')

    @routes.get('')
    def listing(store=Depends(get_store)):
        return Repositories(store).list()

    @routes.post('', status_code=201)
    def create(body: CreateRepository, store=Depends(get_store), user=Depends(get_user)):
        return Repositories(store).create(body.name, user)

    @routes.get('/{rid}')
    def snapshot(rid: str, branch: str = 'main', commit: str | None = None, store=Depends(get_store)):
        return Repositories(store).snapshot(rid, branch, commit)

    @routes.get('/{rid}/history')
    def history(rid: str, branch: str = 'main', store=Depends(get_store)):
        return Repositories(store).history(rid, branch)

    @routes.post('/{rid}/branches', status_code=201)
    def create_branch(rid: str, body: Branch, store=Depends(get_store), user=Depends(get_user)):
        return Repositories(store).create_branch(rid, body.name, body.from_commit)

    @routes.post('/{rid}/folders', status_code=201)
    def folder(rid: str, body: Change, store=Depends(get_store), user=Depends(get_user)):
        return Repositories(store).folder(rid, body.path, body.branch, body.base_commit, body.message, user)

    @routes.post('/{rid}/files', status_code=201)
    async def upload(rid: str, files: list[UploadFile] = File(...), path: str = Form(''),
                     branch: str = Form('main'), base_commit: str = Form(...),
                     message: str = Form(...), file_type: str = Form('auto'),
                     store=Depends(get_store), user=Depends(get_user)):
        if len(files) > 50:
            raise RepositoryError(413, 'BATCH_LIMIT', 'At most 50 files per upload.')
        uploads = []
        total = 0
        for file in files:
            data = await file.read(MAX_FILE_BYTES + 1)
            total += len(data)
            if len(data) > MAX_FILE_BYTES or total > MAX_BATCH_BYTES:
                raise RepositoryError(413, 'UPLOAD_LIMIT', 'At most 16 MiB per file and 64 MiB per batch.')
            uploads.append((file.filename or 'upload', data))
        return Repositories(store).upload(rid, uploads, path, branch, base_commit, message, user, file_type)

    @routes.get('/{rid}/file')
    def file(rid: str, path: str, branch: str = 'main', commit: str | None = None,
             download: bool = False, store=Depends(get_store)):
        _, data = Repositories(store).file(rid, path, branch, commit)
        filename = path.replace('\\', '/').rsplit('/', 1)[-1]
        disposition = 'attachment' if download else 'inline'
        return Response(data, media_type='application/octet-stream', headers={
            'Content-Disposition': f"{disposition}; filename*=UTF-8''{quote(filename, safe='')}",
            'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'none'; sandbox",
        })

    @routes.patch('/{rid}/file')
    def edit(rid: str, body: Edit, store=Depends(get_store), user=Depends(get_user)):
        return Repositories(store).edit(rid, body.path, body.content, body.branch, body.base_commit, body.message, user)

    @routes.delete('/{rid}/entry')
    def delete(rid: str, body: Change, store=Depends(get_store), user=Depends(get_user)):
        return Repositories(store).delete_entry(rid, body.path, body.branch, body.base_commit, body.message, user)

    @routes.delete('/{rid}', status_code=204)
    def delete_repository(rid: str, store=Depends(get_store), user=Depends(get_user)):
        with store._tx() as db:
            Repositories(store)._repository(rid)
            db.execute('INSERT OR REPLACE INTO tombstones VALUES (?,datetime(\'now\'))', (rid,))
        return Response(status_code=204)

    return routes
