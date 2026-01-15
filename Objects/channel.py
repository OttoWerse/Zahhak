class Channel:
    def __init__(self, site, unique_id):
        self.site = site
        self.unique_id = unique_id

    def __eq__(self, other):
        if not isinstance(other, Channel):
            return NotImplemented
        else:
            same = True
            if not self.site == other.site:
                same = False
            if not self.unique_id == other.unique_id:
                same = False
            return same

    def process(self):
        pass  # TODO

    def download(self):
        """Downloads all channel media from site using YT-DLP"""
        pass  # TODO

    def enrich_from_db(self):
        self.name_database = None  # TODO

    def enrich_from_online(self):
        url = self.site.get_channel_media_feed_url(self.unique_id)
        self.name_online = None  # TODO


if __name__ == '__main__':
    pass  # TODO simple test case getting channel details using both DB and JSON
