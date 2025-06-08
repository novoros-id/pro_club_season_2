from prepare_files import prepare_files
file_path = '/Users/alexeyvaganov/Documents/doc/Работа/КЛУБ РАЗРАБОТЧИКОВ/Инструкция по боту_720_converted.mp4'

prep_file = prepare_files(file_path)
video_file = prep_file.extract_clean_audio()

print(video_file)
