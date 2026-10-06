"""Standard-library installation boundaries, locks and durable small files."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


def path(value):
    from private_setup import safe_path
    result = safe_path(value)
    if '..' in Path(value).parts:
        raise ValueError('Parent traversal is unsupported')
    return result


def read(file, limit=2 * 1024 * 1024):
    file = path(file)
    fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise ValueError('Expected a bounded private regular file')
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Private file is too large')
    return data


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic(file, data, mode=0o600):
    file = path(file)
    if file.exists():
        read(file)
    fd, temporary = tempfile.mkstemp(prefix='.install-', dir=file.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, file)
        directory = os.open(file.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def runtime_lock(root, shared=False):
    file = path(root)/'.runtime.lock'
    fd = os.open(file, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(fd).st_nlink != 1 or not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Invalid runtime lock')
        try:
            fcntl.flock(fd, (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Runtime is busy. Stop its connection before installing or updating.') from None
        yield
    finally:
        os.close(fd)
