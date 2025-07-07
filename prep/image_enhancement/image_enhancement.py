# image_enhancement.py

import torch
import numpy as np
from PIL import Image
from basicsr.utils import img2tensor, tensor2img


class ImageEnhancement:
    """
    Класс для повышения разрешения изображений с помощью Real-ESRGAN.
    """

    def __init__(self, device=None, scale=4, model_name='RealESRGAN_x4plus'):
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.scale = scale
        self.model_name = model_name
        self.model_path = f'weights/{self.model_name}.pth'

        # Создаем opt — словарь с параметрами модели
        self.opt = {
            'network_g': {
                'type': 'RRDBNet',
                'num_in_ch': 3,
                'num_out_ch': 3,
                'num_feat': 64,
                'num_block': 23,
                'num_grow_ch': 32,
            },
            'path': {
                'pretrain_network_g': self.model_path,
            },
            'scale': scale,
            'param_key': 'params_ema',  # ✅ ВАЖНО: именно этот ключ нужен для этой модели
        }

        from realesrgan import RealESRGANModel
        self.model = RealESRGANModel(self.opt)
        self.model.net_g.to(self.device).eval()

    def predict(self, img: Image.Image):
        """Прогоняет изображение через модель Real-ESRGAN"""
        img_np = np.array(img)
        img_tensor = img2tensor(img_np / 255.0, bgr2rgb=False).unsqueeze(0).to(self.device)

        with torch.no_grad():
            output_tensor = self.model.net_g(img_tensor).clamp_(0, 1)

        output_img = tensor2img(output_tensor, rgb2bgr=False, min_max=(0, 1))
        return Image.fromarray((output_img * 255).astype(np.uint8))

    def process_images(self, upload_folder='./upload/', result_folder='./result/'):
        """
        Обрабатывает все изображения в указанной папке.
        :param upload_folder: Путь к исходным изображениям.
        :param result_folder: Путь для сохранения результата.
        """
        import os
        import glob

        os.makedirs(result_folder, exist_ok=True)
        image_paths = glob.glob(os.path.join(upload_folder, '*'))

        for path in image_paths:
            try:
                print(f"🚀 Обработка: {path}")
                image = Image.open(path).convert('RGB')

                sr_image = self.predict(image)

                base_name = os.path.basename(path)
                output_path = os.path.join(result_folder, base_name)
                sr_image.save(output_path)
                print(f"✅ Сохранено: {output_path}")

            except Exception as e:
                print(f"❌ Ошибка при обработке {path}: {e}")