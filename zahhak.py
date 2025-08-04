import argparse
import json
import os
import random
import re
import shutil
import sys
import time
from datetime import datetime
from subprocess import STDOUT, check_output

import mysql.connector
import yt_dlp
from colorama import init, Fore, Style, just_fix_windows_console

# TODO https://www.reddit.com/r/youtubedl/comments/1berg2g/is_repeatedly_downloading_api_json_necessary/

'''Download directory settings'''
directory_download_temp = os.getenv('ZAHHAK_DIR_DOWNLOAD_TEMP')  # TODO: Default?
directory_download_home = os.getenv('ZAHHAK_DIR_DOWNLOAD_HOME')  # TODO: Default?
if directory_download_temp is None or directory_download_home is None:
    print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} Directories not defined!', end="\n")
    sys.exit()

'''MySQL settings'''
mysql_host = os.getenv('ZAHHAK_MYSQL_HOSTNAME', 'localhost')
mysql_database = os.getenv('ZAHHAK_MYSQL_DATABASE', 'zahhak')
mysql_user = os.getenv('ZAHHAK_MYSQL_USERNAME', 'admin')
mysql_password = os.getenv('ZAHHAK_MYSQL_PASSWORD', 'admin')

'''Variables'''
# Enable or disable VPN reconnect functionality
enable_vpn = True
# Frequency to reconnect VPN (in seconds)
sleep_time_vpn = 10
# How often to retry connecting to a VPN country before giving up
retry_reconnect_new_vpn_node = 5
# Frequency to check if switch from downloading secondary to primary videos is needed (in seconds)
switch_to_primary_frequency = 120

# Countries to connect to with NordVPN
DEFAULT_vpn_countries = [
    'Austria',
    'Belgium',
    'Bulgaria',
    'Cyprus',
    'Czech Republic',
    'Denmark',
    'Estonia',
    'Finland',
    'France',
    'Georgia',
    'Germany',
    'Greece',
    'Hungary',
    'Iceland',
    'Ireland',
    'Italy',
    'Latvia',
    'Lithuania',
    'Luxembourg',
    # 'Moldova',
    'Netherlands',
    'North Macedonia',
    'Norway',
    'Poland',
    'Portugal',
    'Romania',
    'Serbia',
    'Slovakia',
    'Slovenia',
    'Spain',
    'Sweden',
    'Switzerland',
    'Ukraine',
    'United Kingdom',
]

GEO_BLOCKED_vpn_countries = []

# Timeout connecting VPN
timeout_vpn = 15

# Timeout for channel home page extraction (in seconds)
timeout_check_channel = 6
# YT-DLP internal retry for channel home page extraction
retry_extraction_check_channel = 0

# Timeout for loading channel video page extraction (in seconds)
timeout_channel = 48
# YT-DLP internal retry for channel video page extraction
retry_extraction_channel = 2
# Times to try channel processing before reconnecting NordVPN (if enabled) - this repeats every X tries!
retry_channel_before_reconnecting_vpn = 1
# Times to try full channel video page processing before switching to using ignore_errors to accept partial processing
retry_channel_before_ignoring_errors = len(DEFAULT_vpn_countries) * 1 * retry_channel_before_reconnecting_vpn
# Times to try channel video page processing before giving up entirely
retry_channel_before_giving_up = len(DEFAULT_vpn_countries) * 2 * retry_channel_before_reconnecting_vpn  #

# Timeout for channel video page extraction (in seconds)
timeout_playlist = 24
# YT-DLP internal retry for full playlist page extraction
retry_extraction_playlist = 2
# Times to try playlist page processing before reconnecting NordVPN (if enabled) - this repeats every X tries!
retry_playlist_before_reconnecting_vpn = 1
# Times to try full playlist page processing before switching to using ignore_errors to accept partial processing
retry_playlist_before_ignoring_errors = len(DEFAULT_vpn_countries) * 1 * retry_playlist_before_reconnecting_vpn
# Times to try playlist page processing before giving up entirely
retry_playlist_before_giving_up = len(DEFAULT_vpn_countries) * 2 * retry_playlist_before_reconnecting_vpn  #

# Timeout for video page extraction (in seconds)
timeout_video = 12
# YT-DLP internal retry for video page extraction
retry_extraction_video = 2
# Times to try video page processing before giving up entirely
retry_process_video = 2

# Timeout for video download (in seconds)
timeout_download = 12
# YT-DLP internal retry for video download
retry_extraction_download = 2

# Sleep time after failed MySQL requests (in seconds)
sleep_time_mysql = 3

# Sleep time when there is no more videos to download (in seconds)
sleep_time_download_done = 300

# Use 0.0.0.0 to force IPv4
external_ip = '0.0.0.0'

# Only log warnings from yt-dlp and wrapper messages from Ilus
quiet_check_channel_info = True
quiet_check_channel_warnings = True
quiet_channel_info = True
quiet_channel_warnings = True
quiet_playlist_info = True
quiet_playlist_warnings = True
quiet_download_info = True
quiet_download_warnings = True

# Extract FLAT
# TODO: Combined with ignore Errors != False sometimes only loads first page?!?!?!
#  Bug is old, but certainly back: https://github.com/ytdl-org/youtube-dl/issues/28075
extract_flat_channel = True  # Can be True for faster processing IF ignore_errors is False and NOT 'only_download'! (causes frequent incomplete checks of channel state, which can prevent playlist checking from happening!)
extract_flat_playlist = True  # TODO: just reconnect_vpn upon bot detection - Previous comment: Leave as False to avoid extraction of every single video AFTER playlist (often detected as bot!)

# Availability Filter
# filter_availability = 'availability=public,unlisted,needs_auth,subscriber_only,premium_only'
filter_availability = 'availability=public,unlisted '
# TODO: Neither of these filters work for actually filtering shorts on the playlist/channel level!
# filter_shorts = '& tags !*= shorts & original_url!=/shorts/ & url!=/shorts/ '
filter_shorts = '& media_type != short '
filter_livestream_current = '& !is_live '
filter_livestream_recording = '& !was_live '

# Set ignore error options
# TODO: Look into what happens if you use False, catch an error like "Private Video" and then do nothing with it. e.g. will yt-dlp continue on
# TODO: Maybe revert to ignoring errors on channel pages for faster runs? (channels will be checked frequently, and new videos should always be on 1st page. Eventually we will get a full list, given enough reruns)
# False --> Getting full list of videos ends when one will not load, is private, is age restricted, etc. we get NO list of videos at all! (IDK is this can be made to work so private videos etc. are filtered out using filter, we need to TEST this!)
DEFAULT_ignore_errors_channel = False
DEFAULT_ignore_errors_playlist = False
# 'only_download' --> We do not always get a full list of videos, but at least we get A list at all!
# DEFAULT_ignore_errors_channel           = 'only_download'
# DEFAULT_ignore_errors_playlist          = 'only_download'

'''Media Types'''
download_shorts = False
download_livestreams = False

'''STRINGS'''
playlist_name_shorts = 'Shorts'
playlist_name_livestreams = 'Livestreams'

'''REGEX'''
# Channel names
regex_live_channel = re.compile(r'.* LIVE$')
regex_fake_channel = re.compile(r'^#.*$')
regex_fake_playlist = re.compile(r'^#.*$')
regex_handle_as_id = re.compile(r'^@.*$')

# YT-DLP Error messages
regex_channel_no_videos = re.compile(r'This channel does not have a videos tab')
regex_channel_no_playlists = re.compile(r'This channel does not have a playlists tab')
regex_channel_unavailable = re.compile(r'This channel is not available')
regex_channel_removed = re.compile(r'This channel was removed because it violated our Community Guidelines')
regex_channel_deleted = re.compile(r'This channel does not exist')
regex_offline = re.compile(r"Offline")
regex_playlist_deleted = re.compile(r'The playlist does not exist')
regex_video_age_restricted = re.compile(r'Sign in to confirm your age')
regex_video_private = re.compile(r'Private video')
regex_video_unavailable = re.compile(r'Video unavailable')
regex_video_unavailable_live = re.compile(r'This live stream recording is not available')
regex_video_unavailable_geo = re.compile(r'The uploader has not made this video available in your country')
regex_video_unavailable_geo_fix = re.compile(r'(?<=This video is available in ).*(?<!\.)')
regex_video_removed = re.compile(r'This video has been removed')
regex_video_members_only = re.compile(r'Join this channel to get access to members-only content like this video, '
                                      r'and other exclusive perks')
regex_video_members_tier = re.compile(r'This video is available to this channel')
regex_video_live_not_started = re.compile(r'This live event will begin in a few moments')
regex_error_connection = re.compile(r'Remote end closed connection without response')
regex_error_timeout = re.compile(r'The read operation timed out')
regex_error_get_addr_info = re.compile(r'getaddrinfo failed')
regex_error_win_10054 = re.compile(r'WinError 10054')
regex_error_win_2 = re.compile(r'WinError 2')
regex_bot = re.compile(r"Sign in to confirm you're not a bot")
regex_sql_duplicate = re.compile(r'Duplicate entry')

# noinspection RegExpRedundantEscape
regex_val = re.compile(r'[^\.a-zA-Z0-9 -]')
regex_caps = re.compile(r'[A-Z][A-Z]+')

'''Status values'''
STATUS_UNWANTED = 'unwanted'
STATUS_WANTED = 'wanted'
STATUS_MEMBERS_ONLY = 'members-only'
STATUS_AGE_RESTRICTED = 'age-restricted'
STATUS_UNAVAILABLE = 'unavailable'
STATUS_PRIVATE = 'private'
STATUS_REMOVED = 'removed'
STATUS_VERIFIED = 'verified'
STATUS_UNCERTAIN = 'uncertain'
STATUS_BROKEN = 'broken'
STATUS_BROKEN_UNAVAILABLE = 'broken-unavailable'
STATUS_CURSED = 'cursed'
STATUS_DONE = 'done'

'''DEBUG'''
DEBUG_empty_video = False
DEBUG_add_video = False
DEBUG_force_date = False
DEBUG_log_date_fields_missing = False
DEBUG_unavailable = False
DEBUG_update_channel = False
DEBUG_update_playlist = False
DEBUG_json_channel = False
DEBUG_json_check_channel = False
DEBUG_json_playlist = False
DEBUG_json_video_add = False
DEBUG_json_video_details = False
DEBUG_error_connection = False
DEBUG_add_unmonitored = False
DEBUG_channel_id = False
DEBUG_channel_playlists = False

'''INIT'''
# Path to use for download archive, best leave at default
global_archive_set = set()
# VPN changer
vpn_counter = 0
vpn_timestamp = datetime.now()
DEFAULT_vpn_frequency = 60  # TODO: recheck if can be reached continuously until timeout is reached instead of just waiting. Possibly split this into two values, one for the new and one for the old functionality. Plus also wait time before even trying to get video after trying to reconnect vpn!
GEO_BLOCKED_vpn_frequency = 30
vpn_frequency = DEFAULT_vpn_frequency


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


class Channel:
    def __init__(self, url_site, url_id, db_name):
        self.url_site = url_site
        self.url_id = url_id
        self.db_name = db_name

    def __eq__(self, other):
        if not isinstance(other, Channel):
            return NotImplemented
        else:
            same = True
            if not self.url_site == other.url_site:
                same = False
            if not self.url_id == other.url_id:
                same = False
            return same


class MediaItem:
    def __init__(self, url_site, url_id, media_type):
        self.url_site = url_site
        self.url_id = url_id
        self.media_type = media_type

    def __eq__(self, other):
        if not isinstance(other, MediaItem):
            return NotImplemented
        else:
            same = True
            if not self.url_site == other.url_site:
                same = False
            if not self.url_id == other.url_id:
                same = False
            return same


