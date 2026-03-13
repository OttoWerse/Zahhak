from string import Template
from Objects.site import Site
from Objects.medium import Medium

youtube = Site(unique_id="youtube",
               channel_playlists_feed_url_format=Template('''https://www.youtube.com/channel/$unique_id/playlists'''),
               channel_media_feed_url_format=Template('''https://www.youtube.com/channel/$unique_id/videos'''),
               playlist_url_format=Template('''https://www.youtube.com/playlist?list=$unique_id'''),
               medium_url_format=Template('''https://www.youtube.com/watch?v=$unique_id'''),
               )

if __name__ == '__main__':
    test_medium = Medium(youtube, 'YE7VzlLtp-4')
    print(test_medium)
