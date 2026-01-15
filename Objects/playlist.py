class Playlist:
    def __init__(self, url_site, unique_id):
        self.site = url_site
        self.unique_id = unique_id

    def __eq__(self, other):
        if not isinstance(other, Playlist):
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
        """Downloads all playlist media from site using YT-DLP"""
        pass  # TODO

    def enrich_from_db(self):
        self.name_database = None  # TODO

    def enrich_from_online(self):
        url = self.site.get_playlist_url(self.unique_id)
        self.name_online = None  # TODO


if __name__ == '__main__':
    pass  # TODO simple test case getting video details using both DB and JSON