# TODO: Look into using logger, progress_hooks, progress (https://github.com/yt-dlp/yt-dlp/issues/66) effectively!
class VoidLogger:
    def debug(self, msg):
        pass

    def info(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


def connect_database():
    """Connects to mysql Database using provided parameters"""
    mydb = mysql.connector.connect(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database
    )
    return mydb


def create_download_archive():
    """Uses MySQL database to build a list of all known video IDs and writes them to YT-DLP archive file"""
    result_archive = []
    while not result_archive:
        try:
            print(f'{datetime.now()} {Fore.CYAN}CREATING{Style.RESET_ALL} download archive from DB',
                  end="\r")

            mydb = connect_database()
            mysql_cursor = mydb.cursor()
            sql = "SELECT videos.site AS 'site', videos.url AS 'url' FROM videos;"
            mysql_cursor.execute(sql)

            result_archive = mysql_cursor.fetchall()
            result_archive_length = len(result_archive)

            counter_archive = 0
            for x in result_archive:
                counter_archive += 1
                if counter_archive % 100 == 0 or counter_archive == result_archive_length:
                    print(f'{datetime.now()} {Fore.CYAN}CREATING{Style.RESET_ALL} download archive from DB '
                          f'({counter_archive}/{len(result_archive)})',
                          end="\r")
                site = x[0]
                url = x[1]
                global_archive_set.add(f'{site} {url}')

            print('', end="\n")

        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_download_archive:
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while creating download archive: '
                  f'{exception_download_archive}')
            time.sleep(sleep_time_mysql)


def update_channel(date, channel, database):
    """Updates last checked date for channel"""

    channel_site = channel[0]
    channel_id = channel[1]
    channel_name = channel[2]

    print(f'{datetime.now()} {Fore.CYAN}MARKING{Style.RESET_ALL} channel '
          f'"{channel_site} {channel_id}" as checked', end='\r')

    # Update DB
    try:
        mydb = database
        mysql_cursor = mydb.cursor()

        sql = "UPDATE channels SET date_checked = %s WHERE site = %s AND url = %s;"
        val = (date, channel_site, channel_id)

        if DEBUG_update_channel:
            input(val)

        mysql_cursor.execute(sql, val)
        mydb.commit()

        print(f'{datetime.now()} {Fore.CYAN}MARKED{Style.RESET_ALL} channel '
              f'"{channel_site} {channel_id}" as checked ', end='\n')
        return True

    except KeyboardInterrupt:
        sys.exit()

    except Exception as exception_update_channel:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while marking channel '
              f'"{channel_name}" ({channel_site} {channel_id}): {exception_update_channel}')
        return False


def update_playlist(date, playlist, database):
    """Updates last checked date for playlist"""

    playlist_site = playlist[0]
    playlist_id = playlist[1]
    playlist_name = playlist[2]

    print(f'{datetime.now()} {Fore.CYAN}MARKING{Style.RESET_ALL} playlist '
          f'"{playlist_name}" ({playlist_site} {playlist_id}) as checked', end='\r')

    # Update DB
    try:
        mysql_cursor = database.cursor()

        sql = "UPDATE playlists SET date_checked = %s WHERE site = %s AND url = %s;"
        val = (date, playlist_site, playlist_id)

        if DEBUG_update_playlist:
            input(val)

        mysql_cursor.execute(sql, val)
        database.commit()

        print(f'{datetime.now()} {Fore.CYAN}MARKED{Style.RESET_ALL} playlist '
              f'"{playlist_name}" ({playlist_site} {playlist_id}) as checked ', end='\n')
        return True

    except KeyboardInterrupt:
        sys.exit()

    except Exception as exception_update_playlist:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while marking playlist '
              f'"{playlist_site} {playlist_id}": {exception_update_playlist}')
        return False


def check_channel_availability(channel):
    """Checks if channel is even reachable from current VPN node"""
    global vpn_frequency

    try:
        channel_site = channel[0]
        channel_id = channel[1]
        channel_name = channel[2]
        print(f'{datetime.now()} Checking availability of channel "{channel_name}" ({channel_site} {channel_id})',
              end='\r')

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_missing_videos_channel:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while getting fields from channel '
              f'"{channel}": {exception_missing_videos_channel}')
        return False

    if regex_fake_channel.search(channel_id):
        print(f'{datetime.now()} {Fore.YELLOW}WARNING{Style.RESET_ALL}: Channel '
              f'"{channel_name}" ({channel_site} {channel_id}) is not a real channel')
        return True

    # Set channel URL
    channel_url = f'https://www.youtube.com/channel/{channel_id}/videos'

    # Ignoring errors here would be unwise, I think...
    ignore_errors = False

    # Set download options for YT-DLP
    channel_download_options = {
        'logger': VoidLogger(),
        'playlist_items': '0',
        'skip_download': True,
        'allow_playlist_files': False,
        'quiet': quiet_check_channel_info,
        'no_warnings': quiet_check_channel_warnings,
        'cachedir': False,
        'ignoreerrors': ignore_errors,
        'ignore_no_formats_error': True,  # Keep "True" https://github.com/yt-dlp/yt-dlp/issues/9810
        'extractor_args': {'youtube': {'skip': ['configs', 'webpage', 'js']}},
        'extractor_retries': retry_extraction_check_channel,
        'socket_timeout': timeout_check_channel,
        'source_address': external_ip,
    }

    try:
        info_json = None
        # Run YT-DLP
        with yt_dlp.YoutubeDL(channel_download_options) as ilus:
            info_json = ilus.sanitize_info(ilus.extract_info(channel_url, process=True, download=False))

    except KeyboardInterrupt:
        # DEBUG: Skip problematic channels
        # return False
        sys.exit()
    except Exception as exception_missing_videos_channel:
        if regex_channel_no_videos.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}EMPTY{Style.RESET_ALL} channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            # TODO: return special case?
            return True
        elif regex_error_connection.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}CLOSED CONNECTION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        elif regex_error_timeout.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}TIME OUT{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        elif regex_error_get_addr_info.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}GET ADDR INFO FAILED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        elif regex_error_win_10054.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}CONNECTION CLOSED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        elif regex_channel_unavailable.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}GEO BLOCKED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = GEO_BLOCKED_vpn_frequency
            return False
        elif regex_channel_removed.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}GUIDELINE VIOLATION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        elif regex_channel_deleted.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}NONEXISTENT{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        else:
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id}): {exception_missing_videos_channel}')
            if DEBUG_error_connection:
                input(r'continue?')
            return False

    if DEBUG_json_check_channel:
        with open('DEBUG_check_channel.json', 'w', encoding='utf-8') as json_file:
            # noinspection PyTypeChecker
            json.dump(info_json, json_file, ensure_ascii=False, indent=4)
        input(f'Dumped JSON... Continue?')

    if info_json is not None:
        print(f'{datetime.now()} {Fore.GREEN}AVAILABLE{Style.RESET_ALL} channel '
              f'"{channel_name}" ({channel_site} {channel_id})')
        return True
    else:
        print(f'{datetime.now()} {Fore.RED}UNAVAILABLE{Style.RESET_ALL} channel '
              f'"{channel_name}" ({channel_site} {channel_id})')
        return False


def get_new_channel_videos_from_youtube(channel, ignore_errors, archive_set):
    """Returns video IDs not present in MySQL database for given channel"""
    global vpn_frequency

    try:
        channel_site = channel[0]
        channel_id = channel[1]
        channel_name = channel[2]
        print(f'{datetime.now()} Checking download state of channel "{channel_name}" ({channel_site} {channel_id})',
              end='\r')

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_missing_videos_channel:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while getting fields from channel '
              f'"{channel}": {exception_missing_videos_channel}')
        return None

    if regex_fake_channel.search(channel_id):
        print(f'{datetime.now()} {Fore.YELLOW}WARNING{Style.RESET_ALL}: Channel '
              f'"{channel_name}" ({channel_site} {channel_id}) is not a real channel')
        # TODO: Update checked date? Return number etc. and in this case, return special case?
        return ['FAKE']

    # Filter out members only content on the channel level
    filter_text = filter_availability

    # Set channel URL
    # channel_url = f'https://www.youtube.com/channel/{channel_id}/videos'
    # TODO: This will lead to shorts being added regardless of filter!
    upload_playlist = re.sub('^UC', 'UU', channel_id)
    channel_url = f'https://www.youtube.com/playlist?list={upload_playlist}'

    # Set download options for YT-DLP
    channel_download_options = {
        'logger': VoidLogger(),
        'extract_flat': extract_flat_channel,
        'skip_download': True,
        'allow_playlist_files': False,
        'lazy_playlist': True,
        'quiet': quiet_channel_info,
        'no_warnings': quiet_channel_warnings,
        'cachedir': False,
        'ignoreerrors': ignore_errors,
        'ignore_no_formats_error': True,  # Keep "True" https://github.com/yt-dlp/yt-dlp/issues/9810
        'download_archive': archive_set,
        'extractor_args': {'youtube': {'skip': ['configs', 'webpage', 'js']}},
        'extractor_retries': retry_extraction_channel,
        'socket_timeout': timeout_channel,
        'source_address': external_ip,
        'match_filter': yt_dlp.utils.match_filter_func(filter_text)
    }

    try:
        info_json = None
        # Run YT-DLP
        with yt_dlp.YoutubeDL(channel_download_options) as ilus:
            info_json = ilus.sanitize_info(ilus.extract_info(channel_url, process=True, download=False))

    except KeyboardInterrupt:
        # DEBUG: Skip problematic channels
        # return False
        sys.exit()
    except Exception as exception_missing_videos_channel:
        if regex_channel_no_videos.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}EMPTY{Style.RESET_ALL} channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            # TODO: Update checked date? Return number etc. and in this case, return special case?
            return []
        elif regex_playlist_deleted.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}EMPTY{Style.RESET_ALL}'
                  f' channel "{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return []
        elif regex_error_connection.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}CLOSED CONNECTION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        elif regex_error_timeout.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}TIME OUT{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        elif regex_error_get_addr_info.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}GET ADDR INFO FAILED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        elif regex_error_win_10054.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}CONNECTION CLOSED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        elif regex_channel_unavailable.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}GEO BLOCKED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = GEO_BLOCKED_vpn_frequency
            return None
        elif regex_channel_removed.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}GUIDELINE VIOLATION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        elif regex_channel_deleted.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}NONEXISTENT{Style.RESET_ALL} '
                  f'channel "{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        else:
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id}): {exception_missing_videos_channel}')
            if DEBUG_error_connection:
                input(r'continue?')
            return False

    if DEBUG_json_channel:
        with open('debug.json', 'w', encoding='utf-8') as json_file:
            # noinspection PyTypeChecker
            json.dump(info_json, json_file, ensure_ascii=False, indent=4)
        input(f'Dumped JSON... Continue?')

    try:
        if info_json is not None:
            videos = info_json['entries']
            if type(videos) == list:
                if videos == [None]:
                    videos = []
            video_count = len(videos)
            if video_count > 0:
                print(f'{datetime.now()} {Fore.GREEN}FOUND{Style.RESET_ALL} {video_count} new videos for channel '
                      f'"{channel_name}" ({channel_site} {channel_id})       ')
            else:
                print(f'{datetime.now()} {Fore.CYAN}NO{Style.RESET_ALL} new videos for channel '
                      f'"{channel_name}" ({channel_site} {channel_id})')

            return videos
        else:
            # TODO: IDK if channel handling in main can handle this, so I am just sending None as in other error cases
            # return False
            return None

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_missing_videos_channel:
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} no entries in "{info_json}" '
              f'({exception_missing_videos_channel})')
        return None


