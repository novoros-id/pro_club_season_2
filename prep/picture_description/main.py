from picture_description import picture_description

video_path = '111.mp4'
video_path = '/home/ivasilishin/test/pro_club_season_2/prep/picture_description/111.mp4'
time_str = '00:01:05'

class_picture_description = picture_description()
#description_frame = class_picture_description.description_frame_at_time(video_path, time_str)
description_frame = class_picture_description.save_frame_at_time(video_path, time_str)


print(description_frame)