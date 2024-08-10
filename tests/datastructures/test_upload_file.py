from speedy.datastructures import UploadFile, Headers


async def test_upload_file_input() -> None:
    file = UploadFile(filename='file', file_data=b'data')
    assert await file.read() == b'data'
    assert await file.size() == 4
    await file.write(b' and more data!')
    assert await file.read() == b''
    assert await file.size() == 19
    await file.seek(0)
    assert await file.read() == b'data and more data!'


async def test_upload_file_rolling() -> None:
    file = UploadFile(filename='file', file_data=b'', size=0)
    file.file._rolled = True
    assert await file.read() == b''
    assert await file.size() == 0
    await file.write(b'data')
    assert await file.read() == b''
    assert await file.size() == 4
    await file.seek(0)
    assert await file.read() == b'data'
    await file.write(b' more')
    assert await file.read() == b''
    assert await file.size() == 9
    await file.seek(0)
    assert await file.read() == b'data more'
    assert await file.size() == 9
    await file.close()


async def test_upload_file_repr() -> None:
    file = UploadFile(filename='file', file_data=b'', size=0)
    assert repr(file) == "UploadFile(filename='file', headers=Headers({}))"
    file = UploadFile(filename='file', file_data=b'', size=0, headers={'content-type': 'video/mp4'})
    assert repr(file) == "UploadFile(filename='file', headers=Headers({'content-type': 'video/mp4'}))"
    file = UploadFile(filename='file', file_data=b'', size=0, headers=Headers({'content-type': 'video/mp4'}))
    assert repr(file) == "UploadFile(filename='file', headers=Headers({'content-type': 'video/mp4'}))"