def get_new_playlist_videos_from_youtube(playlist, ignore_errors, counter, archive_set):
    """Returns list of missing videos as objects in given playlist"""

    playlist_site = playlist[0]
    playlist_id = playlist[1]
    playlist_name = playlist[2]
    playlist_priority = playlist[3]
    channel_id = playlist[4]
    channel_name = playlist[5]
    channel_priority = playlist[6]
    playlist_download = playlist[7]

    # owned by channel "{channel_name}" ({playlist_site} {channel_id})
    print(f'{datetime.now()} Checking download state of playlist "{playlist_name}" ({playlist_site} {playlist_id})',
          end='\r')

    # Set Live/Short filter according to channel and playlist title
    if playlist_name == playlist_name_livestreams or regex_live_channel.search(channel_name):
        print(f'{datetime.now()} {Fore.CYAN}LIVE{Style.RESET_ALL} playlist '
              f'"{playlist_name}" ({playlist_site} {playlist_id})')
        # TODO: get this info into add_video method?
        filter_text = (filter_availability + filter_livestream_current + filter_shorts)
    elif playlist_name == playlist_name_shorts:
        print(f'{datetime.now()} {Fore.CYAN}SHORTS{Style.RESET_ALL} playlist '
              f'"{playlist_name}" ({playlist_site} {playlist_id})')
        # TODO: get this info into add_video method?
        filter_text = (filter_availability + filter_livestream_current + filter_livestream_recording)
    else:
        filter_text = (filter_availability + filter_livestream_current + filter_livestream_recording + filter_shorts)

    # Set playlist URL
    # User Channel
    if re.search("^UC.*$", playlist_id):
        # Standard format for YouTube channel IDs (e.g. all videos "playlist")
        # playlist_url = f'https://www.youtube.com/channel/{playlist_id}/videos'
        # TODO: This leads to shorts being added regardless of filter!
        upload_playlist = re.sub('^UC', 'UU', channel_id)
        playlist_url = f'https://www.youtube.com/playlist?list={upload_playlist}'
        timeout = timeout_channel
        extract_flat = extract_flat_channel

        if counter > 3:
            # TODO: This needs to be aware of outer counter and only happen once variable retry_full_channel_before_ignoring_errors is reached (in next version maybe)
            ignore_errors = 'only_download'
    # Play List
    elif re.search("^PL.*$", playlist_id):
        # Standard format for YouTube playlist IDs
        playlist_url = f'https://www.youtube.com/playlist?list={playlist_id}'
        timeout = timeout_playlist
        extract_flat = extract_flat_playlist

    # Skip fake playlists created for shorts and livestreams
    elif regex_fake_playlist.search(playlist_id):
        print(f'{datetime.now()} {Fore.YELLOW}SKIPPING{Style.RESET_ALL} playlist "{playlist_id}" ({playlist_id})')
        return []  # Return empty list to not trigger continuous retry on playlists with unknown format

    else:
        # ID format unknown
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL}: Unknown ID format '
              f'"{playlist_name}" ({playlist_site} {playlist_id})')
        return []  # Return empty list to not trigger continuous retry on playlists with unknown format

    # Set download options for YT-DLP
    playlist_download_options = {
        'logger': VoidLogger(),
        'extract_flat': extract_flat,
        'skip_download': True,
        'allow_playlist_files': False,
        'lazy_playlist': True,
        'quiet': quiet_playlist_info,
        'no_warnings': quiet_playlist_warnings,
        'cachedir': False,
        'ignoreerrors': ignore_errors,
        'ignore_no_formats_error': True,  # Keep "True" https://github.com/yt-dlp/yt-dlp/issues/9810
        'download_archive': archive_set,
        'extractor_args': {'youtube': {'skip': ['configs', 'webpage', 'js']}},
        'extractor_retries': retry_extraction_playlist,
        'socket_timeout': timeout,
        'source_address': external_ip,
        'match_filter': yt_dlp.utils.match_filter_func(filter_text)
    }

    # Try-Except Block to handle YT-DLP exceptions such as "playlist does not exist"
    try:
        info_json = None
        # Run YT-DLP
        with yt_dlp.YoutubeDL(playlist_download_options) as ilus:
            info_json = ilus.sanitize_info(ilus.extract_info(playlist_url, process=True, download=False))

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_missing_videos_playlist:
        if regex_playlist_deleted.search(str(exception_missing_videos_playlist)):
            print(f'{datetime.now()} {Fore.RED}DELETED{Style.RESET_ALL} playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id})')
            # TODO: Return number etc. and in this case, return special case?
            return []
        elif regex_error_connection.search(str(exception_missing_videos_playlist)):
            print(f'{datetime.now()} {Fore.RED}CLOSED CONNECTION{Style.RESET_ALL} while adding playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id})')
            return None
        elif regex_error_timeout.search(str(exception_missing_videos_playlist)):
            print(f'{datetime.now()} {Fore.RED}TIME OUT{Style.RESET_ALL} while adding playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id})')
            return None
        elif regex_error_get_addr_info.search(str(exception_missing_videos_playlist)):
            print(f'{datetime.now()} {Fore.RED}GET ADDR INFO FAILED{Style.RESET_ALL} while adding playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id})')
            return None
        elif regex_error_win_10054.search(str(exception_missing_videos_playlist)):
            print(f'{datetime.now()} {Fore.RED}CONNECTION CLOSED{Style.RESET_ALL} while adding playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id})')
            return None
        else:
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id}): {exception_missing_videos_playlist}')
            if DEBUG_error_connection:
                input(r'continue?')
            return False

    if DEBUG_json_playlist:
        with open('debug.json', 'w', encoding='utf-8') as json_file:
            # noinspection PyTypeChecker
            json.dump(info_json, json_file, ensure_ascii=False, indent=4)
        input(f'Dumped JSON... Continue?')

    try:
        if info_json is not None:
            videos = info_json['entries']
            if type(videos) == list:
                if videos == [None]:
                    videos = []
            video_count = len(videos)
            if video_count > 0:
                print(f'{datetime.now()} {Fore.GREEN}FOUND{Style.RESET_ALL} {video_count} new videos for playlist '
                      f'"{playlist_name}" ({playlist_site} {playlist_id})')
            else:
                print(f'{datetime.now()} {Fore.CYAN}NO{Style.RESET_ALL} new videos for playlist '
                      f'"{playlist_name}" ({playlist_site} {playlist_id})')

            return videos
        else:
            # TODO: IDK if playlist handling in main can handle this, so I am just sending None as in other error cases
            # return False
            return None

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_missing_videos_playlist:
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} no entries in "{info_json}" '
              f'({exception_missing_videos_playlist})')
        # TODO: Return false for now to stop retry. In case of exception in YT-DLP we still return None. Ignore Errors "Only Download" could cause issues here!
        return False
        # TODO: To make this work properly, we need to count retries and give up at some point, I guess?
        # return [] # This is to stop repeating to try in this (rare) case of not getting entries for playlist EVER (cause unknown, possibly related to single video lists or hidden videos etc.)


def get_monitored_channels_from_db():
    """Returns a list of all known YouTube channels als list of lists
    Inner list field order is as follows:
      - channels.site
      - channels.url
      - channels.name
      - channels.priority"""

    print(f'{datetime.now()} Collecting channels...', end='\r')

    mydb = connect_database()

    mysql_cursor = mydb.cursor()

    sql = ("SELECT channels.site, channels.url, channels.name, channels.priority "
           "FROM channels "
           "WHERE site = %s "
           "AND channels.url IN("
           "SELECT playlists.channel FROM playlists "
           "WHERE playlists.done IS NOT TRUE "
           # "AND playlists.download IS TRUE "
           "AND playlists.monitor IS TRUE "
           "GROUP BY playlists.channel HAVING count(*) > 0) "
           "ORDER BY channels.priority DESC, EXTRACT(year FROM channels.date_checked) ASC, "
           "EXTRACT(month FROM channels.date_checked) ASC, EXTRACT(day FROM channels.date_checked) ASC, "
           "EXTRACT(hour FROM channels.date_checked) ASC, RAND();")
    val = ('youtube',)  # DO NOT REMOVE COMMA, it is necessary for MySQL to work!
    mysql_cursor.execute(sql, val)
    mysql_result = mysql_cursor.fetchall()
    return mysql_result


def get_channel_playlists_from_db(channel):
    """Returns all playlists for the given channel als list of lists

    Inner list field order is as follows:
      - playlists.site
      - playlists.url
      - playlists.name
      - playlists.priority
      - channels.url
      - channels.name
      - channels.priority
      - playlists.download"""

    channel_site = channel[0]
    channel_id = channel[1]
    channel_name = channel[2]

    playlists = []
    retry_db = True
    while retry_db:
        print(f'{datetime.now()} Collecting playlists for "{channel_name}" ({channel_site} {channel_id})', end='\r')
        mydb = connect_database()

        mysql_cursor = mydb.cursor()

        playlists = []

        # Get playlists with no videos in them
        sql = ("SELECT playlists.site, playlists.url, playlists.name, playlists.priority, "
               "channels.url, channels.name, channels.priority, playlists.download "
               "FROM playlists "
               "INNER JOIN channels on playlists.channel=channels.url "
               "WHERE playlists.site = %s "
               "AND playlists.channel = %s "
               "AND playlists.done IS NOT TRUE "
               # "AND playlists.download IS TRUE "
               "AND playlists.monitor IS TRUE "
               "AND NOT EXISTS ( SELECT 1 FROM videos WHERE videos.playlist = playlists.url ) "
               "ORDER BY playlists.priority DESC, EXTRACT(year FROM playlists.date_checked) ASC, "
               "EXTRACT(month FROM playlists.date_checked) ASC, EXTRACT(day FROM playlists.date_checked) ASC, "
               "EXTRACT(hour FROM playlists.date_checked) ASC, RAND();")
        val = ('youtube', channel_id)
        mysql_cursor.execute(sql, val)
        mysql_result = mysql_cursor.fetchall()
        # playlists.append(mysql_result)
        for entry in mysql_result:
            playlists.append(entry)

        # Get playlists with videos present
        sql = ("SELECT playlists.site, playlists.url, playlists.name, playlists.priority, "
               "channels.url, channels.name, channels.priority, playlists.download "
               "FROM playlists "
               "INNER JOIN channels "
               "ON playlists.channel = channels.url "
               "WHERE playlists.site = %s "
               "AND playlists.channel = %s "
               "AND playlists.done IS NOT TRUE "
               # "AND playlists.download IS TRUE "
               "AND playlists.monitor IS TRUE "
               "AND EXISTS ( SELECT 1 FROM videos WHERE videos.playlist = playlists.url ) "
               "ORDER BY playlists.priority DESC, EXTRACT(year FROM playlists.date_checked) ASC, "
               "EXTRACT(month FROM playlists.date_checked) ASC, EXTRACT(day FROM playlists.date_checked) ASC, "
               "EXTRACT(hour FROM playlists.date_checked) ASC, RAND();")
        val = ('youtube', channel_id)
        mysql_cursor.execute(sql, val)
        mysql_result = mysql_cursor.fetchall()
        # playlists.append(mysql_result)
        for entry in mysql_result:
            playlists.append(entry)

        retry_db = False

    return playlists


def get_video_details(video_id, ignore_errors, archive_set):
    """Fills the details for a video by its ID"""
    global vpn_frequency
    vpn_counter = 0
    done = False

    while not done:
        # Try-Except Block to handle YT-DLP exceptions such as "playlist does not exist"
        try:
            video_url = f'https://www.youtube.com/watch?v={video_id}'

            # Set download options for YT-DLP
            video_download_options = {
                'logger': VoidLogger(),
                'skip_download': True,
                'allow_playlist_files': False,
                'cachedir': False,
                'ignoreerrors': ignore_errors,
                'download_archive': archive_set,
                'extractor_args': {'youtube': {'skip': ['configs', 'webpage', 'js']}},
                'extractor_retries': retry_extraction_video,
                'socket_timeout': timeout_video,
                'source_address': external_ip
            }

            # Run YT-DLP
            with yt_dlp.YoutubeDL(video_download_options) as ilus:
                info_json = ilus.sanitize_info(ilus.extract_info(video_url, process=True, download=False))

            if DEBUG_json_video_details:
                with open('debug.json', 'w', encoding='utf-8') as json_file:
                    # noinspection PyTypeChecker
                    json.dump(info_json, json_file, ensure_ascii=False, indent=4)
                input(f'Dumped JSON... Continue?')

            return info_json

        except KeyboardInterrupt:
            sys.exit()

        except Exception as e:
            if regex_bot.search(str(e)):
                print(f'{datetime.now()} {Fore.RED}BOT DETECTED{Style.RESET_ALL}')
                vpn_frequency = DEFAULT_vpn_frequency
                vpn_counter = reconnect_vpn(vpn_counter)

            else:
                # print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while getting details for video "{video_id}": {e}')
                raise


