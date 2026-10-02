"""Content-addressed private objects. Keys never use user filenames."""
from hashlib import sha256
from pathlib import Path
import os
import re
import tempfile

MAX_BYTES = 20 * 1024 * 1024


def object_key(owner, data):
    if not data or len(data) > MAX_BYTES:
        raise ValueError('Content must be between 1 byte and 20 MiB')
    return sha256(owner.encode()).hexdigest() + '/' + sha256(data).hexdigest()


def validate_key(key):
    if not re.fullmatch(r'[0-9a-f]{64}/[0-9a-f]{64}', key):
        raise ValueError('Invalid object key')


class LocalObjects:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def put(self, owner, data, media_type):
        key = object_key(owner, data)
        path = self.root / key
        path.parent.mkdir(exist_ok=True, mode=0o700)
        # Atomic rename; identical keys have identical bytes even under retries.
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as f:
            f.write(data)
            temp = f.name
        os.replace(temp, path)
        return key

    def get(self, key):
        validate_key(key)
        data = (self.root / key).read_bytes()
        if sha256(data).hexdigest() != key.split('/')[1]:
            raise ValueError('Object hash mismatch')
        return data


class S3Objects:
    def __init__(self, bucket, client=None):
        import boto3
        from botocore.config import Config
        self.bucket = bucket
        self.client = client or boto3.client('s3', config=Config(
            connect_timeout=5, read_timeout=30, max_pool_connections=4,
            retries={'total_max_attempts': 2, 'mode': 'standard'}))

    def put(self, owner, data, media_type):
        key = object_key(owner, data)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data,
                               ContentType=media_type, ServerSideEncryption='AES256')
        return key

    def get(self, key):
        validate_key(key)
        with self.client.get_object(Bucket=self.bucket, Key=key)['Body'] as body:
            data = body.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES or sha256(data).hexdigest() != key.split('/')[1]:
            raise ValueError('Object size/hash mismatch')
        return data
