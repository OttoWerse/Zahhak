class Site:
    def __init__(self, name, url):
        self.name = name
        self.url = url

    def __eq__(self, other):
        if not isinstance(other, Site):
            return NotImplemented
        else:
            same = True
            if not self.name == other.name:
                same = False
            return same