def get_channel_details(channel_url, ignore_errors):
    print(f'{datetime.now()} Getting ID for channel "{channel_url}"')

    # Set download options for YT-DLP
    channel_download_options = {'extract_flat': True,
                                'skip_download': True,
                                'allow_playlist_files': False,
                                'quiet': True,
                                'no_warnings': True,
                                'playlist_items': '0',
                                'ignoreerrors': ignore_errors,
                                'download_archive': None,
                                'extractor_args': {'youtube': {'skip': ['configs', 'webpage', 'js']}},
                                'extractor_retries': retry_extraction_channel,
                                'socket_timeout': timeout_channel,
                                'source_address': external_ip
                                }

    # Try-Except Block to handle YT-DLP exceptions such as "playlist does not exist"
    try:
        # Run YT-DLP
        with yt_dlp.YoutubeDL(channel_download_options) as ilus:
            info_json = ilus.sanitize_info(ilus.extract_info(channel_url, process=True, download=False))

        if DEBUG_channel_id:
            with open('debug.json', 'w', encoding='utf-8') as f:
                # noinspection PyTypeChecker
                json.dump(info_json, f, ensure_ascii=False, indent=4)
            input(f'Dumped JSON... Continue?')

        try:
            # Check if there is an ID in the JSON, otherwise we cannot use it.
            json_id = info_json['id']
            if regex_handle_as_id.search(str(json_id)):
                print(f'{datetime.now()} {Fore.RED}MALFORMED{Style.RESET_ALL} channel ID  "{json_id}"! '
                      f'Please try again and use /videos URL to avoid this! ',
                      end='\n')
            else:
                print(f'{datetime.now()} {Fore.GREEN}FOUND{Style.RESET_ALL} channel ID  "{json_id}" in Info JSON ',
                      end='\r')
                return info_json
        except KeyboardInterrupt:
            sys.exit()
        except Exception as e:
            print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} cannot find channel ID in Info JSON '
                  f'"{info_json}" {e}')
            return None
            # TODO: To make this work properly, we need to count retries and give up at some point, I guess?
            # return [] # This is to stop repeating to try in this (rare) case of not getting entries for playlist EVER (cause unknown, possibly related to single video lists or hidden videos etc.)

    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding channel from URL "{channel_url}": '
              f'{e}')
        return None


def add_channel(channel_id, channel_name):
    channel_site = 'youtube'

    channel_priority = 100

    try:
        mydb = mysql.connector.connect(
            host=mysql_host,
            user=mysql_user,
            password=mysql_password,
            database=mysql_database)

        mysql_cursor = mydb.cursor()

        sql = "INSERT INTO channels (site, url, name, priority) VALUES (%s, %s, %s, %s)"
        val = (channel_site, channel_id, channel_name, channel_priority)
        mysql_cursor.execute(sql, val)
        mydb.commit()

        print(f'{datetime.now()} {Fore.GREEN}NEW CHANNEL{Style.RESET_ALL}: '
              f'"{channel_name}" ({channel_site} {channel_id})')
        print()

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_add_channel:
        if regex_sql_duplicate.search(str(exception_add_channel)):
            # TODO: return parameter of this needs reworking but cannot be bothered right now FR
            pass
        else:
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding playlist '
                  f'"{channel_name}" ({channel_site} {channel_id}): {exception_add_channel}')
            return None


def add_playlist(playlist_id, playlist_name, channel_id, download, monitor):
    playlist_site = 'youtube'

    if channel_id == playlist_id:
        playlist_priority = 0
    else:
        playlist_priority = 100

    try:
        mydb = mysql.connector.connect(
            host=mysql_host,
            user=mysql_user,
            password=mysql_password,
            database=mysql_database)

        mysql_cursor = mydb.cursor()

        sql = "INSERT INTO playlists (site, url, name, channel, priority, download, monitor) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        val = (playlist_site, playlist_id, playlist_name, channel_id, playlist_priority, download, monitor)
        mysql_cursor.execute(sql, val)
        mydb.commit()

        print(f'{datetime.now()} {Fore.GREEN}NEW PLAYLIST{Style.RESET_ALL}: '
              f'"{playlist_name}" ({playlist_site} {playlist_id})')
        print()

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_add_playlist:
        if regex_sql_duplicate.search(str(exception_add_playlist)):
            # TODO: return parameter of this needs reworking but cannot be bothered right now FR
            pass
        else:
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id}): {exception_add_playlist}')
            return None


def get_text_color_for_video_status(video_status):
    # Set text_color for video status
    text_color = Fore.WHITE
    if video_status == STATUS_PRIVATE:
        text_color = Fore.RED
    elif video_status == STATUS_REMOVED:
        text_color = Fore.RED
    elif video_status == STATUS_AGE_RESTRICTED:
        text_color = Fore.RED
    elif video_status == STATUS_BROKEN_UNAVAILABLE:
        text_color = Fore.RED
    elif video_status == STATUS_CURSED:
        text_color = Fore.RED
    elif video_status == STATUS_UNAVAILABLE:
        text_color = Fore.RED
    elif video_status == STATUS_BROKEN:
        text_color = Fore.YELLOW
    elif video_status == STATUS_MEMBERS_ONLY:
        text_color = Fore.YELLOW
    elif video_status == STATUS_UNCERTAIN:
        text_color = Fore.YELLOW
    elif video_status == STATUS_WANTED:
        text_color = Fore.CYAN
    elif video_status == STATUS_UNWANTED:
        text_color = Fore.CYAN
    elif video_status == STATUS_VERIFIED:
        text_color = Fore.GREEN
    elif video_status == STATUS_DONE:
        text_color = Fore.GREEN

    return text_color


def add_video(video_site, video_id, video_channel, video_playlist, video_status, video_date, download, database=None):
    """Adds a video to given playlist & channel in database with the given status fields"""
    if not database:
        mydb = connect_database()
    else:
        mydb = database

    global global_archive_set

    mysql_cursor = mydb.cursor()
    sql = ("INSERT INTO videos(site, url, channel, playlist, status, original_date, download) "
           "VALUES(%s, %s, %s, %s, %s, %s, %s) "
           "ON DUPLICATE KEY UPDATE status = VALUES(status);")
    val = (video_site, video_id, video_channel, video_playlist, video_status, video_date, download)
    mysql_cursor.execute(sql, val)
    mydb.commit()

    text_color = get_text_color_for_video_status(video_status=video_status)

    if f'{video_site} {video_id}' in global_archive_set:
        print(f'{datetime.now()} {Fore.CYAN}UPDATED{Style.RESET_ALL} video "{video_site} {video_id}" '
              f'to status {text_color}"{video_status}"{Style.RESET_ALL}')
    else:
        global_archive_set.add(f'{video_site} {video_id}')
        print(f'{datetime.now()} {Fore.GREEN}ADDED{Style.RESET_ALL} video "{video_site} {video_id}" '
              f'with status {text_color}"{video_status}"{Style.RESET_ALL}')


def process_video(video, channel_site, channel_id, playlist_id, download, archive_set, database):
    """Processes a video and adds it to database depending on results and settings"""
    if DEBUG_json_video_add:
        with open('debug.json', 'w', encoding='utf-8') as json_file:
            # noinspection PyTypeChecker
            json.dump(video, json_file, ensure_ascii=False, indent=4)
        input(f'Dumped JSON... Continue?')

    # Skip input error
    if video is None:
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} no video!')
        if DEBUG_empty_video:
            input('Continue?')
        return False

    # Get key fields
    try:
        video_site = channel_site
        video_id = video['id']
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_add_video:
        print(f'{datetime.now()} {Fore.RED}MISSING{Style.RESET_ALL} JSON field {exception_add_video} '
              f'in video "{video}": ')
        return False

    # CLEAR date
    original_date = None

    # Check that video has all details (full extract) or extract info (flat extract)
    try:
        # This is NOT in flat playlist JSON, if we want to use flat, we need to extract videos individually!
        video_channel_id = video['channel_id']
        video_type = video['media_type']
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_add_video:
        if not extract_flat_playlist:  # retrying online is expected to happen then extract_flat_playlist is True
            print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} reading local video details, retrying online')
        try:
            # Get all info for video online (necessary in case of flat extraction)
            video = get_video_details(video_id=video_id, ignore_errors=False, archive_set=archive_set)
            video_channel_id = video['channel_id']
            video_type = video['media_type']

        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_add_video:
            if (regex_video_members_only.search(str(exception_add_video))
                    or regex_video_members_tier.search(str(exception_add_video))):
                print(f'{datetime.now()} {Fore.RED}MEMBERS ONLY{Style.RESET_ALL} video "{video_id}"')
                # Update DB
                try:
                    add_video(video_site=video_site,
                              video_id=video_id,
                              video_channel=channel_id,
                              video_playlist=playlist_id,
                              video_status=STATUS_MEMBERS_ONLY,
                              video_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating video "{video_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_video_removed.search(str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}REMOVED{Style.RESET_ALL} video "{video_id}"')
                # Update DB
                try:
                    add_video(video_site=video_site,
                              video_id=video_id,
                              video_channel=channel_id,
                              video_playlist=playlist_id,
                              video_status=STATUS_REMOVED,
                              video_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating video "{video_id}": '
                          f'{exception_update_db}')
                    return False

            elif (regex_video_unavailable.search(str(exception_add_video))
                  or regex_video_unavailable_live.search(str(exception_add_video))):
                print(f'{datetime.now()} {Fore.RED}UNAVAILABLE{Style.RESET_ALL} video "{video_id}"')
                # Update DB
                try:
                    add_video(video_site=video_site,
                              video_id=video_id,
                              video_channel=channel_id,
                              video_playlist=playlist_id,
                              video_status=STATUS_UNAVAILABLE,
                              video_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating video "{video_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_video_unavailable_geo.search(str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}GEO BLOCKED{Style.RESET_ALL} video "{video_id}"')
                # TODO: Handle geo location change?
                return False

            elif regex_video_private.search(str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}PRIVATE{Style.RESET_ALL} video "{video_id}"')
                # Update DB
                try:
                    add_video(video_site=video_site,
                              video_id=video_id,
                              video_channel=channel_id,
                              video_playlist=playlist_id,
                              video_status=STATUS_PRIVATE,
                              video_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating video "{video_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_video_age_restricted.search(str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}AGE RESTRICTED{Style.RESET_ALL} video "{video_id}"')
                # Update DB
                try:
                    add_video(video_site=video_site,
                              video_id=video_id,
                              video_channel=channel_id,
                              video_playlist=playlist_id,
                              video_status=STATUS_AGE_RESTRICTED,
                              video_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_add_video:
                    if regex_sql_duplicate.search(str(exception_add_video)):
                        print(f'{datetime.now()} {Fore.RED}DUPLICATE{Style.RESET_ALL} video "{video_id}"')
                        return True
                    else:
                        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding '
                              f'{Fore.RED}UNAVAILABLE{Style.RESET_ALL} video "{video_id}": {exception_add_video}')
                        return False

            elif regex_offline.search(str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}OFFLINE{Style.RESET_ALL} ({exception_add_video})')
                # Update DB
                try:
                    add_video(video_site=video_site,
                              video_id=video_id,
                              video_channel=channel_id,
                              video_playlist=playlist_id,
                              video_status=STATUS_UNAVAILABLE,
                              video_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_add_video:
                    if regex_sql_duplicate.search(str(exception_add_video)):
                        print(f'{datetime.now()} {Fore.RED}DUPLICATE{Style.RESET_ALL} video "{video_id}"')
                        return True
                    else:
                        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding '
                              f'{Fore.RED}UNAVAILABLE{Style.RESET_ALL} video "{video_id}": {exception_add_video}')
                        return False

            else:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while processing video "{video}": '
                      f'{exception_add_video}')
                return None  # Return None to trigger retry

    # Get date
    if original_date is None:
        try:
            original_date = datetime.strptime(video['upload_date'], '%Y%m%d').strftime('%Y-%m-%d')
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_date:
            if DEBUG_log_date_fields_missing:
                print(f'{datetime.now()} {Fore.YELLOW}MISSING{Style.RESET_ALL} JSON field {exception_date}')
    if original_date is None:
        try:
            original_date = datetime.strptime(video['release_date'], '%Y%m%d').strftime('%Y-%m-%d')
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_date:
            if DEBUG_log_date_fields_missing:
                print(f'{datetime.now()} {Fore.YELLOW}MISSING{Style.RESET_ALL} JSON field {exception_date}')
    if original_date is None:
        print(f'{datetime.now()} {Fore.RED}NO DATE{Style.RESET_ALL} aborting!')
        return False

    # Get Media Type
    final_playlist_id = playlist_id
    final_download = download
    if video_type == 'short':
        final_playlist_id = '#shorts'
        if download_shorts:
            final_download = download
        else:
            final_download = False
        # TODO: This is not matching our data model, it leads to just ONE playlist for all shorts which changes channel ownership
        # add_playlist(playlist_id=final_playlist_id,
        #              playlist_name=playlist_name_shorts,
        #              channel_id=channel_id,
        #              download=final_download,
        #              monitor= )
    elif video_type == 'livestream':
        final_playlist_id = '#livestreams'
        if download_livestreams:
            final_download = download
        else:
            final_download = False
        # TODO: This is not matching our data model, it leads to just ONE playlist for all livestreams which changes channel ownership
        # add_playlist(playlist_id=final_playlist_id,
        #              playlist_name=playlist_name_livestreams,
        #              channel_id=channel_id,
        #              download=final_download,
        #              monitor= )

    # TODO: This STILL leads to shorts and livestreams being added as regular videos.
    #  The "media_type" field is NOT reliable for videos which aren't available yet!
    try:
        if video['availability'] is None:
            print(f'{datetime.now()} {Fore.RED}PSEUDO-PRIVATE{Style.RESET_ALL} video "{video_id}"')
            # Update DB
            try:
                # add_video(video_site=video_site,
                #           video_id=video_id,
                #           video_channel=video_channel_id,
                #           video_playlist=final_playlist_id,
                #           video_status=STATUS_PRIVATE,
                #           video_date=original_date,
                #           download=final_download,
                #           database=database)
                return True
            except KeyboardInterrupt:
                sys.exit()
            except Exception as exception_update_db:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating video "{video_id}": '
                      f'{exception_update_db}')
                return False
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_check_private:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} checking private video: '
              f'{exception_check_private}')
        return True

    if original_date is not None:
        if final_download:
            video_status = STATUS_WANTED
            print(f'{datetime.now()} {Fore.CYAN}ADDING{Style.RESET_ALL} video {video_id} type "{video_type}"',
                  end='\r')
        else:
            video_status = STATUS_UNWANTED
            print(f'{datetime.now()} {Fore.CYAN}SKIPPING{Style.RESET_ALL} video "{video_id}" type "{video_type}"',
                  end='\r')

        # Update DB
        try:
            add_video(video_site=video_site,
                      video_id=video_id,
                      video_channel=video_channel_id,
                      video_playlist=final_playlist_id,
                      video_status=video_status,
                      video_date=original_date,
                      download=final_download,
                      database=database)
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_add_video:
            if regex_sql_duplicate.search(str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}DUPLICATE{Style.RESET_ALL} video "{video_id}"')
                return True
            else:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding video "{video_id}": '
                      f'{exception_add_video}')
                return False

        if final_download:
            print(f'{datetime.now()} {Fore.GREEN}ADDED{Style.RESET_ALL} video "{video_id}" type "{video_type}"'
                  f'        ', end='\n')
        else:
            print(f'{datetime.now()} {Fore.YELLOW}SKIPPED{Style.RESET_ALL} video "{video_id}" type "{video_type}"'
                  f'        ', end='\n')
        return True

    else:
        print(f'{datetime.now()} {Fore.RED}INCOMPLETE{Style.RESET_ALL} video "{video_id}"')
        return False


