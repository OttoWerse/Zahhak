import json
from datetime import datetime
from Objects import settings, regex
from colorama import Fore, Style
import yt_dlp
import logging

'''Logger'''
logger = logging.getLogger(__name__)


class Channel:
    def __init__(self, site, unique_id, json_data=None):
        """Initialize Channel object
        optionally including data from existing JSON data (e.g. an existing local JSON file)"""
        self.site = site
        self.unique_id = unique_id
        self.enrich_from_db()
        self.enrich_from_json(json_data=json_data)

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

    def __str__(self):
        return f'{self.site} {self.unique_id}'

    def enrich_from_db(self):
        """Enriches channel object details using local database"""
        pass  # TODO

    def enrich_from_json(self, json_data=None):
        """Enrich channel object details from YT-DLP JSON data"""
        if json_data is None:
            json_data = self.get_json_data()

        if settings.DEBUG:
            user_input = input(f'Save JSON? y/n')
            if user_input.lower() == 'y':
                with open('DEBUG.json', 'w', encoding='utf-8') as json_file:
                    # noinspection PyTypeChecker
                    json.dump(json_data, json_file, ensure_ascii=False, indent=4)

        '''Handle more difficult parts of JSON first to prevent useless processing being done'''
        # TODO

    def get_json_data(self):
        """Gets channel details from site using YT-DLP"""
        info_json = None
        while info_json is None:
            try:
                channel_url = self.site.get_channel_media_feed_url(self.unique_id)
                # Set download options for YT-DLP
                channel_download_options = {
                    # TODO 'logger': VoidLogger(),
                    'extract_flat': True,  # TODO: This was dynamic in old Zahhak for "Other" Playlists!
                    'lazy_playlist': True,
                    'skip_download': True,
                    'allow_playlist_files': False,
                    'cachedir': False,
                    'ignoreerrors': 'only_download',  # TODO: This was dynamic in old Zahhak for "Other" Playlists!
                    'extractor_args': {'youtube': {'skip': ['configs', 'webpage', 'js']}},
                    'source_address': settings.external_ip
                }
                # Run YT-DLP
                with yt_dlp.YoutubeDL(channel_download_options) as ilus:
                    info_json = ilus.sanitize_info(ilus.extract_info(channel_url, process=True, download=False))
            except Exception as e:
                if regex.bot.search(str(e)):
                    logger.error(f'{datetime.now()} {Fore.RED}BOT DETECTED{Style.RESET_ALL}')
                    # TODO: VPN reconnect
                else:
                    raise
        return info_json

    def download(self):
        """Downloads all channel media from site using YT-DLP"""
        pass  # TODO

    def check(self):
        """Checks download state of the channel"""
        pass  # TODO
