"""STAR may read approved public-source paths, never secrets or arbitrary repos."""
import pytest
from star.repo_intelligence import validate_repo_path, PUBLIC_REPO

def test_public_repo_is_bound_to_star():
    assert PUBLIC_REPO=="oncoursemail/Star-AI"
    assert validate_repo_path("star/agent.py")=="star/agent.py"
    assert validate_repo_path("frontend/src/Desktop.tsx")=="frontend/src/Desktop.tsx"
    assert validate_repo_path("README.md")=="README.md"

@pytest.mark.parametrize("path",[
    "../secrets.txt",".env","star/../README.md","/.git/config",
    "https://evil.example/steal","star/private_token.py","star/.env",
    "installer/STAR.iss","star/model.gguf","frontend/public/star.svg",
    "star\\\\agent.py","star//agent.py"
])
def test_unreviewed_or_unsafe_repository_paths_rejected(path):
    with pytest.raises((PermissionError,ValueError)):
        validate_repo_path(path)