def sanitize_name(name, is_user=False):
    name_sane = name
    # TODO: This seems overcomplicated to implement ourselves, we should seek a pre-existing package that does this!

    if regex_val.search(name_sane) or regex_caps.search(name):
        # TODO: This way of doing things does not fix things written in ALL CAPS. We should look into how to best handle all ways of wiring

        # German Umlaut
        name_sane = re.sub(r'ä', 'ae', name_sane)
        name_sane = re.sub(r'Ä', 'AE', name_sane)
        name_sane = re.sub(r'ö', 'oe', name_sane)
        name_sane = re.sub(r'Ö', 'OE', name_sane)
        name_sane = re.sub(r'ü', 'ue', name_sane)
        name_sane = re.sub(r'Ü', 'UE', name_sane)
        name_sane = re.sub(r'ß', 'ss', name_sane)

        # English Apostrophes
        name_sane = re.sub(r"don't ", 'Do not ', name_sane)
        name_sane = re.sub(r"Don't ", 'Do not ', name_sane)
        name_sane = re.sub(r"I'm ", 'I am ', name_sane)
        name_sane = re.sub(r"you're ", 'you are ', name_sane)
        name_sane = re.sub(r"You're ", 'You are ', name_sane)
        name_sane = re.sub(r"she's ", 'she is ', name_sane)
        name_sane = re.sub(r"She's ", 'She is ', name_sane)
        name_sane = re.sub(r"he's ", 'he is ', name_sane)
        name_sane = re.sub(r"He's ", 'He is ', name_sane)
        name_sane = re.sub(r"it's ", 'it is ', name_sane)
        name_sane = re.sub(r"It's ", 'It is ', name_sane)
        name_sane = re.sub(r"We're ", 'We are ', name_sane)
        name_sane = re.sub(r"we're ", 'we are ', name_sane)

        # Alternative hyphens to real hypes
        name_sane = re.sub(r"–", '-', name_sane)

        # &
        name_sane = re.sub(r' & ', ' and ', name_sane)

        # ": " is not allowed on Windows!
        name_sane = re.sub(r': ', ' - ', name_sane)

        # Remove all other unknown chars
        name_sane = re.sub(regex_val, '', name_sane)

        # Remove whitespace
        name_sane = re.sub(r'^ +', '', name_sane)
        name_sane = re.sub(r' +$', '', name_sane)
        name_sane = re.sub(r'  +', '', name_sane)

    if not is_user:
        # Make proper title case
        name_sane = name_sane.title()

    if name != name_sane:
        print(f'{datetime.now()} {Fore.CYAN}ATTENTION{Style.RESET_ALL} name sanitized from "{name}" to "{name_sane}"')

    return name_sane


def reconnect_vpn(counter, vpn_countries=None):
    """Reconnects NordVPN to a random country from list"""
    if enable_vpn:
        time_difference = (datetime.now() - vpn_timestamp).total_seconds()
        if time_difference < vpn_frequency:
            sleep_time = vpn_frequency - time_difference
            print(f'{datetime.now()} {Fore.YELLOW}WAITING{Style.RESET_ALL} {sleep_time}s before reconnecting', end='\n')
            time.sleep(sleep_time)

        if vpn_countries is None:
            vpn_countries = DEFAULT_vpn_countries

        if counter is None:
            counter = 0
        elif counter >= len(vpn_countries):
            counter = 0

        # vpn_country = random.choice(vpn_countries)
        vpn_country = vpn_countries[counter]

        # Increment to use next country next time
        counter += 1

        counter_retry_vpn = 0
        while counter_retry_vpn < retry_reconnect_new_vpn_node:
            print(f'{datetime.now()} {Fore.CYAN}RECONNECTING{Style.RESET_ALL} to {vpn_country} ({counter})...',
                  end='\r')
            vpn_command = ['C:\\Program Files\\NordVPN\\NordVPN.exe', '-c', '-g', vpn_country]

            try:
                check_output(vpn_command, stderr=STDOUT, timeout=timeout_vpn)
            except KeyboardInterrupt:
                sys.exit()
            except Exception as exception_reconnect_vpn:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} connecting VPN: '
                      f'{exception_reconnect_vpn}',
                      end='\n')
                counter_retry_vpn += 1

            print(f'{datetime.now()} {Fore.CYAN}CONNECTED{Style.RESET_ALL} to {vpn_country} ({counter})          ',
                  end='\n')

            time.sleep(sleep_time_vpn)

            return counter

    else:
        print(f'{datetime.now()} {Fore.CYAN}VPN DISABLED{Style.RESET_ALL}')


def get_videos_from_db(database, status=STATUS_WANTED):
    """
    Returns a list of all wanted YouTube videos als list of lists
    Inner list field order is as follows:
      - videos.site
      - videos.url
      - videos.original_date
      - videos.status
      - channels.name
      - channels.url
      - playlists.name
      - playlists.url
      """

    text_color = get_text_color_for_video_status(status)

    print(f'{datetime.now()} Collecting {text_color}{status}{Style.RESET_ALL} videos...', end='\r')

    mysql_cursor = database.cursor()

    sql = (
        "SELECT videos.site, videos.url, videos.original_date, videos.status, "
        "channels.name, channels.url, "
        "playlists.name, playlists.url "
        "FROM videos "
        "INNER JOIN playlists ON videos.playlist=playlists.url "
        "INNER JOIN channels ON playlists.channel=channels.url "
        "WHERE (videos.status = %s) "
        "AND videos.download IS TRUE "
        "ORDER BY "
        "EXTRACT(year FROM videos.original_date) DESC, "
        "EXTRACT(month FROM videos.original_date) DESC, "
        "EXTRACT(day FROM videos.original_date) DESC, "
        "channels.priority DESC, "
        "playlists.priority DESC, "
        "RAND();")

    val = (status,)

    mysql_cursor.execute(sql, val)

    mysql_result = mysql_cursor.fetchall()

    print(f'{datetime.now()} {Fore.CYAN}FOUND{Style.RESET_ALL} {len(mysql_result)} '
          f'{text_color}{status}{Style.RESET_ALL} videos      ', end='\n')

    return mysql_result


def download_all_videos():
    global GEO_BLOCKED_vpn_countries
    global vpn_frequency

    database = connect_database()

    # Videos which are not downloaded and available to download
    status_priority = {STATUS_BROKEN, STATUS_WANTED}

    # Videos which could have been unreleased before (or simply taken private for other reasons, sadly no way to tell)
    status_secondary = {STATUS_PRIVATE}

    # Videos that can only be downloaded using YT account
    status_account_required = {STATUS_AGE_RESTRICTED}

    # Videos in other error states (slim chance we can ever get these downloaded TBH)
    status_hopeless = {STATUS_UNAVAILABLE,
                       STATUS_BROKEN_UNAVAILABLE,
                       STATUS_REMOVED}

    # Collect videos of various status indicating download ability
    all_videos = []
    # TODO
    #  for current_status in status_account_required:
    #    text_color = get_text_color_for_video_status(video_status=current_status)
    #    account_required_videos = get_videos_from_db(database=database,
    #    status=current_status)
    #    all_videos.extend(account_required_videos)

    for current_status in status_priority:
        text_color = get_text_color_for_video_status(video_status=current_status)
        priority_videos = get_videos_from_db(database=database,
                                             status=current_status)
        all_videos.extend(priority_videos)

    for current_status in status_secondary:
        text_color = get_text_color_for_video_status(video_status=current_status)
        secondary_videos = get_videos_from_db(database=database,
                                              status=current_status)
        all_videos.extend(secondary_videos)

    # TODO
    #  for current_status in status_hopeless:
    #    text_color = get_text_color_for_video_status(video_status=current_status)
    #    hopeless_videos = get_videos_from_db(database=database,
    #    status=current_status)
    #    all_videos.extend(hopeless_videos)

    if len(all_videos) == 0:
        print(f'{datetime.now()} {Fore.CYAN}DONE{Style.RESET_ALL} waiting {sleep_time_download_done} seconds')
        time.sleep(sleep_time_download_done)

    else:
        old_video_status = ''
        timestamp_old = datetime.now()
        video_counter = 0
        for current_video in all_videos:
            video_counter += 1

            video_site = current_video[0]
            video_id = current_video[1]
            original_date = current_video[2]
            video_status = current_video[3]
            channel_name = current_video[4]
            channel_id = current_video[5]
            playlist_name = current_video[6]
            playlist_id = current_video[7]

            timestamp_now = datetime.now()
            timestamp_distance = timestamp_now - timestamp_old

            if old_video_status != video_status:
                text_color = get_text_color_for_video_status(video_status=video_status)
                print(f'{timestamp_now} {Fore.CYAN}SWITCHED{Style.RESET_ALL} '
                      f'to downloading {text_color}"{video_status}"{Style.RESET_ALL} videos!')
            old_video_status = video_status

            if video_status == STATUS_PRIVATE and timestamp_distance.seconds > switch_to_primary_frequency:
                timestamp_old = timestamp_now
                database = connect_database()  # We HAVE to reconnect DB for updated results!

                priority_videos = []
                for current_status in status_priority:
                    priority_videos.extend(get_videos_from_db(database=database,
                                                              status=current_status))

                if priority_videos and len(priority_videos) > 0:
                    text_color = get_text_color_for_video_status(video_status=video_status)
                    print(f'{timestamp_now} {Fore.YELLOW}ABORTING{Style.RESET_ALL} '
                          f'downloading {text_color}{video_status}{Style.RESET_ALL} '
                          f'to focus on {len(priority_videos)} priority videos!')
                    break

            video_downloaded = False

            vpn_counter_geo = 0
            GEO_BLOCKED_vpn_countries = []

            while not video_downloaded:
                video_downloaded = download_video(video=current_video)
                if video_downloaded is True:
                    continue
                elif video_downloaded is None:
                    return
                else:
                    if GEO_BLOCKED_vpn_countries:
                        vpn_frequency = GEO_BLOCKED_vpn_frequency
                        vpn_counter_geo = reconnect_vpn(vpn_counter_geo, GEO_BLOCKED_vpn_countries)
                        # To break endless loop
                        if vpn_counter_geo == 0:
                            continue


