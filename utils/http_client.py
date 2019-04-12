from functools import partial
from tornado import httpclient
from urllib.parse import quote
from uuid import uuid4
import mimetypes


# Using HTTP POST, upload one or more files in a single multipart-form-encoded
# request.
async def multipart_producer(boundary, filenames, write):
    boundary_bytes = boundary.encode()

    for filename in filenames:
        filename_bytes = filename.encode()
        mtype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        buf = (
                (b'--%s\r\n' % boundary_bytes) +
                (b'Content-Disposition: form-data; name="%s"; filename="%s"\r\n' %
                 (filename_bytes, filename_bytes)) +
                (b'Content-Type: %s\r\n' % mtype.encode()) +
                b'\r\n'
        )
        await write(buf)
        with open(filename, 'rb') as f:
            while True:
                # 16k at a time.
                chunk = f.read(16 * 1024)
                if not chunk:
                    break
                await write(chunk)
        await write(b'\r\n')

    await write(b'--%s--\r\n' % (boundary_bytes,))


async def upload(filenames, url):
    client = httpclient.AsyncHTTPClient()
    boundary = uuid4().hex
    headers = {'Content-Type': 'multipart/form-data; boundary=%s' % boundary}
    producer = partial(multipart_producer, boundary, filenames)
    response = await client.fetch(
        url, method='POST', headers=headers, body_producer=producer)
    return response


async def raw_producer(filename, write):
    with open(filename, 'rb') as f:
        while True:
            # 16K at a time.
            chunk = f.read(16 * 1024)
            if not chunk:
                # Complete.
                break
            await write(chunk)
