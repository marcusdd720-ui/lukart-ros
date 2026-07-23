import os

def test_canon_folder_exists():
    assert os.path.exists('canon')

def test_canon_is_directory():
    assert os.path.isdir('canon')