def download_video(video):
    video_site = video[0]
    video_id = video[1]
    original_date = video[2]
    video_status = video[3]
    channel_name = video[4]
    channel_id = video[5]
    playlist_name = video[6]
    playlist_id = video[7]

    if directory_download_temp is None or directory_download_home is None:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} download paths are not set!')
        return False

    # Clear temp directory
    try:
        print(f'{datetime.now()} {Fore.CYAN}DELETING TEMP DIRECTORY{Style.RESET_ALL} {directory_download_temp}',
              end='\r')
        shutil.rmtree(directory_download_temp)
        print(f'{datetime.now()} {Fore.CYAN}DELETED TEMP DIRECTORY{Style.RESET_ALL} {directory_download_temp} ',
              end='\n')
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_clear_temp:
        if not regex_error_win_2.search(str(exception_clear_temp)):
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} {exception_clear_temp}')

    text_color = get_text_color_for_video_status(video_status=video_status)

    print(f'{datetime.now()} {Fore.CYAN}DOWNLOADING{Style.RESET_ALL} '
          f'video "{video_site} - {video_id}" '
          f'status {text_color}"{video_status}"{Style.RESET_ALL}')

    if video_site == 'youtube':
        # Set the full output path
        full_path = os.path.join(f'{channel_name} - {playlist_name}',
                                 f'Season %(release_date>%Y,upload_date>%Y)s [{channel_name}]',
                                 f'{channel_name} - {playlist_name} - '
                                 f'S%(release_date>%Y,upload_date>%Y)sE%(release_date>%j,upload_date>%j)s - '
                                 f'%(title)s.%(ext)s')
        # print(f'Path for video "{video_site} {video_id}": {full_path}')

        video_url = f'https://www.youtube.com/watch?v={video_id}'

        # Set download options for YT-DLP
        video_download_options = {
            'logger': VoidLogger(),  # TODO: This suppresses all errors, we should still see them in exception handling
            'quiet': quiet_download_info,
            'no_warnings': quiet_download_warnings,
            # 'verbose': True,
            'download_archive': None,  # TODO: This is correct, yes?
            'cachedir': False,
            'skip_unavailable_fragments': False,  # To abort on missing video parts (largely avoids re-downloading)
            'ignoreerrors': False,
            'ignore_no_formats_error': False,  # Keep "False" to get exception to handle in python!
            'extractor_retries': retry_extraction_download,
            'socket_timeout': timeout_download,
            'source_address': external_ip,
            'nocheckcertificate': True,
            'restrictfilenames': True,
            'windowsfilenames': True,
            'throttledratelimit': 1000,
            'retries': 0,
            'concurrent_fragment_downloads': 20,
            'overwrites': True,
            'writethumbnail': True,
            'embedthumbnail': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'writeinfojson': True,
            'allow_playlist_files': False,
            # 'check_formats': True,
            'format': 'bestvideo*[ext=mp4][height<=1080]+bestaudio[ext=m4a]',
            'allow_multiple_audio_streams': True,
            'merge_output_format': 'mp4',
            'subtitleslangs': ['de-orig', 'en-orig'],
            'outtmpl': full_path,
            'paths': {
                'temp': directory_download_temp,
                'home': directory_download_home,
            },
            'postprocessors': [
                {
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                },
                {
                    'key': 'FFmpegMetadata',
                    'add_metadata': True,
                },
                {
                    'key': 'EmbedThumbnail',
                    'already_have_thumbnail': True,
                },
                {
                    'key': 'FFmpegThumbnailsConvertor',
                    'format': 'png',
                    'when': 'before_dl',
                }
            ],
        }

        r'''# leftover YT-DLP config
    # Do not remove sponsored segments
    --no-sponsorblock

    --recode mp4

    # Do not continue download started before (as this will lead to corruption if initial download was interrupted in any way, including brief internet outages or packet loss)
    --no-continue

    # Set Retry Handling
    --retry-sleep 1
    --file-access-retries 1000
    --fragment-retries 30
    --extractor-retries 3

    # Abort when redirected to "Video Not Available"-page, pieces of video are missing, or any other errors happen
    --break-match-filters "title!*=Video Not Available"
        '''

        # Try-Except Block to handle YT-DLP exceptions such as "playlist does not exist"
        try:
            # Run YT-DLP
            with yt_dlp.YoutubeDL(video_download_options) as ilus:
                # ilus.download(video_url)
                meta = ilus.extract_info(video_url, download=True)
                meta = ilus.sanitize_info(meta)
                path = meta['requested_downloads'][0]['filepath']
                # TODO: new format? path = path[len(directory_download_home)+len(os.sep):len(path)-len('.mp4')]
                path = path[len(directory_download_home) + len(os.sep):len(path)]

                # Get date
                if original_date is None:
                    try:
                        original_date = datetime.strptime(meta['upload_date'], '%Y%m%d').strftime('%Y-%m-%d')
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception_date:
                        if DEBUG_log_date_fields_missing:
                            print(f'{datetime.now()} {Fore.YELLOW}MISSING{Style.RESET_ALL} JSON field {exception_date}')
                if original_date is None:
                    try:
                        original_date = datetime.strptime(meta['release_date'], '%Y%m%d').strftime('%Y-%m-%d')
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception_date:
                        if DEBUG_log_date_fields_missing:
                            print(f'{datetime.now()} {Fore.YELLOW}MISSING{Style.RESET_ALL} JSON field {exception_date}')
                if original_date is None:
                    print(f'{datetime.now()} {Fore.RED}NO DATE{Style.RESET_ALL} aborting!')
                    return False

            """
            What happens in the weird edge-case that YT-DLP ends with reaching all retries?
            It does not progress past this point, but also does not throw an exception. No IDK how/why.
            """

            # Update DB
            try:
                # TODO: This needs to be worked into the add_video method (or update_video, whatever we end up calling it
                video_status = 'fresh'
                mydb = connect_database()
                mysql_cursor = mydb.cursor()
                sql = "UPDATE videos SET status = %s, save_path = %s, original_date = %s WHERE site = %s AND url = %s;"
                val = (video_status, path, original_date, video_site, video_id)
                mysql_cursor.execute(sql, val)
                mydb.commit()
                print(f'{datetime.now()} {Fore.CYAN}UPDATED{Style.RESET_ALL} video "{video_id}"'
                      f'to status "{video_status}"')
                return True
            except KeyboardInterrupt:
                sys.exit()
            except Exception as exception_update_db:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating video "{video_id}": '
                      f'{exception_update_db}')
                return False
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_download:
            if (regex_video_members_only.search(str(exception_download))
                    or regex_video_members_tier.search(str(exception_download))):
                # print(f'{datetime.now()} {Fore.RED}MEMBERS ONLY{Style.RESET_ALL} video "{video_id}"')
                # Update DB
                try:
                    if video_status != STATUS_MEMBERS_ONLY:
                        add_video(video_site=video_site,
                                  video_id=video_id,
                                  video_channel=channel_id,
                                  video_playlist=playlist_id,
                                  video_status=STATUS_MEMBERS_ONLY,
                                  video_date=original_date,
                                  download=True)  # Download can be assumed to be True for a video that is being downloaded
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating video "{video_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_video_removed.search(str(exception_download)):
                # print(f'{datetime.now()} {Fore.RED}REMOVED{Style.RESET_ALL} video "{video_id}"')
                # Update DB
                try:
                    if video_status != STATUS_REMOVED:
                        add_video(video_site=video_site,
                                  video_id=video_id,
                                  video_channel=channel_id,
                                  video_playlist=playlist_id,
                                  video_status=STATUS_REMOVED,
                                  video_date=original_date,
                                  download=True)  # Download can be assumed to be True for a video that is being downloaded
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating video "{video_id}": '
                          f'{exception_update_db}')
                    return False

            elif (regex_video_unavailable.search(str(exception_download))
                  or regex_video_unavailable_live.search(str(exception_download))):
                # print(f'{datetime.now()} {Fore.RED}UNAVAILABLE{Style.RESET_ALL} video "{video_id}"')
                # Update DB
                try:
                    if video_status != STATUS_UNAVAILABLE:
                        add_video(video_site=video_site,
                                  video_id=video_id,
                                  video_channel=channel_id,
                                  video_playlist=playlist_id,
                                  video_status=STATUS_UNAVAILABLE,
                                  video_date=original_date,
                                  download=True)  # Download can be assumed to be True for a video that is being downloaded
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating video "{video_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_video_unavailable_geo.search(str(exception_download)):
                # print(f'{datetime.now()} {Fore.RED}GEO BLOCKED{Style.RESET_ALL} video "{video_id}"')
                global GEO_BLOCKED_vpn_countries
                if not GEO_BLOCKED_vpn_countries:
                    try:
                        countries_results = regex_video_unavailable_geo_fix.search(str(exception_download))
                        countries_str = countries_results.group(0)
                        countries_list = countries_str.split(', ')
                        GEO_BLOCKED_vpn_countries = countries_list
                        return False
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception_regex_geo_blocked:
                        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL}: '
                              f'{exception_regex_geo_blocked}')
                        # To prevent external endless loop
                        return True

            elif regex_video_private.search(str(exception_download)):
                # print(f'{datetime.now()} {Fore.RED}PRIVATE{Style.RESET_ALL} video "{video_id}"')
                # Update DB
                try:
                    if video_status != STATUS_PRIVATE:
                        add_video(video_site=video_site,
                                  video_id=video_id,
                                  video_channel=channel_id,
                                  video_playlist=playlist_id,
                                  video_status=STATUS_PRIVATE,
                                  video_date=original_date,
                                  download=True)  # Download can be assumed to be True for a video that is being downloaded
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating video "{video_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_video_age_restricted.search(str(exception_download)):
                # print(f'{datetime.now()} {Fore.RED}AGE RESTRICTED{Style.RESET_ALL} video "{video_id}"')
                # Update DB
                try:
                    if video_status != STATUS_AGE_RESTRICTED:
                        add_video(video_site=video_site,
                                  video_id=video_id,
                                  video_channel=channel_id,
                                  video_playlist=playlist_id,
                                  video_status=STATUS_AGE_RESTRICTED,
                                  video_date=original_date,
                                  download=True)  # Download can be assumed to be True for a video that is being downloaded
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating video "{video_id}": '
                          f'{exception_update_db}')
                    return False
            else:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} downloading video: {exception_download}')
                return True


