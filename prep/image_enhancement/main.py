# main.py

from image_enhancement import ImageEnhancement

if __name__ == '__main__':
    enhancer = ImageEnhancement(scale=4)  # можно указать model_name='RealESRGAN_x4plus_anime_6B'
    enhancer.process_images()