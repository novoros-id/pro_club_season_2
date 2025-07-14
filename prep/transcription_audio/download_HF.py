from huggingface_hub import hf_hub_download
from tqdm.auto import tqdm

# заранее скачиваем модель с прогресс-баром
model_path = hf_hub_download(
    repo_id="antony66/whisper-large-v3-russian",
    filename="model.safetensors",
    force_download=True # если обрывается – докачаем
)