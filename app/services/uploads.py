import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename

ALLOWED = {
    'png': ('image/png', [b'\x89PNG']), 'jpg': ('image/jpeg', [b'\xff\xd8\xff']), 'jpeg': ('image/jpeg', [b'\xff\xd8\xff']),
    'gif': ('image/gif', [b'GIF8']), 'webp': ('image/webp', [b'RIFF']), 'pdf': ('application/pdf', [b'%PDF']),
    'docx': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', [b'PK\x03\x04']),
    'xlsx': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', [b'PK\x03\x04']),
    'txt': ('text/plain', None), 'csv': ('text/csv', None),
}
IMAGE_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def save(file_storage):
    """Validate (extension + magic bytes + text decoding) and store with a random name."""
    if not file_storage or not file_storage.filename:
        raise ValueError('No file selected.')
    name = secure_filename(file_storage.filename)
    ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
    if ext not in ALLOWED:
        raise ValueError('File type not allowed. Allowed: ' + ', '.join(sorted(ALLOWED)))
    mime, magics = ALLOWED[ext]
    head = file_storage.stream.read(2048)
    file_storage.stream.seek(0)
    if magics and not any(head.startswith(m) for m in magics):
        raise ValueError('File content does not match its extension.')
    if ext in ('txt', 'csv'):
        try:
            head.decode('utf-8')
        except UnicodeDecodeError:
            if len(head) < 2048:
                raise ValueError('Text files must be UTF-8 encoded.')
    stored = f'{uuid.uuid4().hex}.{ext}'
    folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, stored)
    file_storage.save(path)
    return stored, name, mime, os.path.getsize(path)


def is_image(name):
    return name.rsplit('.', 1)[-1].lower() in IMAGE_EXT
