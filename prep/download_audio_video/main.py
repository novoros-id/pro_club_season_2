from download_audio_video import DownloadAudioVideo

if __name__ == "__main__":
    downloader = DownloadAudioVideo()

    # Пример прямой ссылки на видео или аудио файл
    video_url = "https://pro-1c-virtualnas.direct.quickconnect.to:5001/d/s/1439ton5ovD5Q4NEyxy7LrtQeKzA71Jr/webapi/entry.cgi/CleanShot%202025-07-05%20at%2019.46.37.mp4?api=SYNO.SynologyDrive.Files&method=download&version=2&files=%5B%22id%3A894137597446631564%22%5D&force_download=false&download_type=%22download%22&sharing_token=%22XHuN2WWgZhy1p.Z2q_HtOpeD4SN._9_90jrKrQm6BMPDKpJX0iIuXh2bkCIInjSiPczh0WEnOXJkPjNChOhht5cjYvsOS7QBNXmxup5w23tSLn.p83Y8Y4Ms2zslb0qcNTz9gALCgDWOX3fGLTNR7LwxvScQHJKhwNvVc5eoEzkG05fUY_OVMexWLsWt0LEzX0.oNsnPGHbZgC5qicRknDE51_h_LdFVl7yEHpQyMeeRr5NjlBKEVj5S%22&_dc=1751873125539"  # замените на вашу реальную прямую ссылку

    downloader.smart_download(video_url)