def get_monitored_playlists_from_db():
    """
    Returns all playlists as list of lists

    Inner list field order is as follows:
      - playlists.site
      - playlists.url
      - playlists.name
      - playlists.priority
      - channels.url
      - channels.name
      - channels.priority
      - playlists.download
      """

    playlists = []
    retry_db = True
    while retry_db:
        print(f'{datetime.now()} Collecting all playlists', end='\r')
        mydb = connect_database()

        mysql_cursor = mydb.cursor()

        playlists = []

        # Get playlists with no videos in them
        sql = ("SELECT playlists.site, playlists.url, playlists.name, playlists.priority, "
               "channels.url, channels.name, channels.priority, playlists.download "
               "FROM playlists "
               "INNER JOIN channels on playlists.channel=channels.url "
               "WHERE playlists.site = %s "
               "AND playlists.done IS NOT TRUE "
               # "AND playlists.download IS TRUE "
               "AND playlists.monitor IS TRUE "
               "AND NOT EXISTS ( SELECT 1 FROM videos WHERE videos.playlist = playlists.url ) "
               "ORDER BY playlists.priority DESC, EXTRACT(year FROM playlists.date_checked) ASC, "
               "EXTRACT(month FROM playlists.date_checked) ASC, EXTRACT(day FROM playlists.date_checked) ASC, RAND();")
        val = ('youtube',)
        mysql_cursor.execute(sql, val)
        mysql_result = mysql_cursor.fetchall()
        # playlists.append(mysql_result)
        for entry in mysql_result:
            playlists.append(entry)

        # Get playlists with videos present
        sql = ("SELECT playlists.site, playlists.url, playlists.name, playlists.priority, "
               "channels.url, channels.name, channels.priority, playlists.download "
               "FROM playlists "
               "INNER JOIN channels "
               "ON playlists.channel = channels.url "
               "WHERE playlists.site = %s "
               "AND playlists.done IS NOT TRUE "
               # "AND playlists.download IS TRUE "
               "AND playlists.monitor IS TRUE "
               "AND EXISTS ( SELECT 1 FROM videos WHERE videos.playlist = playlists.url ) "
               "ORDER BY playlists.priority DESC, EXTRACT(year FROM playlists.date_checked) ASC, "
               "EXTRACT(month FROM playlists.date_checked) ASC, EXTRACT(day FROM playlists.date_checked) ASC, RAND();")
        val = ('youtube',)
        mysql_cursor.execute(sql, val)
        mysql_result = mysql_cursor.fetchall()
        # playlists.append(mysql_result)
        for entry in mysql_result:
            playlists.append(entry)

        retry_db = False

    return playlists


def get_all_channel_videos_from_youtube(channel):
    get_new_channel_videos_from_youtube(channel=channel,
                                        ignore_errors=DEFAULT_ignore_errors_channel,
                                        archive_set=set())


def get_all_channel_playlists_from_youtube(channel_id, ignore_errors):
    """Returns a list of all online YouTube playlists for the given channel"""
    print(f'{datetime.now()} Collecting playlists for channel "{channel_id}"', end='\r')

    channel_playlists_url = f'https://www.youtube.com/channel/{channel_id}/playlists'

    playlists = []

    # Set download options for YT-DLP
    channel_playlists_download_options = {
        'logger': VoidLogger(),
        'extract_flat': True,
        'skip_download': True,
        'allow_playlist_files': False,
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': ignore_errors,
        'download_archive': None,
        'extractor_args': {'youtube': {'skip': ['configs', 'webpage', 'js']}},
        'extractor_retries': retry_extraction_channel,
        'socket_timeout': timeout_channel,
        'source_address': external_ip
    }

    # Try-Except Block to handle YT-DLP exceptions such as "playlist does not exist"
    try:
        # Run YT-DLP
        with yt_dlp.YoutubeDL(channel_playlists_download_options) as ilus:
            info_json = ilus.sanitize_info(ilus.extract_info(channel_playlists_url, process=True, download=False))

        if DEBUG_channel_playlists:
            with open('debug.json', 'w', encoding='utf-8') as json_file:
                # noinspection PyTypeChecker
                json.dump(info_json, json_file, ensure_ascii=False, indent=4)
            input(f'Dumped JSON... Continue?')

        try:
            playlists = info_json['entries']
            if playlists[0] is not None:
                playlists_count = len(playlists)
                print(f'{datetime.now()} {Fore.GREEN}FOUND{Style.RESET_ALL} {playlists_count} online playlists '
                      f'for channel "{channel_id}"')  # TODO: Improve logging
                return playlists
        except KeyboardInterrupt:
            sys.exit()
        except Exception as e:
            print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} cannot find entries in Info JSON "{info_json}": '
                  f'{e}')
            return None

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_get_online_playlists:
        if not regex_channel_no_playlists.search(str(exception_get_online_playlists)):
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while getting playlists for channel '
                  f'"{channel_id}": {exception_get_online_playlists}')
        return None


def get_all_playlist_videos_from_youtube(playlist):
    get_new_playlist_videos_from_youtube(playlist=playlist,
                                         ignore_errors=DEFAULT_ignore_errors_channel,
                                         archive_set=set(),
                                         counter=0)


def add_playlist_videos(videos):
    for video in videos:
        # TODO
        print(video)


def add_channel_videos(videos):
    for video in videos:
        # TODO
        print(video)


def update_subscriptions():
    global vpn_timestamp
    global vpn_counter
    global global_archive_set

    database_playlists = get_database_playlist_names()

    all_channels = get_monitored_channels_from_db()

    for current_channel in all_channels:
        database = connect_database()

        # TESTING: random new order of countries each channel
        random.shuffle(DEFAULT_vpn_countries)

        current_channel_site = current_channel[0]
        current_channel_id = current_channel[1]
        current_channel_name = current_channel[2]
        videos_added_channel = 0

        unknown_playlists_exist = False

        # Retry getting missing videos for channel from YouTube
        counter_process_channel = 0
        ignore_errors_channel = DEFAULT_ignore_errors_channel
        skip_channel = False
        missing_videos_channel = None
        while missing_videos_channel is None and not skip_channel:
            channel_available = check_channel_availability(channel=current_channel)
            if channel_available:
                # Check if channel has new playlists online that we do not know of
                online_playlists = None
                online_playlists = get_all_channel_playlists_from_youtube(channel_id=current_channel_id,
                                                                          ignore_errors=DEFAULT_ignore_errors_playlist)
                if online_playlists is not None:
                    for online_playlist in online_playlists:
                        # TODO: Add site to query (part of changing to object based list with compare method etc.)
                        online_playlist_site = current_channel_site
                        online_playlist_id = online_playlist['id']
                        online_playlist_name = online_playlist['title']

                        if online_playlist_id not in database_playlists:
                            unknown_playlists_exist = True

                    if unknown_playlists_exist:
                        print(f'{datetime.now()} {Fore.RED}INCOMPLETE{Style.RESET_ALL} '
                              f'channel "{current_channel_name}" ({current_channel_site} {current_channel_id})')
                        if INPUT_POSSIBLE:
                            process_channel(channel_url=f'https://www.youtube.com/channel/{current_channel_id}/videos')
                    else:
                        print(f'{datetime.now()} {Fore.GREEN}COMPLETE{Style.RESET_ALL} '
                              f'channel "{current_channel_name}" ({current_channel_site} {current_channel_id})')

                missing_videos_channel = get_new_channel_videos_from_youtube(channel=current_channel,
                                                                             ignore_errors=ignore_errors_channel,
                                                                             archive_set=global_archive_set)
            counter_process_channel += 1

            if missing_videos_channel is None:
                if counter_process_channel % retry_channel_before_reconnecting_vpn == 0:
                    vpn_counter = reconnect_vpn(counter=vpn_counter)
                    vpn_timestamp = datetime.now()
                if counter_process_channel > retry_channel_before_ignoring_errors:
                    ignore_errors_channel = True
                    print(f'{datetime.now()} {Fore.RED}IGNORING ERRORS{Style.RESET_ALL} after '
                          f'{counter_process_channel} tries while processing channel '
                          f'"{current_channel_name}" ({current_channel_site} {current_channel_id})')
                if counter_process_channel > retry_channel_before_giving_up:
                    print(f'{datetime.now()} {Fore.RED}GIVING UP{Style.RESET_ALL} after '
                          f'{counter_process_channel} tries while processing channel '
                          f'"{current_channel_name}" ({current_channel_site} {current_channel_id})')
                    skip_channel = True

        # noinspection PySimplifyBooleanCheck
        if missing_videos_channel == False:
            print(f'{datetime.now()} {Fore.RED}CRITICAL ERROR{Style.RESET_ALL} while processing channel '
                  f'"{current_channel_name}" ({current_channel_site} {current_channel_id})')
        # After this point we can guarantee the presence of channel video list
        elif missing_videos_channel is not None:
            all_playlists_checked_successfully = True
            missing_video_count_channel = 0
            if type(missing_videos_channel) == list:
                missing_video_count_channel = len(missing_videos_channel)
            if missing_video_count_channel > 0:
                # Get missing videos for channel from MySQL (no retry needed)
                channel_playlists = get_channel_playlists_from_db(channel=current_channel)

                for current_playlist in channel_playlists:
                    counter_process_playlist = 0
                    current_playlist_site = current_playlist[0]
                    current_playlist_id = current_playlist[1]
                    current_playlist_name = current_playlist[2]
                    current_playlist_download = current_playlist[7]
                    current_playlist_checked_successfully = True

                    # If any playlist was not reachable (e.g. given up upon, once we can trust yt-dlp settings fully) do NOT process "Other" playlist!
                    if current_channel_id == current_playlist_id:
                        if not all_playlists_checked_successfully or unknown_playlists_exist:
                            print(f'{datetime.now()} {Fore.YELLOW}SKIPPING{Style.RESET_ALL} uploads playlist for '
                                  f'channel "{current_channel_name}" ({current_playlist_site} {current_channel_id})')
                            current_playlist_checked_successfully = False  # To skip processing in case of skipped "Other" playlist

                    if current_playlist_checked_successfully:  # To skip processing in case of skipped "Other" playlist
                        if DEBUG_add_unmonitored:
                            input(f'{current_playlist_download} - {type(current_playlist_download)}')

                        if videos_added_channel >= missing_video_count_channel:
                            print(f'{datetime.now()} {Fore.GREEN}DONE{Style.RESET_ALL} processing channel '
                                  f'"{current_channel_name}" ({current_playlist_site} {current_channel_id})')
                            break

                        # Retry getting missing videos for playlist from YouTube
                        ignore_errors_playlist = DEFAULT_ignore_errors_playlist
                        skip_playlist = False
                        missing_videos_playlist = None
                        while missing_videos_playlist is None and not skip_playlist:
                            missing_videos_playlist = get_new_playlist_videos_from_youtube(playlist=current_playlist,
                                                                                           ignore_errors=ignore_errors_playlist,
                                                                                           counter=counter_process_playlist,
                                                                                           archive_set=global_archive_set)
                            counter_process_playlist += 1

                            if missing_videos_playlist is None:
                                if counter_process_playlist % retry_playlist_before_reconnecting_vpn == 0:
                                    vpn_counter = reconnect_vpn(counter=vpn_counter)
                                    vpn_timestamp = datetime.now()
                                if counter_process_playlist > retry_playlist_before_ignoring_errors:
                                    ignore_errors_playlist = True
                                    print(f'{datetime.now()} {Fore.RED}IGNORING ERRORS{Style.RESET_ALL} after '
                                          f'{counter_process_playlist} tries while processing playlist '
                                          f'"{current_playlist_name}" ({current_playlist_site} {current_playlist_id})')
                                if counter_process_playlist > retry_playlist_before_giving_up:
                                    print(f'{datetime.now()} {Fore.RED}GIVING UP{Style.RESET_ALL} after '
                                          f'{counter_process_playlist} tries while processing playlist '
                                          f'"{current_playlist_name}" ({current_playlist_site} {current_playlist_id})')
                                    skip_playlist = True
                                    all_playlists_checked_successfully = False
                                    current_playlist_checked_successfully = False

                        # noinspection PySimplifyBooleanCheck
                        if missing_videos_playlist == False:
                            print(f'{datetime.now()} {Fore.RED}CRITICAL ERROR{Style.RESET_ALL} '
                                  f'while processing playlist "'
                                  f'{current_playlist_name}" ({current_playlist_site} {current_playlist_id})')
                        elif missing_videos_playlist is not None:
                            '''After this point we can guarantee the presence of playlist video list'''
                            missing_video_count_playlist = 0
                            if type(missing_videos_playlist) == list:
                                missing_video_count_playlist = len(missing_videos_playlist)
                            if missing_video_count_playlist > 0:
                                for missing_video_playlist in missing_videos_playlist:
                                    # Add video info
                                    video_added = None
                                    skip_video = False
                                    counter_process_video = 0
                                    while video_added is None and not skip_video:

                                        video_added = process_video(channel_site=current_playlist_site,
                                                                    video=missing_video_playlist,
                                                                    channel_id=current_channel_id,
                                                                    playlist_id=current_playlist_id,
                                                                    download=current_playlist_download,
                                                                    archive_set=global_archive_set,
                                                                    database=database)

                                        counter_process_video += 1

                                        if video_added is None:
                                            if counter_process_video > retry_process_video:
                                                try:
                                                    current_video_id = missing_video_playlist['id']
                                                except KeyboardInterrupt:
                                                    sys.exit()
                                                except Exception as e:
                                                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} '
                                                          f'getting id from video "{missing_video_playlist}": {e}')
                                                    current_video_id = missing_video_playlist

                                                print(f'{datetime.now()} {Fore.RED}GIVING UP{Style.RESET_ALL} after '
                                                      f'{counter_process_video} tries while processing video "{current_video_id}"')
                                                skip_video = True

                                    if video_added:
                                        videos_added_channel += 1

                    # Playlist is updated after
                    # A: All videos have been processed or already known
                    # B: The playlist had no (new) videos
                    if current_playlist_checked_successfully:
                        playlist_updated = False
                        while not playlist_updated:
                            playlist_updated = update_playlist(
                                date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                playlist=current_playlist,
                                database=database)
                            if not playlist_updated:
                                database = connect_database()
                    else:
                        print(f'{datetime.now()} {Fore.RED}INCOMPLETE CHECK{Style.RESET_ALL} on playlist '
                              f'"{current_playlist_name}" ({current_playlist_site} {current_playlist_id})')

            # Channel is updated after
            # A: All playlists have been checked to completion (<= all videos was found on playlists)
            # B: All new channel videos have been found on a playlist
            # C: The channel had no new videos
            if all_playlists_checked_successfully:
                channel_updated = False
                while not channel_updated:
                    channel_updated = update_channel(date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                                     channel=current_channel,
                                                     database=database)
                    if not channel_updated:
                        database = connect_database()
            else:
                print(f'{datetime.now()} {Fore.RED}INCOMPLETE CHECK{Style.RESET_ALL} on channel '
                      f'"current_channel_name" ({current_channel_site} {current_channel_id})')


