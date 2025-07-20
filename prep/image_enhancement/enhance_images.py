# enhance_images.py

import os
import glob
import torch
from PIL import Image
from RealESRGAN import RealESRGAN


class ImageEnhancer:
    """
    Класс для повышения разрешения изображений с помощью Real-ESRGAN.
    """

    def __init__(self, upload_folder='./upload/', result_folder='./result/', scale=4):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        print(f"🖥 Используемое устройство: {self.device}")

        self.upload_folder = upload_folder
        self.result_folder = result_folder

        os.makedirs(self.result_folder, exist_ok=True)

        print("📥 Инициализируем модель...")
        self.model = RealESRGAN(self.device, scale=scale)
        self.model.load_weights('weights/RealESRGAN_x4.pth', download=True)
        self.model.model.to(self.device).eval()

    def enhance_all(self):
        """Обрабатывает все изображения в указанной папке."""
        image_paths = glob.glob(os.path.join(self.upload_folder, '*'))
        print(f"🖼 Найдено изображений: {len(image_paths)}")

        for path in image_paths:
            try:
                print(f"🚀 Обрабатываем: {path}")
                image = Image.open(path).convert('RGB')

                # Прогоняем через модель
                sr_image = self.model.predict(image)

                base_name = os.path.basename(path)
                output_path = os.path.join(self.result_folder, base_name)
                sr_image.save(output_path)
                print(f"✅ Сохранено: {output_path}")

            except Exception as e:
                print(f"❌ Ошибка при обработке {path}: {e}")