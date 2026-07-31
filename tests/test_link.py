import pytest
from tests.test_auto_link import test_auto_link_photo

try:
    test_auto_link_photo()
except Exception as e:
    print(e)
