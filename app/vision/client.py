"""Initial build uses mock extraction; live integration is an explicit backlog item."""
from .mock_data import mock_extract

def extract(filename):
    return mock_extract(filename), 'mock'
