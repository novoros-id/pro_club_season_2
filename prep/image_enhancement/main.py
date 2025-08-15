# main.py

from enhance_images import ImageEnhancer

if __name__ == '__main__':
    enhancer = ImageEnhancer(
        upload_folder='upload',
        result_folder='result',
        scale=4
    )
    enhancer.enhance_all()