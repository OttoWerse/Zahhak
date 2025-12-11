class Medium:
    def __init__(self, url_site, url_id, media_type):
        self.url_site = url_site
        self.url_id = url_id
        self.type = media_type

    def __int__(self, json_data):
        self.url_site = json_data['extractor']
        self.url_id = json_data['id']
        self.type = json_data['_type']  # TODO: Does this field match our concept of livestreams and shorts?

    def __eq__(self, other):
        if not isinstance(other, Medium):
            return NotImplemented
        else:
            same = True
            if not self.url_site == other.url_site:
                same = False
            if not self.url_id == other.url_id:
                same = False
            return same
