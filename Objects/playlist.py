class Playlist:
    def __init__(self, url_site, url_id, db_name):
        self.url_site = url_site
        self.url_id = url_id
        self.db_name = db_name

    def __eq__(self, other):
        if not isinstance(other, Playlist):
            return NotImplemented
        else:
            same = True
            if not self.url_site == other.url_site:
                same = False
            if not self.url_id == other.url_id:
                same = False
            return same

    def process(self):
        pass

    def download(self):
        pass
