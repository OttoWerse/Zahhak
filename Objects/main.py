import os
from string import Template
from Objects.site import Site
from Objects.medium import Medium
from Objects.playlist import Playlist
from Objects.channel import Channel

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

'''Create known sites'''  # TODO: Maybe this should be in the Database too? (modularity overkill)
youtube = Site(unique_id="youtube",
               channel_playlists_feed_url_format=Template('''https://www.youtube.com/channel/$unique_id/playlists'''),
               channel_media_feed_url_format=Template('''https://www.youtube.com/channel/$unique_id/videos'''),
               playlist_url_format=Template('''https://www.youtube.com/playlist?list=$unique_id'''),
               medium_url_format=Template('''https://www.youtube.com/watch?v=$unique_id'''),
               )

if __name__ == '__main__':
    '''Test Channel objects'''
    print('Test Channel objects')
    # Regular channel
    test_channel = Channel(site=youtube, unique_id='UCuN6CiunobgtFGyW-upi0Dw')
    print(test_channel.__dict__)

    '''Test Playlist objects'''
    print('Test Playlist objects')
    # Regular playlist
    test_playlist = Playlist(site=youtube, unique_id='PLjMeeZO2frknrGpqUkFxrdasFQrC-8mbq')
    print(test_playlist.__dict__)
    # Channel Uploads playlist
    # TODO: test_channel_uploads_playlist = Playlist(site=youtube, unique_id='')

    '''Test Media objects'''
    print('Test Media objects')
    # Test a regular video
    test_video = Medium(site=youtube, unique_id='YE7VzlLtp-4')
    print(test_video.__dict__)
    # Test a short
    test_short = Medium(site=youtube, unique_id='EAGW-6PNqM4')
    print(test_short.__dict__)
    # Test a 24/7 livestream
    test_live = Medium(site=youtube, unique_id='xMyFK-EqXeA')
    print(test_live.__dict__)
