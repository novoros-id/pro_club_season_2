from prepare_files import prepare_files
file_path = '/Users/alexeyvaganov/Documents/doc/Работа/КЛУБ РАЗРАБОТЧИКОВ/Видео конкурс.mov'

prep_file = prepare_files(file_path)
video_file = prep_file.process_file()

print(video_file)
