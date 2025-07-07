from download_audio_video import DownloadAudioVideo

if __name__ == "__main__":
    downloader = DownloadAudioVideo()
    video_link = "https://pro-1c-virtualnas.direct.quickconnect.to:5001/?launchApp=SYNO.SDS.VideoPlayer2.Application&SynoToken=tJMAmbEUENj7k&launchParam=url%3Dwebapi%252Fentry.cgi%253Fapi%253DSYNO.SynologyDrive.Files%2526method%253Ddownload%2526version%253D2%2526files%253D%25255B%252522id%25253A894137597446631564%252522%25255D%2526force_download%253Dtrue%2526is_preview%253Dtrue%2526download_serial%253D%252522%25255C%252522jqABPQDuHK%25255C%252522%252522%2526SynoToken%253DtJMAmbEUENj7k%26filename%3DCleanShot%25202025-07-05%2520at%252019.46.37.mp4"
    downloader.download_video_directly(video_link)