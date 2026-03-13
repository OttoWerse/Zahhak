import os
from string import Template
from Objects.site import Site
from Objects.medium import Medium

'''Handle Environmental Variables'''
# File Directories
directory_download_temp = os.getenv('ZAHHAK_DIR_DOWNLOAD_TEMP')
directory_download_home = os.getenv('ZAHHAK_DIR_DOWNLOAD_HOME')
directory_final = os.getenv('ZAHHAK_DIR_FINAL')
# MySQL Connection
mysql_host = os.getenv('ZAHHAK_MYSQL_HOSTNAME', 'localhost')
mysql_database = os.getenv('ZAHHAK_MYSQL_DATABASE', 'zahhak')
mysql_user = os.getenv('ZAHHAK_MYSQL_USERNAME', 'admin')
mysql_password = os.getenv('ZAHHAK_MYSQL_PASSWORD', 'admin')

youtube = Site(unique_id="youtube",
               channel_playlists_feed_url_format=Template('''https://www.youtube.com/channel/$unique_id/playlists'''),
               channel_media_feed_url_format=Template('''https://www.youtube.com/channel/$unique_id/videos'''),
               playlist_url_format=Template('''https://www.youtube.com/playlist?list=$unique_id'''),
               medium_url_format=Template('''https://www.youtube.com/watch?v=$unique_id'''),
               )

if __name__ == '__main__':
    test_video = Medium(youtube, 'YE7VzlLtp-4')
    print(test_video.__dict__)

    test_short = Medium(youtube, 'EAGW-6PNqM4')
    print(test_short.__dict__)

    test_live = Medium(youtube, 'xMyFK-EqXeA')
    print(test_live.__dict__)
