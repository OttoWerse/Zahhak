from string import Template


class Site:
    def __init__(self, unique_id, channel_playlists_feed_url_format, channel_media_feed_url_format, playlist_url_format,
                 medium_url_format):
        self.unique_id: str = unique_id
        self.channel_playlists_feed_url_format: Template = channel_playlists_feed_url_format
        self.channel_media_feed_url_format: Template = channel_media_feed_url_format
        self.playlist_url_format: Template = playlist_url_format
        self.medium_url_format: Template = medium_url_format

    def __eq__(self, other):
        if not isinstance(other, Site):
            return NotImplemented
        else:
            same = True
            if not self.unique_id == other.unique_id:
                same = False
            return same

    def get_channel_playlists_feed_url(self, channel_id):
        return self.channel_playlists_feed_url_format.substitute(unique_id=channel_id)

    def get_channel_media_feed_url(self, channel_id):
        return self.channel_media_feed_url_format.substitute(unique_id=channel_id)

    def get_playlist_url(self, playlist_id):
        return self.playlist_url_format.substitute(unique_id=playlist_id)

    def get_media_url(self, media_id):
        return self.medium_url_format.substitute(unique_id=media_id)


if __name__ == '__main__':
    youtube = Site(unique_id="youtube",
                   channel_playlists_feed_url_format=Template(
                       '''https://www.youtube.com/channel/$unique_id/playlists'''),
                   channel_media_feed_url_format=Template('''https://www.youtube.com/channel/$unique_id/videos'''),
                   playlist_url_format=Template('''https://www.youtube.com/playlist?list=$unique_id'''),
                   medium_url_format=Template('''https://www.youtube.com/watch?v=$unique_id'''),
                   )
    print(youtube.get_channel_playlists_feed_url(channel_id="THIS_IS_A_TEST_CHANNEL_ID"))
    print(youtube.get_channel_media_feed_url(channel_id="THIS_IS_A_TEST_CHANNEL_ID"))
    print(youtube.get_playlist_url(playlist_id="THIS_IS_A_TEST_PLAYLIST_ID"))
    print(youtube.get_media_url(media_id="THIS_IS_A_TEST_MEDIUM_ID"))
