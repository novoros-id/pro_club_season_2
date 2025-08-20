import os, sys, pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # /.../pro_club_season_2
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

@pytest.fixture(scope="session")
def sample_audio_path():
    path = os.path.join(os.path.dirname(__file__), "data", "sample.wav")
    if not os.path.isfile(path):
        pytest.skip("Нет tests/data/sample.wav — положи короткий WAV для e2e теста")
    return path

@pytest.fixture
def tmp_chroma_dir(tmp_path):
    # отдельный persist для каждого теста
    return str(tmp_path / "vectorstore")