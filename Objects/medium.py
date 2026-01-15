from datetime import datetime
from Objects import settings, regex
from colorama import Fore, Style
import yt_dlp


class Medium:
    def __init__(self, site, unique_id):
        self.site = site
        self.unique_id = unique_id
        self.enrich_from_db()
        self.enrich_from_json()

    def __eq__(self, other):
        if not isinstance(other, Medium):
            return NotImplemented
        else:
            same = True
            if not self.site == other.site:
                same = False
            if not self.unique_id == other.unique_id:
                same = False
            return same

    def enrich_from_db(self):
        """Enriches media details using local database"""
        pass  # TODO

    def enrich_from_json(self):
        """Enrich media object from YT-DLP JSON data"""
        json_data = self.get_json_data()
        '''Handle more difficult parts of JSON first to prevent useless processing being done'''
        # Date
        json_date = json_data['upload_date'] or json_data['release_date']
        self.available_date = datetime.strptime(json_date, '%Y%m%d').strftime('%Y-%m-%d')
        # Site
        self.site = json_data['extractor']
        # ID
        self.unique_id = json_data['id']
        # Type (video, livestream, short, ...)
        self.type = json_data['_type']  # TODO: Does this field match our concept of livestreams and shorts?

    def get_json_data(self):
        """Gets media details from site using YT-DLP"""
        info_json = None
        while info_json is None:
            try:
                if self.site == 'youtube':
                    media_url = f'https://www.youtube.com/watch?v={self.unique_id}'
                else:
                    exit()  # TODO: Handle errors more gracefully
                # Set download options for YT-DLP
                media_download_options = {
                    # TODO 'logger': VoidLogger(),
                    'skip_download': True,
                    'allow_playlist_files': False,
                    'cachedir': False,
                    'extractor_args': {'youtube': {'skip': ['configs', 'webpage', 'js']}},
                    'source_address': settings.external_ip
                }
                # Run YT-DLP
                with yt_dlp.YoutubeDL(media_download_options) as ilus:
                    info_json = ilus.sanitize_info(ilus.extract_info(media_url, process=True, download=False))
            except Exception as e:
                if regex.bot.search(str(e)):
                    print(f'{datetime.now()} {Fore.RED}BOT DETECTED{Style.RESET_ALL}')
                    # TODO: Build OOP VPN reconnect approach and use here
                    #  vpn_frequency = DEFAULT_vpn_frequency
                    #  local_vpn_counter = reconnect_vpn(counter=local_vpn_counter)
                else:
                    # print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while getting details for media "{media_id}": {e}')
                    raise
        return info_json

    def download(self):
        """Downloads media from site using YT-DLP"""
        done = False
        while not done:
            pass  # TODO: download_media


if __name__ == '__main__':
    pass  # TODO simple test case getting media details using both DB and JSON