# TODO: This is redundant and needs to be merged with get_monitored_channels_from_db()
def get_database_channel_names():
    """
    Returns a list of all known YouTube channels
    Field order:
        - channels.url
        - channels.name
    """

    print(f'{datetime.now()} Collecting channel names...', end='\r')

    mydb = mysql.connector.connect(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database)

    mysql_cursor = mydb.cursor()

    sql = ("select channels.url, channels.name FROM channels "
           "WHERE site = %s AND url not like '%#%'"
           "AND channels.url IN("
           "SELECT playlists.channel FROM playlists "
           "WHERE playlists.done IS NOT TRUE "
           "AND playlists.monitor IS TRUE "
           "GROUP BY playlists.channel HAVING count(*) > 0) "
           ";")
    val = ('youtube',)  # DO NOT REMOVE COMMA, it is necessary for MySQL to work!
    mysql_cursor.execute(sql, val)
    mysql_result = mysql_cursor.fetchall()

    return dict(mysql_result)


# TODO: This is redundant and needs to be merged with get_monitored_playlists_from_db()
def get_database_playlist_names():
    """
    Returns a list of all known YouTube playlists
        Field order:
            - playlists.url
            - playlists.name
    """
    print(f'{datetime.now()} Collecting playlists...', end='\r')

    mydb = mysql.connector.connect(
        host=mysql_host,
        user=mysql_user,
        password=mysql_password,
        database=mysql_database)

    mysql_cursor = mydb.cursor()

    sql = "select playlists.url, playlists.name from playlists WHERE site = %s;"
    val = ('youtube',)  # DO NOT REMOVE COMMA, it is necessary for MySQL to work!
    mysql_cursor.execute(sql, val)
    mysql_result = mysql_cursor.fetchall()

    return dict(mysql_result)


def add_subscriptions():
    database_channels = get_database_channel_names()
    database_playlists = get_database_playlist_names()

    channel_list = []

    use_database = None
    while use_database is None:
        use_database_input = input(f'Check playlists for all existing channels? '
                                   f'{Fore.GREEN}Y{Style.RESET_ALL} or '
                                   f'{Fore.RED}N{Style.RESET_ALL}: ')
        if use_database_input.lower() == 'y':
            use_database = True
        elif use_database_input.lower() == 'n':
            use_database = False
        else:
            continue

    if use_database:
        for database_channel in database_channels:
            channel_list.append(f'https://www.youtube.com/channel/{database_channel}/videos')
    else:
        channel_url = input(f'Enter CHANNEL URL: ')
        channel_list.append(channel_url)

    for channel_url in channel_list:
        process_channel(channel_url=channel_url,
                        database_channels=database_channels,
                        database_playlists=database_playlists)


def process_channel(channel_url, database_channels=None, database_playlists=None):
    if not database_channels:
        database_channels = get_database_channel_names()
    if not database_playlists:
        database_playlists = get_database_playlist_names()

    channel = get_channel_details(channel_url=channel_url, ignore_errors=DEFAULT_ignore_errors_channel)
    print()
    try:
        channel_id = channel['id']
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_get_channel_id:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} {exception_get_channel_id}')
        return False

    channel_name_online = channel['channel']

    if channel_id in database_channels:
        channel_name_sane = database_channels[channel_id]
        print(f'{datetime.now()} Channel known as "{channel_name_sane}"')
    else:
        channel_name_sane = sanitize_name(name=channel_name_online)
        channel_name_input = input(f'ENTER to keep default or type to change CHANNEL name: ')

        if channel_name_input:
            channel_name_sane = sanitize_name(name=channel_name_input, is_user=True)

        add_channel(channel_id=channel_id, channel_name=channel_name_sane)

    if channel_id in database_playlists:
        print(
            f'{datetime.now()} {Fore.CYAN}ATTENTION{Style.RESET_ALL} All "Other" videos are already being downloaded!')

    online_playlists = None
    online_playlists = get_all_channel_playlists_from_youtube(channel_id=channel_id,
                                                              ignore_errors=DEFAULT_ignore_errors_playlist)

    if online_playlists is not None:
        for online_playlist in online_playlists:
            print()

            playlist_id = online_playlist['id']
            playlist_name_online = online_playlist['title']

            if playlist_id in database_playlists:
                playlist_name_sane = database_playlists[playlist_id]
                if playlist_name_sane is not None:
                    print(f'{datetime.now()} Playlist known as "{playlist_name_sane}"')
                else:
                    print(f'{datetime.now()} Playlist with ID "{playlist_id}" was ignored forever!')
            else:
                playlist_name_sane = sanitize_name(name=playlist_name_online)
                skip_playlist = False
                while not skip_playlist:
                    add_playlist_input = input(
                        f'What do you want to do with "{playlist_name_sane}" ({playlist_id})? '
                        f'{Fore.GREEN}D{Style.RESET_ALL}ownload immediately, '
                        f'{Fore.YELLOW}M{Style.RESET_ALL}onitor only or '
                        f'{Fore.RED}I{Style.RESET_ALL}gnore forever: ')
                    if add_playlist_input.lower() == 'd':
                        monitor_playlist = True
                        download_playlist = True
                    elif add_playlist_input.lower() == 'm':
                        monitor_playlist = True
                        download_playlist = False
                    elif add_playlist_input.lower() == 'i':
                        monitor_playlist = False
                        download_playlist = None
                    else:
                        continue

                    if monitor_playlist:
                        playlist_name_input = input(f'ENTER to keep default or type to change PLAYLIST name: ')
                        if playlist_name_input:
                            playlist_name_sane = sanitize_name(name=playlist_name_input, is_user=True)
                    else:
                        playlist_name_sane = None

                    add_playlist(playlist_id=playlist_id, playlist_name=playlist_name_sane, channel_id=channel_id,
                                 download=download_playlist, monitor=monitor_playlist)
                    skip_playlist = True

    # Handle "Other" playlist (channel video feed)
    playlist_id = channel_id
    playlist_name_online = 'Other'
    print(
        f'{datetime.now()} {Fore.CYAN}ATTENTION{Style.RESET_ALL} "Other" Playlist should only be added for channels where most videos are not on playlists!')

    if playlist_id in database_playlists:
        playlist_name_sane = database_playlists[playlist_id]
        if playlist_name_sane is not None:
            print(f'{datetime.now()} Playlist known as "{playlist_name_sane}"')
        else:
            print(f'{datetime.now()} Playlist with ID "{playlist_id}" was ignored forever!')
    else:
        playlist_name_sane = sanitize_name(name=playlist_name_online)
        skip_playlist = False
        while not skip_playlist:
            add_playlist_input = input(f'What do you want to do with "{playlist_name_sane}" ({playlist_id})? '
                                       f'{Fore.GREEN}D{Style.RESET_ALL}ownload immediately, '
                                       f'{Fore.YELLOW}M{Style.RESET_ALL}onitor only or '
                                       f'{Fore.RED}I{Style.RESET_ALL}gnore forever: ')
            if add_playlist_input.lower() == 'd':
                monitor_playlist = True
                download_playlist = True
            elif add_playlist_input.lower() == 'm':
                monitor_playlist = True
                download_playlist = False
            elif add_playlist_input.lower() == 'i':
                monitor_playlist = False
                download_playlist = None
            else:
                continue

            if monitor_playlist:
                playlist_name_input = input(f'ENTER to keep default or type to change PLAYLIST name: ')
                if playlist_name_input:
                    playlist_name_sane = sanitize_name(name=playlist_name_input, is_user=True)
            else:
                playlist_name_sane = None

            add_playlist(playlist_id=playlist_id, playlist_name=playlist_name_sane, channel_id=channel_id,
                         download=download_playlist, monitor=monitor_playlist)
            skip_playlist = True


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Zahhak")
    parser.add_argument("--mode",
                        choices=('A', 'D', 'M'),
                        help="'A' for Add Subscriptions, "
                             "'D' for Download Media, "
                             "'M' for Monitor Subscriptions, "
                             "EMPTY to run in serial mode. ",
                        type=str,
                        required=False)
    args = parser.parse_args()

    init(convert=True)
    just_fix_windows_console()

    # Skips ALL processing of known videos to speed up skript
    create_download_archive()

    if not args.mode:
        INPUT_POSSIBLE = True
        print(f'{datetime.now()} {Fore.YELLOW}WARNING{Style.RESET_ALL}: '
              f'no operating mode was set. Running in user interactive mode!')
        while True:
            add_subscriptions()
            update_subscriptions()
            download_all_videos()
    elif len(args.mode) == 1:
        INPUT_POSSIBLE = False
        if args.mode == 'D':
            while True:
                print(f'{datetime.now()} {Fore.CYAN}MODE{Style.RESET_ALL}: '
                      f'Download Media')
                download_all_videos()
        elif args.mode == 'M':
            while True:
                print(f'{datetime.now()} {Fore.CYAN}MODE{Style.RESET_ALL}: '
                      f'Monitor Subscriptions')
                update_subscriptions()
        elif args.mode == 'A':
            while True:
                print(f'{datetime.now()} {Fore.CYAN}MODE{Style.RESET_ALL}: '
                      f'Add Subscriptions')
                add_subscriptions()
        else:
            print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL}: '
                  f'No mode "{args.mode}" exists')
    else:
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL}: '
              f'Malformed arguments found!')
