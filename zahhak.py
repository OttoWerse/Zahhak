import argparse
import io
import json
import math
import os
import random
import re
import shutil
import sys
import time
from datetime import datetime
from faulthandler import enable
from subprocess import STDOUT, check_output, Popen, PIPE

import lxml.builder
import lxml.etree
import mysql.connector
import yt_dlp
from colorama import init, Fore, Style, just_fix_windows_console

# TODO https://www.reddit.com/r/youtubedl/comments/1berg2g/is_repeatedly_downloading_api_json_necessary/

'''Directory settings'''
directory_download_temp = os.getenv('ZAHHAK_DIR_DOWNLOAD_TEMP')
directory_download_home = os.getenv('ZAHHAK_DIR_DOWNLOAD_HOME')
directory_final = os.getenv('ZAHHAK_DIR_FINAL')  # TODO: How to handle multiple final directories?

'''MySQL settings'''
mysql_host = os.getenv('ZAHHAK_MYSQL_HOSTNAME', 'localhost')
mysql_database = os.getenv('ZAHHAK_MYSQL_DATABASE', 'zahhak')
mysql_user = os.getenv('ZAHHAK_MYSQL_USERNAME', 'admin')
mysql_password = os.getenv('ZAHHAK_MYSQL_PASSWORD', 'admin')

'''Variables'''
# Frequency to reconnect VPN (in seconds)
sleep_time_vpn = 10
# How often to retry connecting to a VPN country before giving up
retry_reconnect_new_vpn_node = 5
# Frequency to check if switch from downloading secondary to primary media is needed (in seconds)
select_newest_media_frequency = 300
# How long to wait after all verified media has been moved into final directory
sleep_time_move_in = 300
# Create a NFO file with data needed for presentation in Jellyfin/Emby
create_nfo_files = True
if create_nfo_files:
    sleep_time_fix_nfo = 0
else:
    sleep_time_fix_nfo = 90
# Mass create all NFO files in final directory - Should be False for normal runs!
fix_all = False
# Replace existing NFO files (for mass-updating format) - Should be False for normal runs!
replace_existing = False
# This is a hotfix for "EXISTING NFO" piling up (IDK why the move after NFO creation fails so often)
keep_existing = True
# Maximum total amount of missing frames to tolerate
error_limit_missing = 1
# Maximum total amount of extra frames to tolerate
error_limit_extra = 1
# Cutoff to switch between relative tolerances for short and long media
duration_cutoff = 60
# Relative error tolerance for short media (below cutoff)
tolerance_short = 0.11
# Relative error tolerance for long media (above cutoff)
tolerance_long = 0.035
# How long to wait after all media has been verified
sleep_time_verification = 150

# Countries to connect to with NordVPN
DEFAULT_vpn_countries = [
    'Afghanistan',
    'Albania',
    'Algeria',
    'Andorra',
    'Angola',
    'Argentina',
    'Armenia',
    'Australia',
    'Austria',
    'Azerbaijan',
    'Bahamas',
    'Bahrain',
    'Bangladesh',
    'Belgium',
    'Belize',
    'Bermuda',
    'Bhutan',
    'Bolivia',
    'Bosnia and Herzegovina',
    'Brazil',
    'Brunei Darussalam',
    'Bulgaria',
    'Cambodia',
    'Canada',
    'Cayman Islands',
    'Chile',
    'Colombia',
    'Comoros',
    'Costa Rica',
    'Croatia',
    'Cyprus',
    'Czech Republic',
    'Denmark',
    'Dominican Republic',
    'Egypt',
    'El Salvador',
    'Ecuador',
    'Estonia',
    'Ethiopia',
    'Finland',
    'France',
    'Georgia',
    'Germany',
    'Ghana',
    'Greece',
    'Greenland',
    'Guam',
    'Guatemala',
    'Honduras',
    'Hong Kong',
    'Hungary',
    'Iceland',
    'India',
    'Ireland',
    'Isle of Man',
    'Israel',
    'Italy',
    'Jamaica',
    'Japan',
    'Jersey',
    'Jordan',
    'Kazakhstan',
    'Kenya',
    'Kuwait',
    'Latvia',
    'Lebanon',
    'Libyan Arab Jamahiriya',
    'Liechtenstein',
    'Lithuania',
    'Luxembourg',
    'Malaysia',
    'Malta',
    'Mauritania',
    'Mexico',
    'Moldova',
    'Monaco',
    'Mongolia',
    'Montenegro',
    'Morocco',
    'Mozambique',
    'Myanmar',
    'Nepal',
    'Netherlands',
    'New Zealand',
    'Nigeria',
    'North Macedonia',
    'Norway',
    'Pakistan',
    'Panama',
    'Papua New Guinea',
    'Paraguay',
    'Peru',
    'Philippines',
    'Poland',
    'Portugal',
    'Puerto Rico',
    'Qatar',
    'Romania',
    'Rwanda',
    'Senegal',
    'Serbia',
    'Singapore',
    'Slovakia',
    'Slovenia',
    'Somalia',
    'South Africa',
    'South Korea',
    'Spain',
    'Sri Lanka',
    'Sweden',
    'Switzerland',
    'Taiwan',
    'Thailand',
    'Trinidad and Tobago',
    'Tunisia',
    'Turkey',
    'Ukraine',
    'United Arab Emirates',
    'United Kingdom',
    'United States',
    'Uruguay',
    'Uzbekistan',
    'Venezuela',
    'Vietnam',
]

GEO_BLOCKED_vpn_countries = []

# Timeout connecting VPN
timeout_vpn = 15

# Timeout for channel home page extraction (in seconds)
timeout_check_channel = 6
# YT-DLP internal retry for channel home page extraction
retry_extraction_check_channel = 0

# Timeout for loading channel uploads playlist extraction (in seconds)
timeout_channel = 48
# YT-DLP internal retry for channel uploads playlist extraction
retry_extraction_channel = 2
# Times to try channel processing before reconnecting NordVPN (if enabled) - this repeats every X tries!
retry_channel_before_reconnecting_vpn = 1
# Times to try full channel uploads playlist processing before switching to using ignore_errors to accept partial processing
retry_channel_before_ignoring_errors = len(DEFAULT_vpn_countries) * 1 * retry_channel_before_reconnecting_vpn
# Times to try channel uploads playlist processing before giving up entirely
retry_channel_before_giving_up = len(DEFAULT_vpn_countries) * 2 * retry_channel_before_reconnecting_vpn  #

# Timeout for channel uploads playlist extraction (in seconds)
timeout_playlist = 24
# YT-DLP internal retry for full playlist page extraction
retry_extraction_playlist = 2
# Times to try playlist page processing before reconnecting NordVPN (if enabled) - this repeats every X tries!
retry_playlist_before_reconnecting_vpn = 1
# Times to try full playlist page processing before switching to using ignore_errors to accept partial processing
retry_playlist_before_ignoring_errors = len(DEFAULT_vpn_countries) * 1 * retry_playlist_before_reconnecting_vpn
# Times to try playlist page processing before giving up entirely
retry_playlist_before_giving_up = len(DEFAULT_vpn_countries) * 2 * retry_playlist_before_reconnecting_vpn  #

# Timeout for media page extraction (in seconds)
timeout_media = 12
# YT-DLP internal retry for media page extraction
retry_extraction_media = 2
# Times to try media page processing before giving up entirely
retry_process_media = 2

# Timeout for media download (in seconds)
timeout_download = 12
# YT-DLP internal retry for media download
retry_extraction_download = 2

# Sleep time after failed MySQL requests (in seconds)
sleep_time_mysql = 3

# Sleep time when there is no more media to download (in seconds)
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
extract_flat_playlist = True  # TODO: just reconnect_vpn upon bot detection - Previous comment: Leave as False to avoid extraction of every single media AFTER playlist (often detected as bot!)

# Availability Filter
# filter_availability = 'availability=public,unlisted,needs_auth,subscriber_only,premium_only'
filter_availability = 'availability=public,unlisted '
# TODO: Neither of these filters work for actually filtering shorts on the playlist/channel level!
# filter_shorts = '& tags !*= shorts & original_url!=/shorts/ & url!=/shorts/ '
filter_shorts = '& media_type != short '
filter_livestream_current = '& !is_live '
filter_livestream_recording = '& !was_live '

# Set ignore error options
# False --> Getting full list of media ends when one will not load, is private, is age restricted, etc. we get NO list of media at all!
# TODO: Look into what happens if you use False, catch an error like "Private Video" and then do nothing with it. e.g. will yt-dlp continue on
# TODO: Maybe revert to ignoring errors on channel pages for faster runs? (channels will be checked frequently, and new media should always be on 1st page. Eventually we will get a full list, given enough reruns)
# TODO: IDK if this can be made to work so private media etc. are filtered out using filter, we need to TEST this!
DEFAULT_ignore_errors_channel = False
DEFAULT_ignore_errors_playlist = False
# 'only_download' --> We do not always get a full list of media, but at least we get A list at all!
# DEFAULT_ignore_errors_channel           = 'only_download'
# DEFAULT_ignore_errors_playlist          = 'only_download'

'''Media Types'''
download_shorts = False
download_livestreams = False

'''STRINGS'''
playlist_name_shorts = 'Shorts'
playlist_name_livestreams = 'Livestreams'

'''Error messages REGEX'''
# Channel
regex_channel_no_media = re.compile(r'This channel does not have a videos tab')
regex_channel_no_playlists = re.compile(r'This channel does not have a playlists tab')
regex_channel_unavailable = re.compile(r'This channel is not available')
regex_channel_removed = re.compile(r'This channel was removed because it violated our Community Guidelines')
regex_channel_deleted = re.compile(r'This channel does not exist')
# Playlist
regex_playlist_deleted = re.compile(r'The playlist does not exist')
# Media
regex_media_format_unavailable = re.compile(r'Requested format is not available')
regex_media_private = re.compile(r'Private video')
regex_media_removed = re.compile(r'This video has been removed')
regex_media_unavailable = re.compile(r'Video unavailable')
regex_media_unavailable_live = re.compile(r'This live stream recording is not available')
regex_media_unavailable_geo = re.compile(r'The uploader has not made this video available in your country')
regex_media_unavailable_geo_fix = re.compile(r'(?<=This video is available in ).*(?<!\.)')
regex_media_age_restricted = re.compile(r'Sign in to confirm your age')
regex_media_members_only = re.compile(r'Join this channel to get access to members-only content like this video')
regex_media_members_tier = re.compile(r'This video is available to this channel.s members on level')
regex_media_paid = re.compile(r'This video requires payment to watch')
regex_media_live_not_started = re.compile(r'This live event will begin in a few moments')
# Networking
regex_bot = re.compile(r"Sign in to confirm you.re not a bot")
regex_offline = re.compile(r"Offline")
regex_error_timeout = re.compile(r'The read operation timed out')
regex_error_get_addr_info = re.compile(r'getaddrinfo failed')
regex_error_connection = re.compile(r'Remote end closed connection without response')
regex_error_http_403 = re.compile(r'HTTP Error 403')
# Storage
regex_json_write = re.compile(r'Cannot write video metadata to JSON file')
regex_error_win_2 = re.compile(r'WinError 2')
regex_error_win_5 = re.compile(r'WinError 5')
regex_error_win_32 = re.compile(r'WinError 32')
regex_error_win_10054 = re.compile(r'WinError 10054')
# MySQL
regex_sql_duplicate = re.compile(r'Duplicate entry')
regex_sql_unavailable = re.compile(r'MySQL Connection not available')

'''Other REGEX'''
# Channel names
regex_live_channel = re.compile(r'.* LIVE$')
regex_fake_channel = re.compile(r'^#.*$')
regex_fake_playlist = re.compile(r'^#.*$')
regex_handle_as_id = re.compile(r'^@.*$')
# noinspection RegExpRedundantEscape
regex_val = re.compile(r'[^\.a-zA-Z0-9 -]')
regex_caps = re.compile(r'[A-Z][A-Z]+')
# File extensions
regex_mp4 = re.compile(r'\.mp4$')
regex_json = re.compile(r'\.info\.json$')
regex_nfo = re.compile(r'\.nfo$')
regex_show_nfo = re.compile(r'^tvshow\.nfo$')
regex_season_nfo = re.compile(r'^season\.nfo$')
# NFO components
# noinspection RegExpRedundantEscape
regex_date_present = re.compile(r'<aired>\d{4}-\d{2}-\d{2}<\/aired>')
# noinspection RegExpRedundantEscape
regex_date_value = re.compile(r'(?<=<aired>)(.*)(?=<\/aired>)')
# noinspection RegExpRedundantEscape
regex_date_add_position = re.compile(r'(?<=<\/season>).*')
# noinspection RegExpRedundantEscape
regex_network_present = re.compile(r'<studio>.*<\/studio>')
# noinspection RegExpRedundantEscape
regex_network_value = re.compile(r'(?<=<studio>)(.*)(?=<\/studio>)')
# noinspection RegExpRedundantEscape
regex_network_add_position = re.compile(r'(?<=<\/runtime>).*')

'''Status values'''
STATUS = {'unwanted': 'unwanted',
          'wanted': 'wanted',
          'paid': 'paid',
          'members-only': 'members-only',
          'age-restricted': 'age-restricted',
          'unavailable': 'unavailable',
          'private': 'private',
          'removed': 'removed',
          'verified': 'verified',
          'uncertain': 'uncertain',
          'broken': 'broken',
          'cursed': 'cursed',
          'fresh': 'fresh',
          'stuck': 'stuck',
          'done': 'done',
          }

'''DEBUG'''
DEBUG_empty_media = False
DEBUG_add_media = False
DEBUG_force_date = False
DEBUG_log_date_fields_missing = False
DEBUG_unavailable = False
DEBUG_update_channel = False
DEBUG_update_playlist = False
DEBUG_json_channel = False
DEBUG_json_check_channel = False
DEBUG_json_playlist = False
DEBUG_json_media_add = False
DEBUG_json_media_details = False
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
DEFAULT_vpn_frequency = 60  # TODO: recheck if can be reached continuously until timeout is reached instead of just waiting. Possibly split this into two values, one for the new and one for the old functionality. Plus also wait time before even trying to get media after trying to reconnect vpn!
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
    """Uses MySQL database to build a list of all known media IDs and writes them to YT-DLP archive file"""
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
    except Exception as exception_missing_media_channel:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while getting fields from channel '
              f'"{channel}": {exception_missing_media_channel}')
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
    except Exception as exception_missing_media_channel:
        if regex_channel_no_media.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}EMPTY{Style.RESET_ALL} channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            # TODO: return special case?
            return True
        elif regex_error_connection.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}CLOSED CONNECTION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        elif regex_error_timeout.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}TIME OUT{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        elif regex_error_get_addr_info.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}GET ADDR INFO FAILED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        elif regex_error_win_10054.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}CONNECTION CLOSED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        elif regex_channel_unavailable.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}GEO BLOCKED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = GEO_BLOCKED_vpn_frequency
            return False
        elif regex_channel_removed.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}GUIDELINE VIOLATION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        elif regex_channel_deleted.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}NONEXISTENT{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        else:
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id}): {exception_missing_media_channel}')
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


def get_new_channel_media_from_youtube(channel, ignore_errors, archive_set):
    """Returns media IDs not present in MySQL database for given channel"""
    global vpn_frequency

    try:
        channel_site = channel[0]
        channel_id = channel[1]
        channel_name = channel[2]
        print(f'{datetime.now()} Checking download state of channel "{channel_name}" ({channel_site} {channel_id})',
              end='\r')

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_missing_media_channel:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while getting fields from channel '
              f'"{channel}": {exception_missing_media_channel}')
        return None

    if regex_fake_channel.search(channel_id):
        print(f'{datetime.now()} {Fore.YELLOW}WARNING{Style.RESET_ALL}: Channel '
              f'"{channel_name}" ({channel_site} {channel_id}) is not a real channel')
        # TODO: Update checked date? Return number etc. and in this case, return special case?
        return ['FAKE']

    # Filter out members only content on the channel level
    filter_text = filter_availability

    # Set channel URL
    # channel_url = f'https://www.youtube.com/channel/{channel_id}/media'
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
    except Exception as exception_missing_media_channel:
        if regex_channel_no_media.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}EMPTY{Style.RESET_ALL} channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            # TODO: Update checked date? Return number etc. and in this case, return special case?
            return []
        elif regex_playlist_deleted.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}EMPTY{Style.RESET_ALL}'
                  f' channel "{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return []
        elif regex_error_connection.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}CLOSED CONNECTION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        elif regex_error_timeout.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}TIME OUT{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        elif regex_error_get_addr_info.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}GET ADDR INFO FAILED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        elif regex_error_win_10054.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}CONNECTION CLOSED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        elif regex_channel_unavailable.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}GEO BLOCKED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = GEO_BLOCKED_vpn_frequency
            return None
        elif regex_channel_removed.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}GUIDELINE VIOLATION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        elif regex_channel_deleted.search(str(exception_missing_media_channel)):
            print(f'{datetime.now()} {Fore.RED}NONEXISTENT{Style.RESET_ALL} '
                  f'channel "{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        else:
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id}): {exception_missing_media_channel}')
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
            media = info_json['entries']
            if type(media) == list:
                if media == [None]:
                    media = []
            media_count = len(media)
            if media_count > 0:
                print(f'{datetime.now()} {Fore.GREEN}FOUND{Style.RESET_ALL} {media_count} new media for channel '
                      f'"{channel_name}" ({channel_site} {channel_id})       ')
            else:
                print(f'{datetime.now()} {Fore.CYAN}NO{Style.RESET_ALL} new media for channel '
                      f'"{channel_name}" ({channel_site} {channel_id})')

            return media
        else:
            # TODO: IDK if channel handling in main can handle this, so I am just sending None as in other error cases
            # return False
            return None

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_missing_media_channel:
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} no entries in "{info_json}" '
              f'({exception_missing_media_channel})')
        return None


def get_new_playlist_media_from_youtube(playlist, ignore_errors, counter, archive_set):
    """Returns list of missing media as objects in given playlist"""

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
        # TODO: get this info into add_media method?
        filter_text = (filter_availability + filter_livestream_current + filter_shorts)
    elif playlist_name == playlist_name_shorts:
        print(f'{datetime.now()} {Fore.CYAN}SHORTS{Style.RESET_ALL} playlist '
              f'"{playlist_name}" ({playlist_site} {playlist_id})')
        # TODO: get this info into add_media method?
        filter_text = (filter_availability + filter_livestream_current + filter_livestream_recording)
    else:
        filter_text = (filter_availability + filter_livestream_current + filter_livestream_recording + filter_shorts)

    # Set playlist URL
    # User Channel
    if re.search("^UC.*$", playlist_id):
        # Standard format for YouTube channel IDs
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
    except Exception as exception_missing_media_playlist:
        if regex_playlist_deleted.search(str(exception_missing_media_playlist)):
            print(f'{datetime.now()} {Fore.RED}DELETED{Style.RESET_ALL} playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id})')
            # TODO: Return number etc. and in this case, return special case?
            return []
        elif regex_error_connection.search(str(exception_missing_media_playlist)):
            print(f'{datetime.now()} {Fore.RED}CLOSED CONNECTION{Style.RESET_ALL} while adding playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id})')
            return None
        elif regex_error_timeout.search(str(exception_missing_media_playlist)):
            print(f'{datetime.now()} {Fore.RED}TIME OUT{Style.RESET_ALL} while adding playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id})')
            return None
        elif regex_error_get_addr_info.search(str(exception_missing_media_playlist)):
            print(f'{datetime.now()} {Fore.RED}GET ADDR INFO FAILED{Style.RESET_ALL} while adding playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id})')
            return None
        elif regex_error_win_10054.search(str(exception_missing_media_playlist)):
            print(f'{datetime.now()} {Fore.RED}CONNECTION CLOSED{Style.RESET_ALL} while adding playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id})')
            return None
        else:
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding playlist '
                  f'"{playlist_name}" ({playlist_site} {playlist_id}): {exception_missing_media_playlist}')
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
            media = info_json['entries']
            if type(media) == list:
                if media == [None]:
                    media = []
            media_count = len(media)
            if media_count > 0:
                print(f'{datetime.now()} {Fore.GREEN}FOUND{Style.RESET_ALL} {media_count} new media for playlist '
                      f'"{playlist_name}" ({playlist_site} {playlist_id})')
            else:
                print(f'{datetime.now()} {Fore.CYAN}NO{Style.RESET_ALL} new media for playlist '
                      f'"{playlist_name}" ({playlist_site} {playlist_id})')

            return media
        else:
            # TODO: IDK if playlist handling in main can handle this, so I am just sending None as in other error cases
            # return False
            return None

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_missing_media_playlist:
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} no entries in "{info_json}" '
              f'({exception_missing_media_playlist})')
        # TODO: Return false for now to stop retry. In case of exception in YT-DLP we still return None. Ignore Errors "Only Download" could cause issues here!
        return False
        # TODO: To make this work properly, we need to count retries and give up at some point, I guess?
        # return [] # This is to stop repeating to try in this (rare) case of not getting entries for playlist EVER (cause unknown, possibly related to single media lists or hidden media etc.)


def get_monitored_channels_from_db(database, regex_channel_url=fr'^UC[a-z0-9\-\_]'):
    """Returns a list of all known YouTube channels als list of lists
    Inner list field order is as follows:
      - channels.site
      - channels.url
      - channels.name
      - channels.priority"""

    print(f'{datetime.now()} {Fore.GREEN}SELECTING{Style.RESET_ALL} channels '
          f'matching ID regex {regex_channel_url}',
          end='\n')
    mysql_cursor = database.cursor()

    sql = ("SELECT channels.site, channels.url, channels.name, channels.priority "
           "FROM channels "
           "WHERE site = %s "
           "AND (LOWER(channels.url) REGEXP %s)"
           "AND channels.url IN("
           "SELECT playlists.channel FROM playlists "
           "WHERE playlists.done IS NOT TRUE "
           # "AND playlists.download IS TRUE "
           "AND playlists.monitor IS TRUE "
           "GROUP BY playlists.channel HAVING count(*) > 0) "
           "ORDER BY channels.priority DESC, EXTRACT(year FROM channels.date_checked) ASC, "
           "EXTRACT(month FROM channels.date_checked) ASC, EXTRACT(day FROM channels.date_checked) ASC, "
           "EXTRACT(hour FROM channels.date_checked) ASC, RAND();")
    val = ('youtube', regex_channel_url)
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


def get_media_details_from_youtube(media_id, ignore_errors, archive_set):
    """Fills the details for media by its ID"""
    global vpn_frequency
    local_vpn_counter = 0
    done = False

    while not done:
        # Try-Except Block to handle YT-DLP exceptions such as "playlist does not exist"
        try:
            media_url = f'https://www.youtube.com/watch?v={media_id}'

            # Set download options for YT-DLP
            media_download_options = {
                'logger': VoidLogger(),
                'skip_download': True,
                'allow_playlist_files': False,
                'cachedir': False,
                'ignoreerrors': ignore_errors,
                'download_archive': archive_set,
                'extractor_args': {'youtube': {'skip': ['configs', 'webpage', 'js']}},
                'extractor_retries': retry_extraction_media,
                'socket_timeout': timeout_media,
                'source_address': external_ip
            }

            # Run YT-DLP
            with yt_dlp.YoutubeDL(media_download_options) as ilus:
                info_json = ilus.sanitize_info(ilus.extract_info(media_url, process=True, download=False))

            if DEBUG_json_media_details:
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
                local_vpn_counter = reconnect_vpn(counter=local_vpn_counter)

            else:
                # print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while getting details for media "{media_id}": {e}')
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
                return None
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
            # return [] # This is to stop repeating to try in this (rare) case of not getting entries for playlist EVER (cause unknown, possibly related to single media lists or hidden media etc.)

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


def get_text_color_for_media_status(media_status):
    # Set text_color for media status
    text_color = Fore.WHITE
    if media_status == STATUS['private']:
        text_color = Fore.RED
    elif media_status == STATUS['removed']:
        text_color = Fore.RED
    elif media_status == STATUS['age-restricted']:
        text_color = Fore.RED
    elif media_status == STATUS['cursed']:
        text_color = Fore.RED
    elif media_status == STATUS['unavailable']:
        text_color = Fore.RED
    elif media_status == STATUS['broken']:
        text_color = Fore.YELLOW
    elif media_status == STATUS['members-only']:
        text_color = Fore.YELLOW
    elif media_status == STATUS['uncertain']:
        text_color = Fore.YELLOW
    elif media_status == STATUS['wanted']:
        text_color = Fore.CYAN
    elif media_status == STATUS['unwanted']:
        text_color = Fore.CYAN
    elif media_status == STATUS['verified']:
        text_color = Fore.GREEN
    elif media_status == STATUS['done']:
        text_color = Fore.GREEN
    elif media_status == STATUS['fresh']:
        text_color = Fore.GREEN

    return text_color


def add_media(media_site, media_id, channel, playlist, media_status, media_available_date, download, database=None):
    """Adds a media to given playlist & channel in database with the given status fields"""
    if not database:
        database = connect_database()

    global global_archive_set

    mysql_cursor = database.cursor()
    sql = ("INSERT INTO videos(site, url, channel, playlist, status, original_date, download) "
           "VALUES(%s, %s, %s, %s, %s, %s, %s) "
           "ON DUPLICATE KEY UPDATE status = VALUES(status);")
    val = (media_site, media_id, channel, playlist, media_status, media_available_date, download)
    mysql_cursor.execute(sql, val)
    database.commit()

    text_color = get_text_color_for_media_status(media_status=media_status)

    if f'{media_site} {media_id}' in global_archive_set:
        print(f'{datetime.now()} {Fore.GREEN}UPDATED{Style.RESET_ALL} media "{media_site} {media_id}" '
              f'to status {text_color}"{media_status}"{Style.RESET_ALL}')
    else:
        global_archive_set.add(f'{media_site} {media_id}')
        print(f'{datetime.now()} {Fore.GREEN}ADDED{Style.RESET_ALL} media "{media_site} {media_id}" '
              f'with status {text_color}"{media_status}"{Style.RESET_ALL}')


def update_media_status(media_site, media_id, media_status, database=None):
    if not database:
        database = connect_database()

    mysql_cursor = database.cursor()
    sql = "UPDATE videos SET status = %s WHERE site = %s AND url = %s;"
    val = (media_status, media_site, media_id,)
    mysql_cursor.execute(sql, val)
    database.commit()

    text_color = get_text_color_for_media_status(media_status=media_status)
    print(f'{datetime.now()} {Fore.GREEN}UPDATED{Style.RESET_ALL} media "{media_site} {media_id}" '
          f'to status {text_color}"{media_status}"{Style.RESET_ALL}')


def process_media(media, channel_site, channel_id, playlist_id, download, archive_set, database):
    """Processes media and adds it to database depending on results and settings"""
    if DEBUG_json_media_add:
        with open('debug.json', 'w', encoding='utf-8') as json_file:
            # noinspection PyTypeChecker
            json.dump(media, json_file, ensure_ascii=False, indent=4)
        input(f'Dumped JSON... Continue?')

    # Skip input error
    if media is None:
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} no media!')
        if DEBUG_empty_media:
            input('Continue?')
        return False

    # Get key fields
    try:
        media_site = channel_site
        media_id = media['id']
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_add_media:
        print(f'{datetime.now()} {Fore.RED}MISSING{Style.RESET_ALL} JSON field {exception_add_media} '
              f'in media "{media}": ')
        return False

    # CLEAR date
    original_date = None

    # Check that media has all details (full extract) or extract info (flat extract)
    try:
        # This is NOT in flat playlist JSON, if we want to use flat, we need to extract media individually!
        media_channel_id = media['channel_id']
        media_type = media['media_type']
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_add_media:
        if not extract_flat_playlist:  # retrying online is expected to happen then extract_flat_playlist is True
            print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} reading local media details, retrying online')
        try:
            # Get all info for media online (necessary in case of flat extraction)
            media = get_media_details_from_youtube(media_id=media_id, ignore_errors=False, archive_set=archive_set)
            media_channel_id = media['channel_id']
            media_type = media['media_type']

        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_add_media:
            if (regex_media_members_only.search(str(exception_add_media))
                    or regex_media_members_tier.search(str(exception_add_media))):
                print(f'{datetime.now()} {Fore.RED}MEMBERS ONLY{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    add_media(media_site=media_site,
                              media_id=media_id,
                              channel=channel_id,
                              playlist=playlist_id,
                              media_status=STATUS['members-only'],
                              media_available_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_media_paid.search(str(exception_add_media)):
                print(f'{datetime.now()} {Fore.RED}PAID{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    add_media(media_site=media_site,
                              media_id=media_id,
                              channel=channel_id,
                              playlist=playlist_id,
                              media_status=STATUS['paid'],
                              media_available_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_media_removed.search(str(exception_add_media)):
                print(f'{datetime.now()} {Fore.RED}REMOVED{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    add_media(media_site=media_site,
                              media_id=media_id,
                              channel=channel_id,
                              playlist=playlist_id,
                              media_status=STATUS['removed'],
                              media_available_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                          f'{exception_update_db}')
                    return False

            elif (regex_media_unavailable.search(str(exception_add_media))
                  or regex_media_unavailable_live.search(str(exception_add_media))):
                print(f'{datetime.now()} {Fore.RED}UNAVAILABLE{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    add_media(media_site=media_site,
                              media_id=media_id,
                              channel=channel_id,
                              playlist=playlist_id,
                              media_status=STATUS['unavailable'],
                              media_available_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_media_unavailable_geo.search(str(exception_add_media)):
                print(f'{datetime.now()} {Fore.RED}GEO BLOCKED{Style.RESET_ALL} media "{media_id}"')
                # TODO: Handle geo location change?
                return False

            elif regex_media_private.search(str(exception_add_media)):
                print(f'{datetime.now()} {Fore.RED}PRIVATE{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    add_media(media_site=media_site,
                              media_id=media_id,
                              channel=channel_id,
                              playlist=playlist_id,
                              media_status=STATUS['private'],
                              media_available_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_media_age_restricted.search(str(exception_add_media)):
                print(f'{datetime.now()} {Fore.RED}AGE RESTRICTED{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    add_media(media_site=media_site,
                              media_id=media_id,
                              channel=channel_id,
                              playlist=playlist_id,
                              media_status=STATUS['age-restricted'],
                              media_available_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_add_media:
                    if regex_sql_duplicate.search(str(exception_add_media)):
                        print(f'{datetime.now()} {Fore.RED}DUPLICATE{Style.RESET_ALL} media "{media_id}"')
                        return True
                    else:
                        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding '
                              f'{Fore.RED}UNAVAILABLE{Style.RESET_ALL} media "{media_id}": {exception_add_media}')
                        return False

            elif regex_offline.search(str(exception_add_media)):
                print(f'{datetime.now()} {Fore.RED}OFFLINE{Style.RESET_ALL} ({exception_add_media})')
                # Update DB
                try:
                    add_media(media_site=media_site,
                              media_id=media_id,
                              channel=channel_id,
                              playlist=playlist_id,
                              media_status=STATUS['unavailable'],
                              media_available_date=original_date,
                              download=download,
                              database=database)
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_add_media:
                    if regex_sql_duplicate.search(str(exception_add_media)):
                        print(f'{datetime.now()} {Fore.RED}DUPLICATE{Style.RESET_ALL} media "{media_id}"')
                        return True
                    else:
                        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding '
                              f'{Fore.RED}UNAVAILABLE{Style.RESET_ALL} media "{media_id}": {exception_add_media}')
                        return False

            elif regex_media_live_not_started.search(str(exception_add_media)):
                print(f'{datetime.now()} {Fore.RED}PRE-LISTED{Style.RESET_ALL} livestream / premiere video')
                # TODO: Is it wise to add these to database etc. for faster processing later? I think it doesn't matter too much.
                return False

            else:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while processing media "{media}": '
                      f'{exception_add_media}')
                return None  # Return None to trigger retry

    # Get date
    if original_date is None:
        try:
            original_date = datetime.strptime(media['upload_date'], '%Y%m%d').strftime('%Y-%m-%d')
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_date:
            if DEBUG_log_date_fields_missing:
                print(f'{datetime.now()} {Fore.YELLOW}MISSING{Style.RESET_ALL} JSON field {exception_date}')
    if original_date is None:
        try:
            original_date = datetime.strptime(media['release_date'], '%Y%m%d').strftime('%Y-%m-%d')
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
    if media_type == 'short':
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
    elif media_type == 'livestream':
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
    #  The "media_type" field is NOT reliable for media which isn't available yet!
    try:
        if media['availability'] is None:
            print(f'{datetime.now()} {Fore.RED}PSEUDO-PRIVATE{Style.RESET_ALL} media "{media_id}"')
            # Update DB
            try:
                # TODO: We used to add media as "unavailable" here, but this seemed to lead to issues with premieres.
                #  AFAIK it is fine to just do nothing as the media will be processed correctly later when the field "availability" is filled
                return True
            except KeyboardInterrupt:
                sys.exit()
            except Exception as exception_update_db:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                      f'{exception_update_db}')
                return False
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_check_private:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} checking private media: '
              f'{exception_check_private}')
        return True

    if original_date is not None:
        if final_download:
            media_status = STATUS['wanted']
            print(f'{datetime.now()} {Fore.CYAN}ADDING{Style.RESET_ALL} media {media_id} type "{media_type}"',
                  end='\r')
        else:
            media_status = STATUS['unwanted']
            print(f'{datetime.now()} {Fore.CYAN}SKIPPING{Style.RESET_ALL} media "{media_id}" type "{media_type}"',
                  end='\r')

        # Update DB
        try:
            add_media(media_site=media_site,
                      media_id=media_id,
                      channel=media_channel_id,
                      playlist=final_playlist_id,
                      media_status=media_status,
                      media_available_date=original_date,
                      download=final_download,
                      database=database)
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_add_media:
            if regex_sql_duplicate.search(str(exception_add_media)):
                print(f'{datetime.now()} {Fore.RED}DUPLICATE{Style.RESET_ALL} media "{media_id}"')
                return True
            if regex_sql_unavailable.search(str(exception_add_media)):
                print(f'{datetime.now()} {Fore.RED}UNAVAILABLE{Style.RESET_ALL} database, reconnecting...', end='\r')
                return None
            else:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding media "{media_id}": '
                      f'{exception_add_media}')
                return False

        if final_download:
            print(f'{datetime.now()} {Fore.GREEN}ADDED{Style.RESET_ALL} media "{media_id}" type "{media_type}"'
                  f'        ', end='\n')
        else:
            print(f'{datetime.now()} {Fore.YELLOW}SKIPPED{Style.RESET_ALL} media "{media_id}" type "{media_type}"'
                  f'        ', end='\n')
        return True

    else:
        print(f'{datetime.now()} {Fore.RED}INCOMPLETE{Style.RESET_ALL} media "{media_id}"')
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


def reconnect_vpn(counter=None, vpn_countries=None):
    """Reconnects NordVPN to a random country from list"""
    if enable_vpn:
        time_difference = (datetime.now() - vpn_timestamp).total_seconds()
        if time_difference < vpn_frequency:
            sleep_time = vpn_frequency - time_difference
            print(f'{datetime.now()} {Fore.YELLOW}WAITING{Style.RESET_ALL} {sleep_time}s before reconnecting', end='\n')
            time.sleep(sleep_time)

        if vpn_countries is None:
            vpn_countries = DEFAULT_vpn_countries
            # ONLY shuffle VPN countries when there is no given list. IDK if this really makes sense, logic here needs to be way more advanced to really cope with Google...
            random.shuffle(vpn_countries)

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


def get_media_from_db(database, status=STATUS['wanted'], regex_media_url=fr'^[a-z0-9\-\_]'):
    """
    Returns a list of all wanted YouTube media als list of lists
    Inner list field order is as follows:
      - videos.site
      - videos.url
      - videos.original_date
      - videos.status
      - videos.save_path
      - channels.name
      - channels.url
      - playlists.name
      - playlists.url
      """

    text_color = get_text_color_for_media_status(status)
    print(f'{datetime.now()} {Fore.GREEN}SELECTING{Style.RESET_ALL} {text_color}{status}{Style.RESET_ALL} media '
          f'matching ID regex {regex_media_url}',
          end='\n')

    mysql_cursor = database.cursor()

    # TODO: This filters media based on download field, which will probably not cause problems
    #  But is not 100% correct for use in verification and juggle modes
    #  (e.g. media which is no longer wanted for download could remain unverified in the download directory forever)
    sql = (
        "SELECT videos.site, videos.url, videos.original_date, videos.status, videos.save_path, "
        "channels.name, channels.url, "
        "playlists.name, playlists.url "
        "FROM videos "
        "INNER JOIN playlists ON videos.playlist=playlists.url "
        "INNER JOIN channels ON playlists.channel=channels.url "
        "WHERE (videos.status = %s) "
        "AND videos.download IS TRUE "
        "AND (LOWER(videos.url) REGEXP %s)"
        "ORDER BY "
        "EXTRACT(year FROM videos.original_date) DESC, "
        "EXTRACT(month FROM videos.original_date) DESC, "
        "EXTRACT(day FROM videos.original_date) DESC, "
        "channels.priority DESC, "
        "playlists.priority DESC, "
        "RAND();")

    val = (status, regex_media_url)

    mysql_cursor.execute(sql, val)

    mysql_result = mysql_cursor.fetchall()

    print(f'{datetime.now()} {Fore.CYAN}FOUND{Style.RESET_ALL} {len(mysql_result)} '
          f'{text_color}{status}{Style.RESET_ALL} media      ', end='\n')

    return mysql_result


def download_all_media(status_values, regex_media_url=fr'^[a-z0-9\-\_]'):
    global GEO_BLOCKED_vpn_countries
    global vpn_frequency

    database = connect_database()

    # Collect media of various status indicating download ability
    all_media = []

    for current_status in status_values:
        # text_color = get_text_color_for_media_status(media_status=current_status)
        media = get_media_from_db(database=database,
                                  status=current_status,
                                  regex_media_url=regex_media_url)
        all_media.extend(media)

    if len(all_media) == 0:
        print(f'{datetime.now()} {Fore.CYAN}DONE{Style.RESET_ALL} waiting {sleep_time_download_done} seconds')
        time.sleep(sleep_time_download_done)

    else:
        old_media_status = ''
        timestamp_old = datetime.now()
        media_counter = 0
        break_for_loop = False

        for current_media in all_media:
            media_downloaded = False
            while not media_downloaded:
                timestamp_now = datetime.now()
                timestamp_distance = timestamp_now - timestamp_old
                media_counter += 1

                media_site = current_media[0]
                media_id = current_media[1]
                media_available_date = current_media[2]
                media_status = current_media[3]
                media_save_path = current_media[4]
                channel_name = current_media[5]
                channel_id = current_media[6]
                playlist_name = current_media[7]
                playlist_id = current_media[8]

                if old_media_status != media_status:
                    text_color = get_text_color_for_media_status(media_status=media_status)
                    print(f'{timestamp_now} {Fore.CYAN}SWITCHED{Style.RESET_ALL} '
                          f'to downloading {text_color}"{media_status}"{Style.RESET_ALL} media!')
                old_media_status = media_status

                if timestamp_distance.seconds > select_newest_media_frequency:
                    timestamp_old = timestamp_now
                    if media_status == STATUS['wanted']:
                        new_media = []
                        database = connect_database()

                        for current_status in status_values:
                            # text_color = get_text_color_for_media_status(media_status=current_status)
                            media = get_media_from_db(database=database,
                                                      status=current_status,
                                                      regex_media_url=regex_media_url)
                            new_media.extend(media)

                        if len(new_media) > 0:
                            text_color = get_text_color_for_media_status(media_status=media_status)
                            print(f'{timestamp_now} {Fore.CYAN}REFRESHING{Style.RESET_ALL} '
                                  f'{text_color}"{media_status}"{Style.RESET_ALL} media list!')
                            break_for_loop = True
                            break

                vpn_counter_geo = 0
                GEO_BLOCKED_vpn_countries = []

                media_downloaded = download_media(media=current_media)
                if media_downloaded is None:
                    return
                elif media_downloaded:
                    continue
                else:
                    if GEO_BLOCKED_vpn_countries:
                        vpn_frequency = GEO_BLOCKED_vpn_frequency
                        vpn_counter_geo = reconnect_vpn(vpn_counter_geo, GEO_BLOCKED_vpn_countries)
                        # To break endless loop
                        if vpn_counter_geo == 0:
                            continue

            if break_for_loop:
                break


def download_media(media):
    media_site = media[0]
    media_id = media[1]
    media_available_date = media[2]
    media_status = media[3]
    media_save_path = media[4]
    channel_name = media[5]
    channel_id = media[6]
    playlist_name = media[7]
    playlist_id = media[8]

    if directory_download_temp is None:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} download temp directory not set!')
        sys.exit()
    if directory_download_home is None:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} download home directory not set!')
        sys.exit()

    clear_temp_dir(media_status=media_status)

    text_color = get_text_color_for_media_status(media_status=media_status)

    print(f'{datetime.now()} {Fore.CYAN}DOWNLOADING{Style.RESET_ALL} '
          f'media for "{media_site} - {media_id}" '
          f'status {text_color}"{media_status}"{Style.RESET_ALL}')

    if media_site == 'youtube':
        # Set the full output path
        full_path = os.path.join(f'{channel_name} - {playlist_name}',
                                 f'Season %(release_date>%Y,upload_date>%Y)s [{channel_name}]',
                                 f'{channel_name} - {playlist_name} - '
                                 f'S%(release_date>%Y,upload_date>%Y)sE%(release_date>%j,upload_date>%j)s - '
                                 f'%(title)s.%(ext)s')
        # print(f'Path for media "{media_site} {media_id}": {full_path}')

        media_url = f'https://www.youtube.com/watch?v={media_id}'
        temp_dir_path = os.path.join(directory_download_temp, f'{media_status} {letter_low}-{letter_high}')

        # Set download options for YT-DLP
        media_download_options = {
            'logger': VoidLogger(),  # TODO: This suppresses all errors, we should still see them in exception handling
            'quiet': quiet_download_info,
            'no_warnings': quiet_download_warnings,
            # 'verbose': True,
            'download_archive': None,  # TODO: This is correct, yes?
            'cachedir': False,
            'skip_unavailable_fragments': False,  # To abort on missing mp4 parts (largely avoids re-downloading)
            'ignoreerrors': False,
            'ignore_no_formats_error': False,  # Keep "False" to get exception to handle in python!
            'extractor_retries': retry_extraction_download,
            'socket_timeout': timeout_download,
            'source_address': external_ip,
            'nocheckcertificate': True,
            'restrictfilenames': True,
            'windowsfilenames': True,
            # 'trim_file_name': True,
            # TODO: This leads to -o being igonred?
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
                'temp': temp_dir_path,
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

    # Abort when redirected to "Video Not Available"-page, pieces of media are missing, or any other errors happen
    --break-match-filters "title!*=Video Not Available"
        '''

        # Try-Except Block to handle YT-DLP exceptions such as "playlist does not exist"
        try:
            # Run YT-DLP
            with yt_dlp.YoutubeDL(media_download_options) as ilus:
                # ilus.download(media_url)
                meta = ilus.extract_info(media_url, download=True)
                meta = ilus.sanitize_info(meta)
                path = meta['requested_downloads'][0]['filepath']
                # TODO: new format? path = path[len(directory_download_home)+len(os.sep):len(path)-len('.mp4')]
                path = path[len(directory_download_home) + len(os.sep):len(path)]

                # Get date
                if media_available_date is None:
                    try:
                        media_available_date = datetime.strptime(meta['upload_date'], '%Y%m%d').strftime('%Y-%m-%d')
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception_date:
                        if DEBUG_log_date_fields_missing:
                            print(f'{datetime.now()} {Fore.YELLOW}MISSING{Style.RESET_ALL} JSON field {exception_date}')
                if media_available_date is None:
                    try:
                        media_available_date = datetime.strptime(meta['release_date'], '%Y%m%d').strftime('%Y-%m-%d')
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception_date:
                        if DEBUG_log_date_fields_missing:
                            print(f'{datetime.now()} {Fore.YELLOW}MISSING{Style.RESET_ALL} JSON field {exception_date}')
                if media_available_date is None:
                    print(f'{datetime.now()} {Fore.RED}NO DATE{Style.RESET_ALL} aborting!')
                    return False

            """
            What happens in the weird edge-case that YT-DLP ends with reaching all retries?
            It does not progress past this point, but also does not throw an exception. No IDK how/why.
            """

            # Update DB
            try:
                # TODO: This needs to be worked together with the add_media method and update_media_status method
                media_status = 'fresh'
                mydb = connect_database()
                mysql_cursor = mydb.cursor()
                sql = "UPDATE videos SET status = %s, save_path = %s, original_date = %s WHERE site = %s AND url = %s;"
                val = (media_status, path, media_available_date, media_site, media_id)
                mysql_cursor.execute(sql, val)
                mydb.commit()

                text_color = get_text_color_for_media_status(media_status=media_status)

                print(f'{datetime.now()} {Fore.GREEN}UPDATED{Style.RESET_ALL} media "{media_id}" '
                      f'to status {text_color}"{media_status}"{Style.RESET_ALL}')
                return True
            except KeyboardInterrupt:
                sys.exit()
            except Exception as exception_update_db:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                      f'{exception_update_db}')
                return False
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_download:
            if regex_error_http_403.search(str(exception_download)):
                print(f'{datetime.now()} {Fore.RED}IP BANNED{Style.RESET_ALL} while downloading media "{media_id}"')
                reconnect_vpn()
                return False

            elif regex_bot.search(str(exception_download)):
                print(f'{datetime.now()} {Fore.RED}BOT DETECTED{Style.RESET_ALL} while downloading media "{media_id}"')
                reconnect_vpn()
                return False

            elif regex_error_get_addr_info.search(str(exception_download)):
                print(
                    f'{datetime.now()} {Fore.RED}GET ADDR INFO FAILED{Style.RESET_ALL} while downloading media "{media_id}"')
                reconnect_vpn()
                return False

            elif regex_media_format_unavailable.search(str(exception_download)):
                print(f'{datetime.now()} {Fore.RED}FORMAT UNAVAILABLE{Style.RESET_ALL} '
                      f'while downloading media "{media_id}"')
                reconnect_vpn()
                return False

            elif regex_json_write.search(str(exception_download)):
                print(f'{datetime.now()} {Fore.RED}JSON WRITE ERROR{Style.RESET_ALL} '
                      f'while downloading media "{media_id}"')
                clear_temp_dir(media_status=media_status)
                return False

            elif regex_error_win_5.search(str(exception_download)):
                print(f'{datetime.now()} {Fore.RED}WIN ERROR 5{Style.RESET_ALL} '
                      f'while downloading media "{media_id}"')
                clear_temp_dir(media_status=media_status)
                reconnect_vpn()
                return False
                # TODO: IDK if we can recover from this error, it seems like once it comes up, it stays until full program restart
                # sys.exit()

            elif regex_error_win_32.search(str(exception_download)):
                print(f'{datetime.now()} {Fore.RED}WIN ERROR 32{Style.RESET_ALL} '
                      f'while downloading media "{media_id}"')
                clear_temp_dir(media_status=media_status)
                reconnect_vpn()
                return False
                # TODO: IDK if we can recover from this error, it seems like once it comes up, it stays until full program restart
                # sys.exit()

            elif regex_error_win_10054.search(str(exception_download)):
                print(f'{datetime.now()} {Fore.RED}WIN ERROR 10054{Style.RESET_ALL} '
                      f'while downloading media "{media_id}"')
                clear_temp_dir(media_status=media_status)
                reconnect_vpn()
                return False
                # TODO: IDK if we can recover from this error, it seems like once it comes up, it stays until full program restart
                # sys.exit()

            elif (regex_media_members_only.search(str(exception_download))
                  or regex_media_members_tier.search(str(exception_download))):
                # print(f'{datetime.now()} {Fore.RED}MEMBERS ONLY{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    if media_status != STATUS['members-only']:
                        add_media(media_site=media_site,
                                  media_id=media_id,
                                  channel=channel_id,
                                  playlist=playlist_id,
                                  media_status=STATUS['members-only'],
                                  media_available_date=media_available_date,
                                  download=True)  # Download can be assumed to be True for media that is being downloaded
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_media_paid.search(str(exception_download)):
                # print(f'{datetime.now()} {Fore.RED}PAID{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    if media_status != STATUS['paid']:
                        add_media(media_site=media_site,
                                  media_id=media_id,
                                  channel=channel_id,
                                  playlist=playlist_id,
                                  media_status=STATUS['paid'],
                                  media_available_date=media_available_date,
                                  download=True)  # Download can be assumed to be True for media that is being downloaded
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_media_removed.search(str(exception_download)):
                # print(f'{datetime.now()} {Fore.RED}REMOVED{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    if media_status != STATUS['removed']:
                        add_media(media_site=media_site,
                                  media_id=media_id,
                                  channel=channel_id,
                                  playlist=playlist_id,
                                  media_status=STATUS['removed'],
                                  media_available_date=media_available_date,
                                  download=True)  # Download can be assumed to be True for media that is being downloaded
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                          f'{exception_update_db}')
                    return False

            elif (regex_media_unavailable.search(str(exception_download))
                  or regex_media_unavailable_live.search(str(exception_download))):
                # print(f'{datetime.now()} {Fore.RED}UNAVAILABLE{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    if media_status != STATUS['unavailable']:
                        add_media(media_site=media_site,
                                  media_id=media_id,
                                  channel=channel_id,
                                  playlist=playlist_id,
                                  media_status=STATUS['unavailable'],
                                  media_available_date=media_available_date,
                                  download=True)  # Download can be assumed to be True for media that is being downloaded
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_media_unavailable_geo.search(str(exception_download)):
                # print(f'{datetime.now()} {Fore.RED}GEO BLOCKED{Style.RESET_ALL} media "{media_id}"')
                global GEO_BLOCKED_vpn_countries
                if not GEO_BLOCKED_vpn_countries:
                    try:
                        countries_results = regex_media_unavailable_geo_fix.search(str(exception_download))
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

            elif regex_media_private.search(str(exception_download)):
                # print(f'{datetime.now()} {Fore.RED}PRIVATE{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    if media_status != STATUS['private']:
                        add_media(media_site=media_site,
                                  media_id=media_id,
                                  channel=channel_id,
                                  playlist=playlist_id,
                                  media_status=STATUS['private'],
                                  media_available_date=media_available_date,
                                  download=True)  # Download can be assumed to be True for media that is being downloaded
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                          f'{exception_update_db}')
                    return False

            elif regex_media_age_restricted.search(str(exception_download)):
                # print(f'{datetime.now()} {Fore.RED}AGE RESTRICTED{Style.RESET_ALL} media "{media_id}"')
                # Update DB
                try:
                    if media_status != STATUS['age-restricted']:
                        add_media(media_site=media_site,
                                  media_id=media_id,
                                  channel=channel_id,
                                  playlist=playlist_id,
                                  media_status=STATUS['age-restricted'],
                                  media_available_date=media_available_date,
                                  download=True)  # Download can be assumed to be True for media that is being downloaded
                    return True
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_update_db:
                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while updating media "{media_id}": '
                          f'{exception_update_db}')
                    return False

            else:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} downloading media: {exception_download}')
                return True


def clear_temp_dir(media_status):
    """Clears the download temp directory"""
    temp_dir_path = os.path.join(directory_download_temp, f'{media_status} {letter_low}-{letter_high}')

    try:
        print(f'{datetime.now()} {Fore.CYAN}DELETING TEMP DIRECTORY{Style.RESET_ALL} {temp_dir_path}',
              end='\r')
        shutil.rmtree(temp_dir_path)
        print(f'{datetime.now()} {Fore.CYAN}DELETED TEMP DIRECTORY{Style.RESET_ALL} {temp_dir_path} ',
              end='\n')
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_clear_temp:
        if not regex_error_win_2.search(str(exception_clear_temp)):
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} {exception_clear_temp}')
        else:
            print(f'{datetime.now()} {Fore.CYAN}NO SUCH TEMP DIRECTORY{Style.RESET_ALL} {temp_dir_path} ',
                  end='\n')


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

        # Get playlists
        sql = ("SELECT playlists.site, playlists.url, playlists.name, playlists.priority, "
               "channels.url, channels.name, channels.priority, playlists.download "
               "FROM playlists "
               "INNER JOIN channels "
               "ON playlists.channel = channels.url "
               "WHERE playlists.site = %s "
               "AND playlists.done IS NOT TRUE "  # TODO: We should either remove or automate the "done" DB field ASAP!
               "AND playlists.monitor IS TRUE "
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


def get_all_channel_media_from_youtube(channel):
    get_new_channel_media_from_youtube(channel=channel,
                                       ignore_errors=DEFAULT_ignore_errors_channel,
                                       archive_set=set())


def get_all_channel_playlists_from_youtube(channel_id, ignore_errors):
    """Returns a list of all online YouTube playlists for the given channel"""
    playlists = []
    while not playlists:
        print(f'{datetime.now()} Collecting playlists for channel "{channel_id}"', end='\r')

        channel_playlists_url = f'https://www.youtube.com/channel/{channel_id}/playlists'

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
                          f'for channel "{channel_id}"')
                    return playlists
            except KeyboardInterrupt:
                sys.exit()
            except Exception as exception_find_entries_in_info_json:
                print(
                    f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} cannot find entries in Info JSON "{info_json}": '
                    f'{exception_find_entries_in_info_json}')
                return None

        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_get_online_playlists:
            if regex_channel_no_playlists.search(str(exception_get_online_playlists)):
                return None
            elif regex_error_timeout.search(str(exception_get_online_playlists)):
                print(f'{datetime.now()} {Fore.RED}TIMEOUT{Style.RESET_ALL} while getting playlists for channel '
                      f'"{channel_id}": {exception_get_online_playlists}')
                continue  # Retry in method instead of external
            elif not regex_channel_no_playlists.search(str(exception_get_online_playlists)):
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while getting playlists for channel '
                      f'"{channel_id}": {exception_get_online_playlists}')
                return None


def get_all_playlist_media_from_youtube(playlist):
    get_new_playlist_media_from_youtube(playlist=playlist,
                                        ignore_errors=DEFAULT_ignore_errors_channel,
                                        archive_set=set(),
                                        counter=0)


def add_playlist_media(media_list):
    for media_list_entry in media_list:
        # TODO
        print(media_list_entry)


def add_channel_media(media_list):
    for media_list_entry in media_list:
        # TODO
        print(media_list_entry)


def check_channel_complete(channel, database_playlists):
    """
    Check if channel has new playlists online that we do not know of
    """
    channel_site = channel[0]
    channel_id = channel[1]
    channel_name = channel[2]

    unknown_playlists_exist = False

    online_playlists = get_all_channel_playlists_from_youtube(channel_id=channel_id,
                                                              ignore_errors=DEFAULT_ignore_errors_playlist)
    if online_playlists is not None:
        if len(online_playlists) == 30:
            if INPUT_POSSIBLE:
                try:
                    input('Press any key to continue processing channel')
                    return True
                except KeyboardInterrupt:
                    return False
            else:
                # TODO: Remove this once yt-dlp becomes reliable?!
                print(f'{datetime.now()} {Fore.YELLOW}SUSPICIOUS PLAYLIST COUNT{Style.RESET_ALL} '
                      f'for channel "{channel_name}" ({channel_site} {channel_id})')
                return False

        for online_playlist in online_playlists:
            # TODO: Add site to query (part of changing to object based list with compare method etc.)
            online_playlist_site = channel_site
            online_playlist_id = online_playlist['id']
            online_playlist_name = online_playlist['title']

            if online_playlist_id not in database_playlists:
                unknown_playlists_exist = True

        if unknown_playlists_exist:
            print(f'{datetime.now()} {Fore.RED}INCOMPLETE{Style.RESET_ALL} '
                  f'channel "{channel_name}" ({channel_site} {channel_id})')
            if INPUT_POSSIBLE:
                process_channel(channel_url=f'https://www.youtube.com/channel/{channel_id}/videos')
            return False
        else:
            print(f'{datetime.now()} {Fore.GREEN}COMPLETE{Style.RESET_ALL} '
                  f'channel "{channel_name}" ({channel_site} {channel_id})')
            return True

    else:
        print(f'{datetime.now()} {Fore.YELLOW}NO PLAYLISTS{Style.RESET_ALL} '
              f'for channel "{channel_name}" ({channel_site} {channel_id})')
        return True


def update_subscriptions(regex_channel_url=fr'^UC[a-z0-9\-\_]'):
    global vpn_timestamp
    global vpn_counter
    global global_archive_set

    database = connect_database()  # TODO: This was previously done every channel, I think it is not needed/buggy, testing.
    database_playlists = get_database_playlist_names(database=database)
    filtered_channels = get_monitored_channels_from_db(database=database, regex_channel_url=regex_channel_url)

    # TODO: Not reconnecting DB every channel may lead to issue where stuck at messages "Database connection unavailable"
    for current_channel in filtered_channels:
        current_channel_site = current_channel[0]
        current_channel_id = current_channel[1]
        current_channel_name = current_channel[2]
        media_added_channel = 0

        channel_complete = False

        # Retry getting missing media for channel from YouTube
        counter_process_channel = 0
        ignore_errors_channel = DEFAULT_ignore_errors_channel
        skip_channel = False
        missing_media_channel = None
        while missing_media_channel is None and not skip_channel:
            channel_available = check_channel_availability(channel=current_channel)
            if channel_available:
                channel_complete = check_channel_complete(channel=current_channel,
                                                          database_playlists=database_playlists)

                missing_media_channel = get_new_channel_media_from_youtube(channel=current_channel,
                                                                           ignore_errors=ignore_errors_channel,
                                                                           archive_set=global_archive_set)
            counter_process_channel += 1

            if missing_media_channel is None:
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
        if missing_media_channel == False:
            print(f'{datetime.now()} {Fore.RED}CRITICAL ERROR{Style.RESET_ALL} while processing channel '
                  f'"{current_channel_name}" ({current_channel_site} {current_channel_id})')
        # After this point we can guarantee the presence of channel media list
        elif missing_media_channel is not None:
            all_playlists_checked_successfully = True
            missing_media_count_channel = 0
            if type(missing_media_channel) == list:
                missing_media_count_channel = len(missing_media_channel)
            if missing_media_count_channel > 0:
                # Get missing media for channel from MySQL (no retry needed)
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
                        if not all_playlists_checked_successfully or not channel_complete:
                            print(f'{datetime.now()} {Fore.YELLOW}SKIPPING{Style.RESET_ALL} uploads playlist for '
                                  f'channel "{current_channel_name}" ({current_playlist_site} {current_channel_id})')
                            current_playlist_checked_successfully = False  # To skip processing in case of skipped "Other" playlist

                    if current_playlist_checked_successfully:  # To skip processing in case of skipped "Other" playlist
                        if DEBUG_add_unmonitored:
                            input(f'{current_playlist_download} - {type(current_playlist_download)}')

                        if media_added_channel >= missing_media_count_channel:
                            print(f'{datetime.now()} {Fore.GREEN}DONE{Style.RESET_ALL} processing channel '
                                  f'"{current_channel_name}" ({current_playlist_site} {current_channel_id})')
                            break

                        # Retry getting missing media for playlist from YouTube
                        ignore_errors_playlist = DEFAULT_ignore_errors_playlist
                        skip_playlist = False
                        missing_media_playlist = None
                        while missing_media_playlist is None and not skip_playlist:
                            missing_media_playlist = get_new_playlist_media_from_youtube(playlist=current_playlist,
                                                                                         ignore_errors=ignore_errors_playlist,
                                                                                         counter=counter_process_playlist,
                                                                                         archive_set=global_archive_set)
                            counter_process_playlist += 1

                            if missing_media_playlist is None:
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
                        if missing_media_playlist == False:
                            print(f'{datetime.now()} {Fore.RED}CRITICAL ERROR{Style.RESET_ALL} '
                                  f'while processing playlist "'
                                  f'{current_playlist_name}" ({current_playlist_site} {current_playlist_id})')
                        elif missing_media_playlist is not None:
                            '''After this point we can guarantee the presence of playlist media list'''
                            missing_media_count_playlist = 0
                            if type(missing_media_playlist) == list:
                                missing_media_count_playlist = len(missing_media_playlist)
                            if missing_media_count_playlist > 0:
                                for missing_media_playlist in missing_media_playlist:
                                    # Add media info
                                    media_added = None
                                    skip_media = False
                                    counter_process_media = 0
                                    while media_added is None and not skip_media:

                                        media_added = process_media(channel_site=current_playlist_site,
                                                                    media=missing_media_playlist,
                                                                    channel_id=current_channel_id,
                                                                    playlist_id=current_playlist_id,
                                                                    download=current_playlist_download,
                                                                    archive_set=global_archive_set,
                                                                    database=database)

                                        counter_process_media += 1

                                        if media_added is None:
                                            # TODO: This is inefficient, it we should differentiate between yt-dlp exceptions and sql exception(s)!
                                            database = connect_database()
                                            if counter_process_media > retry_process_media:
                                                try:
                                                    current_media_id = missing_media_playlist['id']
                                                except KeyboardInterrupt:
                                                    sys.exit()
                                                except Exception as e:
                                                    print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} '
                                                          f'getting id from media "{missing_media_playlist}": {e}')
                                                    current_media_id = missing_media_playlist

                                                print(f'{datetime.now()} {Fore.RED}GIVING UP{Style.RESET_ALL} after '
                                                      f'{counter_process_media} tries while processing media "{current_media_id}"')
                                                skip_media = True

                                    if media_added:
                                        media_added_channel += 1

                    # Playlist is updated after
                    # A: All media has been processed or already known
                    # B: The playlist had no (new) media
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
            # A: All playlists have been checked to completion (<= all media was found on playlists)
            # B: All new channel media has been found on a playlist
            # C: The channel had no new media
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
def get_database_channel_names(database):
    """
    Returns a list of all known YouTube channels
    Field order:
        - channels.url
        - channels.name
    """

    print(f'{datetime.now()} Collecting channel names...', end='\r')
    mysql_cursor = database.cursor()

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
    channel_name_list = dict(mysql_result)
    return channel_name_list


# TODO: This is redundant and needs to be merged with get_monitored_playlists_from_db()
def get_database_playlist_names(database):
    """
    Returns a list of all known YouTube playlists
        Field order:
            - playlists.url
            - playlists.name
    """
    print(f'{datetime.now()} Collecting playlists...', end='\r')
    mysql_cursor = database.cursor()

    sql = "select playlists.url, playlists.name from playlists WHERE site = %s;"
    val = ('youtube',)  # DO NOT REMOVE COMMA, it is necessary for MySQL to work!
    mysql_cursor.execute(sql, val)
    mysql_result = mysql_cursor.fetchall()

    return dict(mysql_result)


def add_subscriptions():
    database = connect_database()
    database_channels = get_database_channel_names(database=database)
    database_playlists = get_database_playlist_names(database=database)

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

    # TODO: In the VERY RARE case that there are no playlists added for a channel, it will not show up here.
    ## This has SIDE EFFECTS; User will be prompted for channel name again, but no change is committed to DB
    ## This was done to purposefully ignore channels which were added by the initial disk scan on our legacy
    ## system with 100'000+ videos on it. Once we have built a new routine to rebuild DB from disk, we need
    ## to fix this finally! WORKAROUND: Just add the channels again using /videos URL. As long as at least
    ## ONE playlist IS added to DB, the channel WILL show up in this list.
    if use_database:
        for database_channel in database_channels:
            channel_list.append(f'https://www.youtube.com/channel/{database_channel}/videos')
    else:
        channel_url = input(f'Enter CHANNEL URL: ')
        channel_list.append(channel_url)

    for channel_url in channel_list:
        try:
            process_channel(channel_url=channel_url,
                            database_channels=database_channels,
                            database_playlists=database_playlists)
        except KeyboardInterrupt:
            print(f'{datetime.now()} {Fore.YELLOW}SKIPPING{Style.RESET_ALL} channel')
            continue
        except Exception as exception_process_channel:
            print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} processing channel: '
                  f'{exception_process_channel}')


def process_channel(channel_url, database_channels=None, database_playlists=None):
    """Add online channel playlists to database"""

    database = connect_database()
    if not database_channels:
        database_channels = get_database_channel_names(database=database)
    if not database_playlists:
        database_playlists = get_database_playlist_names(database=database)

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
        print(f'{datetime.now()} {Fore.CYAN}ATTENTION{Style.RESET_ALL} All "Other" media is already being monitored!')

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

    # Handle "Other" playlist (channel "uploads" playlist)
    playlist_id = channel_id
    playlist_name_online = 'Other'
    print(f'{datetime.now()} {Fore.CYAN}ATTENTION{Style.RESET_ALL} '
          f'"Other" Playlist should only be added for channels where most media is not on any playlists!')

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


def switch_directory(path_orig, dir_orig, dir_new):
    return os.path.join(dir_new, path_orig[len(dir_orig + os.sep):len(path_orig)])


def juggle_verified_media():
    """
    Move in verified files
    """
    if directory_final is None:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} final directory not set!')
        sys.exit()
    if directory_download_home is None:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} download home directory not set!')
        sys.exit()

    database = connect_database()

    leftover_files = check_leftover_files(directory_to_check=directory_download_home)
    print(f'{datetime.now()} {leftover_files} files left to move in...')

    file_counter_total = 0

    for directory, folders, files in os.walk(directory_download_home):
        folders.sort(reverse=True)
        files.sort(reverse=True)
        for filename in files:
            if regex_mp4.search(filename):
                # Original paths
                path_orig = os.path.join(directory, filename)

                json_path_orig = regex_mp4.sub('.info.json', path_orig)
                png_path_orig = regex_mp4.sub('.png', path_orig)
                vtt_en_path_orig = regex_mp4.sub('.en-orig.vtt', path_orig)
                vtt_de_path_orig = regex_mp4.sub('.de-orig.vtt', path_orig)
                nfo_path_orig = regex_mp4.sub('.nfo', path_orig)

                # Target paths
                path_move = switch_directory(path_orig=path_orig,
                                             dir_orig=directory_download_home,
                                             dir_new=directory_final)
                json_path_move = switch_directory(path_orig=json_path_orig,
                                                  dir_orig=directory_download_home,
                                                  dir_new=directory_final)
                png_path_move = switch_directory(path_orig=png_path_orig,
                                                 dir_orig=directory_download_home,
                                                 dir_new=directory_final)
                # TODO: Remove "-orig" in name to fix being detected as ICELANDIC subtitles!
                vtt_en_path_move = switch_directory(path_orig=vtt_en_path_orig,
                                                    dir_orig=directory_download_home,
                                                    dir_new=directory_final)
                # TODO: Remove "-orig" in name to fix being detected as ICELANDIC subtitles!
                vtt_de_path_move = switch_directory(path_orig=vtt_de_path_orig,
                                                    dir_orig=directory_download_home,
                                                    dir_new=directory_final)
                nfo_path_move = switch_directory(path_orig=nfo_path_orig,
                                                 dir_orig=directory_download_home,
                                                 dir_new=directory_final)

                # Further work can only be done, if an Info JSON exists!
                if os.path.exists(json_path_orig):
                    with io.open(json_path_orig, encoding='utf-8-sig') as json_txt:
                        try:
                            # Get keys for ilus DB from Info JSON
                            json_obj = json.load(json_txt)
                            json_site = json_obj['extractor']
                            json_url = json_obj['id']

                            json_date = None
                            if json_date is None:
                                try:
                                    json_date = datetime.strptime(json_obj['upload_date'], '%Y%m%d').strftime(
                                        '%Y-%m-%d')
                                except KeyboardInterrupt:
                                    sys.exit()
                                except Exception as exception_add_media:
                                    print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL}: '
                                          f'No upload date in info JSON! ({exception_add_media})')
                            if json_date is None:
                                try:
                                    json_date = datetime.strptime(json_obj['release_date'], '%Y%m%d').strftime(
                                        '%Y-%m-%d')
                                except KeyboardInterrupt:
                                    sys.exit()
                                except Exception as exception_add_media:
                                    print(
                                        f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL}: No release date in info JSON! ({exception_add_media})')

                        except KeyboardInterrupt:
                            sys.exit()
                        except Exception as exception:
                            print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} reading info JSON: {exception}')
                            continue

                        try:
                            # TODO: This should be a method!
                            # Reconnect DB every time to avoid caching
                            mydb = mysql.connector.connect(
                                host=mysql_host,
                                user=mysql_user,
                                password=mysql_password,
                                database=mysql_database
                            )
                            mycursor = mydb.cursor()

                            # Check status in ilus DB
                            sql = "SELECT status FROM videos WHERE site = %s AND url = %s;"
                            val = (json_site, json_url)
                            mycursor.execute(sql, val)
                            myresult = mycursor.fetchall()
                            try:
                                sql_status = myresult[0][0]
                            except KeyboardInterrupt:
                                sys.exit()
                            except Exception as exception:
                                print(f'{datetime.now()} {Fore.RED}UNKNOWN MEDIA{Style.RESET_ALL} '
                                      f'{os.path.basename(path_move)}')
                                if json_date is None:
                                    # If we have no date, we cannot insert!
                                    continue
                                else:
                                    # TODO: We used to add media as "fresh" here, this should not be necessary,
                                    #  but could be re-added in the future for completeness sake.
                                    continue

                            if sql_status == STATUS['wanted']:
                                print(f'{datetime.now()} {Fore.CYAN}DATABASE MISMATCH{Style.RESET_ALL} '
                                      f'{os.path.basename(path_move)}: Status "{sql_status}"')
                                continue
                            elif not (sql_status == STATUS['verified'] or sql_status == STATUS['uncertain']):
                                print(f'{datetime.now()} {Fore.CYAN}SKIPPING{Style.RESET_ALL} '
                                      f'{os.path.basename(path_move)}: Status "{sql_status}"')
                                continue

                        except KeyboardInterrupt:
                            sys.exit()
                        except Exception as exception:
                            print(f'{datetime.now()} {Fore.RED}SQL SELECT ERROR{Style.RESET_ALL} '
                                  f'{os.path.basename(path_move)}: {exception}')
                            continue

                # Move in Files
                move_in_error = False

                # NFO
                nfo_created = fix_nfo_file(nfo_path_move)
                if not nfo_created:
                    # print(f'NO NFO')
                    move_in_error = True
                    continue

                # Thumbnail
                try:
                    # os.renames(png_path_orig, png_path_move)
                    shutil.move(png_path_orig, png_path_move)
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception:
                    print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} '
                          f'Moving {os.path.basename(png_path_move)} in: {exception}')
                    move_in_error = True

                # Info JSON
                try:
                    # os.renames(json_path_orig, json_path_move)
                    shutil.move(json_path_orig, json_path_move)
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception:
                    print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} '
                          f'Moving {os.path.basename(json_path_move)} in: {exception}')
                    move_in_error = True

                # English Subtitles
                # TODO: This needs to be changed to work for ALL subtitles!
                try:
                    # os.renames(vtt_en_path_orig, vtt_en_path_move)
                    shutil.move(vtt_en_path_orig, vtt_en_path_move)
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception:
                    # German Subtitles
                    # TODO: This needs to be changed to work for ALL subtitles!
                    try:
                        # os.renames(vtt_de_path_orig, vtt_de_path_move)
                        shutil.move(vtt_de_path_orig, vtt_de_path_move)
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception:
                        print(f'{datetime.now()} {Fore.CYAN}INFO{Style.RESET_ALL} No Subtitles found.')
                        # TODO: Handle as seperate case! move_in_error = True

                # MP4 video file
                try:
                    # os.renames(path_orig, path_move)
                    shutil.move(path_orig, path_move)
                    file_counter_total += 1
                    print(f'{datetime.now()} {Fore.GREEN}MOVED{Style.RESET_ALL} {os.path.basename(path_move)} in.')
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception:
                    print(
                        f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} Moving {os.path.basename(path_move)} in: {exception}')
                    move_in_error = True
                try:
                    if move_in_error:
                        # TODO: Rollback moved files instead and DO NOT update DB to anything (auto retry happens later)!
                        # Update DB
                        update_media_status(media_site=json_site,
                                            media_id=json_url,
                                            media_status=STATUS['stuck'],
                                            database=database)
                    else:
                        # Update DB
                        update_media_status(media_site=json_site,
                                            media_id=json_url,
                                            media_status=STATUS['done'],
                                            database=database)
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception:
                    print(
                        f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} Moving {os.path.basename(path_move)} in: {exception}')

    print(f'{datetime.now()} Moved in {file_counter_total} episodes!')

    print(f'{datetime.now()} {Fore.CYAN}WAITING{Style.RESET_ALL} {sleep_time_move_in}s...')
    time.sleep(sleep_time_move_in)

    # TODO: Return amount of moved in media / files?
    return


def check_leftover_files(directory_to_check):
    """
    Return False when there is no files left in given directory, otherwise returns the count of files.
    """
    try:
        file_count = sum([len(files) for r, d, files in os.walk(directory_to_check)])
        # file_count = len(os.listdir(directory_to_check))
        if file_count == 0:
            return False
        else:
            return file_count
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception:
        return False


def write_nfo(path, content):
    """
    Writes NFO file content to file on disk
    """
    folder = os.path.split(path)[0]
    if not os.path.exists(folder):
        os.makedirs(folder)

    if content:
        try:
            with io.open(path, 'w', encoding='utf-8-sig') as nfo_new:
                nfo_new.write(content)
                return True
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception:
            input(exception)
            return False

    else:
        # TODO: Replace input with well-designed logging
        input(f'CRITICAL ERROR')
        return False


# TODO: This method will become redundant when we switch to objects
def get_channel_name(media_site, media_id):
    """
    Gets database channel name from site and id
    """
    try:
        # Reconnect DB every time to avoid caching
        mydb = mysql.connector.connect(
            host=mysql_host,
            user=mysql_user,
            password=mysql_password,
            database=mysql_database
        )
        mycursor = mydb.cursor()

        # Check status in ilus DB
        sql = "SELECT name FROM channels WHERE site = %s AND url = (SELECT channel FROM playlists WHERE site = %s AND url = ( SELECT playlist FROM videos WHERE site = %s AND url = %s));"
        val = (media_site, media_site, media_site, media_id)
        mycursor.execute(sql, val)
        myresult = mycursor.fetchall()

        channel_name = myresult[0][0]
        return channel_name

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception:
        print(
            f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} getting channel name for "{media_site} {media_id}": {exception}')
        return None


def fix_nfo_file(nfo_file):
    filename = nfo_file
    nfo_modified = False

    # Redundant check if file is NFO
    if regex_nfo.search(filename) and not regex_show_nfo.search(filename) and not regex_season_nfo.search(filename):
        path_nfo = filename
        base_path_nfo = os.path.basename(path_nfo)
        path_json = re.sub(regex_nfo, '.info.json', path_nfo)
        base_path_json = os.path.basename(path_json)

        if not os.path.exists(path_json):
            # Take data from incomplete (fresh) directory instead of final (verified)
            path_json = switch_directory(path_orig=path_json,
                                         dir_orig=directory_final,
                                         dir_new=directory_download_home)
            # TODO: Remove input
            input(path_json)

        if not os.path.exists(path_json):
            print(f'{datetime.now()} {Fore.RED}MISSING JSON{Style.RESET_ALL} {os.path.basename(path_json)}')
            return False

        with io.open(path_json, 'r', encoding='utf-8-sig') as json_txt:
            try:
                json_obj = json.load(json_txt)

                json_id = json_obj['id']

                json_title = json_obj['title']
                json_fulltitle = json_obj['fulltitle']
                nfo_title = json_title

                try:
                    json_description = json_obj['description']
                    nfo_description = r'<![CDATA[' + json_description + r']]>'
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception:
                    print(f'NO DESCRIPTION, continue?! {exception}')
                    json_description = ''
                    nfo_description = ''

                json_upload_date = json_obj['upload_date']
                json_upload_date = datetime.strptime(json_upload_date, '%Y%m%d')
                nfo_upload_date = json_upload_date.strftime('%Y-%m-%d')

                nfo_year = json_upload_date.strftime('%Y')

                # TODO: is will always get the media uploader name, which is fine for media, but should NOT be used for season and/or shows without first confirming they are the same as playlist owner!
                json_site = json_obj['extractor']
                json_channel = json_obj['channel_id']
                nfo_network = get_channel_name(media_site=json_site, media_id=json_id)
                if nfo_network == None:
                    return False

            except KeyboardInterrupt:
                sys.exit()
            except Exception as exception:
                print(
                    f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} reading JSON "{base_path_json}": {exception}')
                return False

        if not os.path.exists(path_nfo) or replace_existing:
            # Make own NFO!
            if create_nfo_files:
                E = lxml.builder.ElementMaker()

                xml_data = E.episodedetails(
                    # E.plot(f'{nfo_description}'),
                    E.title(f'{nfo_title}'),
                    E.year(f'{nfo_year}'),
                    E.studio(f'{nfo_network}'),
                    E.aired(f'{nfo_upload_date}')
                )
                xml_txt = lxml.etree.tostring(xml_data, encoding=str, pretty_print=True)

                # xml_tree = BeautifulSoup(xml_txt, 'xml').prettify()
                xml_tree = xml_txt

                # FIX for '<' and '>' in BS4
                # xml_tree = re.sub(r'&lt;', '<', xml_tree)
                # xml_tree = re.sub(r'&gt;', '>', xml_tree)

                # input(xml_tree)

                nfo_txt = xml_tree

                write_nfo_result = write_nfo(path=path_nfo, content=nfo_txt)

                # print(f'{datetime.now()} {Fore.GREEN}CREATED{Style.RESET_ALL} new NFO {base_path_nfo}')

                return write_nfo_result

            else:
                print(f'{datetime.now()} {Fore.RED}MISSING NFO{Style.RESET_ALL} {base_path_nfo}')
        else:
            if keep_existing:
                print(f'{datetime.now()} {Fore.GREEN}EXISTING NFO{Style.RESET_ALL} {base_path_nfo}', end='\r')
                return True
            else:
                print(f'{datetime.now()} {Fore.RED}EXISTING NFO{Style.RESET_ALL} {base_path_nfo}', end='\n')
                return False


def fix_nfo_files(files_to_process):
    """
    Fixes NFO files

    files_to_process:  maximum file count to process
    """
    total_counter = 0
    total_files_to_fix = len(files_to_process)

    while total_counter < total_files_to_fix:
        if sleep_time_fix_nfo > 0:
            print(f'{datetime.now()} {Fore.CYAN}WAITING{Style.RESET_ALL} {sleep_time_fix_nfo}s for NFO files...')
            time.sleep(sleep_time_fix_nfo)
        for filename in files_to_process:
            fix_nfo_result = fix_nfo_file(nfo_file=filename)
            if fix_nfo_result:
                total_counter += 1
                print(
                    f'{Fore.GREEN}CREATED{Style.RESET_ALL} {total_counter}/{total_files_to_fix} NFO files {os.path.basename(filename)}',
                    end='\n')

        if total_files_to_fix > 1:
            print(
                f'{datetime.now()} {Fore.GREEN}MODIFIED{Style.RESET_ALL} {total_counter}/{total_files_to_fix} NFO files')

    return total_counter


def fix_all_nfo_files():
    """
    Fixes all NFO files
    """
    print(f'{datetime.now()} Collecting NFO files in {directory_final}')

    nfo_file_list = []

    for directory, folders, files in os.walk(directory_final):
        folders.sort(reverse=True, key=lambda x: os.path.getmtime(os.path.join(directory, x)))
        files.sort(reverse=True, key=lambda x: os.path.getctime(os.path.join(directory, x)))

        for filename in files:
            if create_nfo_files:
                # If we need to create all NFO files, it is no use to only append existing NFOs!
                if regex_mp4.search(filename):
                    nfo_file_list.append(regex_mp4.sub('.nfo', os.path.join(directory, filename)))

            else:
                # Only append existing NFO files to save time
                if regex_nfo.search(filename) and not regex_show_nfo.search(filename) and not regex_season_nfo.search(
                        filename):
                    nfo_file_list.append(os.path.join(directory, filename))

    added_dates = fix_nfo_files(nfo_file_list)
    return added_dates


def verify_fresh_media(status=STATUS['fresh'], regex_media_url=fr'^[a-z0-9\-\_]'):
    if directory_download_home is None:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} download home directory not set!')
        sys.exit()

    text_color = get_text_color_for_media_status(status)
    print(f'{datetime.now()} {Fore.GREEN}VERIFYING{Style.RESET_ALL} {text_color}{status}{Style.RESET_ALL} media '
          f'matching ID regex {regex_media_url}',
          end='\n')

    # TODO: Make this global and use it everywhere for better readability in console Windows or find something better!
    print_path_length = 128

    database = connect_database()

    # TODO: This result is ALWAYS "malformed", since the return format mismatches between our "next gen" Zahhak code and
    ## the original "Old School" Ilus codebase. We NEED to switch these things to OBJECTS and not waste more time
    ## unifying Tuple formats etc. it is exhausting!
    fresh_media = get_media_from_db(database=database,
                                    status=status,
                                    regex_media_url=regex_media_url)

    for current_media in fresh_media:
        # Get basic media info
        try:
            site = current_media[0]
            url = current_media[1]
            status = current_media[3]
            path = os.path.join(directory_download_home, current_media[4])
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_sql:
            print(f'{datetime.now()} {Fore.MAGENTA}ERROR{Style.RESET_ALL}: SQL result malformed! "{current_media}"',
                  end='\n')
            continue

        json_broken = False

        # Big try to catch any unforeseen exceptions
        try:
            if os.path.exists(path):
                # Checks if duration value exists in Info JSON, if not: continue with next media immediately!
                path_json = re.sub(r'\.mp4$', '.info.json', path)
                path_png = re.sub(r'\.mp4$', '.png', path)
                path_vtt_en = re.sub(r'\.mp4$', '.en-orig.vtt', path)
                path_vtt_de = re.sub(r'\.mp4$', '.de-orig.vtt', path)
                if os.path.exists(path_json):
                    with io.open(path_json, encoding='utf-8-sig') as json_txt:
                        duration_json = None
                        try:
                            json_obj = json.load(json_txt)
                            duration_json = float(json_obj['duration'])

                            # This is to check for missing metadata in JSON
                            try:
                                json_description = json_obj['description']
                            except KeyboardInterrupt:
                                sys.exit()
                            except Exception as exception_json:
                                # TODO: In this case, we need to delete the media files(s) too, since the name will be different upon redownload! It would be best to detect this in download!
                                print(
                                    f'{datetime.now()} {Fore.RED}BROKEN{Style.RESET_ALL}: {site} {url} ({os.path.basename(path)[0:print_path_length]}) - Incomplete Info JSON at {path_json}!',
                                    end='\n')
                                json_broken = True

                        except KeyboardInterrupt:
                            sys.exit()
                        except Exception as exception_json:
                            # Patreon sadly does not always give duration in Info JSON files.
                            if site != 'patreon':
                                print(
                                    f'{datetime.now()} {Fore.MAGENTA}ERROR{Style.RESET_ALL}: {site} {url} ({os.path.basename(path)[0:print_path_length]}) - No Duration found in Info JSON at {path_json}!',
                                    end='\n')
                                json_broken = True

                    # TODO: Rework handling of error cases to streamline the process
                    #  We should only mark media as "broken" in ONE way!
                    # A broken Info JSON is immediately deleted and considered wanted to re-grab title!
                    if json_broken:
                        try:
                            # Delete
                            try:
                                os.remove(path)
                            except KeyboardInterrupt:
                                sys.exit()
                            except Exception as exception_delete:
                                print(
                                    f'{datetime.now()} {Fore.MAGENTA}ERROR{Style.RESET_ALL}: deleting {os.path.basename(path)[0:print_path_length]}: {exception_delete}',
                                    end='\n')
                                continue

                            try:
                                os.remove(path_json)
                            except KeyboardInterrupt:
                                sys.exit()
                            except Exception as exception_delete:
                                print(
                                    f'{datetime.now()} {Fore.MAGENTA}ERROR{Style.RESET_ALL}: deleting {os.path.basename(path_json)[0:print_path_length]}: {exception_delete}',
                                    end='\n')

                            try:
                                os.remove(path_png)
                            except KeyboardInterrupt:
                                sys.exit()
                            except Exception as exception_delete:
                                print(
                                    f'{datetime.now()} {Fore.MAGENTA}ERROR{Style.RESET_ALL}: deleting {os.path.basename(path_png)[0:print_path_length]}: {exception_delete}',
                                    end='\n')

                            try:
                                os.remove(path_vtt_de)
                            except KeyboardInterrupt:
                                sys.exit()
                            except Exception as exception_delete:
                                print(
                                    f'{datetime.now()} {Fore.MAGENTA}ERROR{Style.RESET_ALL}: deleting {os.path.basename(path_vtt_de)[0:print_path_length]}: {exception_delete}',
                                    end='\n')

                            try:
                                os.remove(path_vtt_en)
                            except KeyboardInterrupt:
                                sys.exit()
                            except Exception as exception_delete:
                                print(
                                    f'{datetime.now()} {Fore.MAGENTA}ERROR{Style.RESET_ALL}: deleting {os.path.basename(path_vtt_en)[0:print_path_length]}: {exception_delete}',
                                    end='\n')

                            # Update DB
                            update_media_status(media_site=site,
                                                media_id=url,
                                                media_status=STATUS['wanted'])
                            continue

                        except KeyboardInterrupt:
                            sys.exit()
                        except Exception as exception_json:
                            print(
                                f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL}: {exception_json}')

                # A missing Info JSON is immediately considered as an error!
                else:
                    print(
                        f'{datetime.now()} {Fore.RED}BROKEN{Style.RESET_ALL}: {site} {url} ({os.path.basename(path)[0:print_path_length]}) - No Info JSON at {path_json}!',
                        end='\n')
                    try:
                        update_media_status(media_site=site,
                                            media_id=url,
                                            media_status=STATUS['broken'])
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception_sql:
                        pass
                    continue

                # Call FFPROBE to get frame count, frame rate and duration of MP4
                try:
                    print(f'{datetime.now()} {Fore.CYAN}NEW{Style.RESET_ALL} '
                          f'media "{site} {url}" ({os.path.basename(path)[0:print_path_length]}) - '
                          f'{status} - calling FFPROBE...',
                          end='\r')
                    ffprobe_command = ['ffprobe', '-show_entries', 'stream=r_frame_rate,nb_read_frames,duration',
                                       '-select_streams', 'v', '-count_frames', '-of', 'compact=p=1:nk=1', '-threads',
                                       '3', '-v',
                                       '0', path]
                    p = Popen(ffprobe_command, stdout=PIPE, stderr=PIPE)
                    out, err = p.communicate()
                # Critical - Error in FFPROBE handling of file
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_ffprobe:
                    print(f'{datetime.now()} {Fore.MAGENTA}ERROR{Style.RESET_ALL}: ffprobe call failed for {path}!',
                          end='\n')
                    # TODO: We used to update media status to "critical" here.
                    #  AFAIK this point is only reached when FFPROBE install is incorrect
                    continue

                # Get & evaluate results of FFPROBE call
                result_utf = ''
                try:
                    result_utf = out.decode('UTF-8')
                    result_arr = result_utf.split('|')
                    frame_rate_str = result_arr[1]
                    frame_rate_arr = frame_rate_str.split('/')
                    frame_rate = float(frame_rate_arr[0]) / float(frame_rate_arr[1])
                    duration_mp4 = float(result_arr[2])
                    frame_count_correct = frame_rate * duration_mp4
                    # This handles media with 0 (ZERO) frames in them (FFPROBE returns "N/A" instead of 0)
                    try:
                        frame_count_str = re.sub(r'\s*stream\s*', '', str(result_arr[3]))
                        frame_count_actual = float(frame_count_str)
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception_frame_count:
                        print(f'{datetime.now()} {Fore.RED}BROKEN{Style.RESET_ALL}: '
                              f'{site} {url} ({os.path.basename(path)[0:print_path_length]}) - '
                              f'Frame count {result_arr[3]} not a number!',
                              end='\n')
                        try:
                            update_media_status(media_site=site,
                                                media_id=url,
                                                media_status=STATUS['broken'])
                        except KeyboardInterrupt:
                            sys.exit()
                        except Exception as exception_frame_count:
                            pass
                        continue
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_frame_count:
                    try:
                        print(
                            f'{datetime.now()} {Fore.MAGENTA}ERROR{Style.RESET_ALL}: FFPROBE result malformed for {path}! - "{result_utf}"',
                            end='\n')
                        # Update media where FFPROBE returns NOTHING as BROKEN too!
                        if result_utf == '':
                            print(
                                f'{datetime.now()} {Fore.RED}BROKEN{Style.RESET_ALL}: {site} {url} ({os.path.basename(path)[0:print_path_length]}) - Frame count empty!',
                                end='\n')
                            update_media_status(media_site=site,
                                                media_id=url,
                                                media_status=STATUS['broken'])
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception_frame_count:
                        print(
                            f'{datetime.now()} {Fore.MAGENTA}ERROR{Style.RESET_ALL}: FFPROBE evaluation failed for {path}!',
                            end='\n')
                    continue

                # Since Patreon does not always give durations in Info JSON files, we need to assume the length of the MP4 is always correct.
                if site == 'patreon':
                    duration_json = duration_mp4

                # This is to allow more tolerance for SHORT media! e.g.: a 3.2s short may be just 3.0s long and that is fine.
                if duration_json < duration_cutoff:
                    tolerance = tolerance_short
                else:
                    tolerance = tolerance_long

                # Check if MP4 and JSON durations are close enough to consider the MP4 to be complete
                if math.isclose(duration_json, duration_mp4, rel_tol=tolerance):
                    error_count = int(frame_count_correct - frame_count_actual)
                    result_str = f'{frame_rate}fps * {duration_mp4}s = {frame_count_correct}f - {frame_count_actual}f = {error_count} missing Frames.'
                # Durations too far apart are calculated as n errors per missing second, where "n" is the frame rate of the media!
                else:
                    error_count = (duration_json - duration_mp4) * frame_rate
                    result_str = f'Duration incorrect! {duration_json} - {duration_mp4} = {error_count} missing Frames.'

                ### Start of set media status according to error count ###
                # Verified - 0 missing or extra frames
                # if error_count == 0:
                if math.isclose(frame_count_actual, frame_count_correct, rel_tol=0.005):
                    print(
                        f'{datetime.now()} {Fore.GREEN}VERIFIED{Style.RESET_ALL}: {site} {url} ({os.path.basename(path)[0:print_path_length]}) - {result_str}',
                        end='\n')
                    try:
                        update_media_status(media_site=site,
                                            media_id=url,
                                            media_status=STATUS['verified'])
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception_sql:
                        pass
                        # Broken - missing or extra frames above threshold
                elif error_count < (-1 * error_limit_extra) or error_count > error_limit_missing:
                    print(
                        f'{datetime.now()} {Fore.RED}BROKEN{Style.RESET_ALL}: {site} {url} ({os.path.basename(path)[0:print_path_length]}) - {result_str}',
                        end='\n')
                    try:
                        update_media_status(media_site=site,
                                            media_id=url,
                                            media_status=STATUS['broken'])
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception_sql:
                        pass
                # Uncertain - missing or extra frames below threshold
                else:
                    print(
                        f'{datetime.now()} {Fore.YELLOW}UNCERTAIN{Style.RESET_ALL}: {site} {url} ({os.path.basename(path)[0:print_path_length]}) - {result_str}',
                        end='\n')
                    try:
                        update_media_status(media_site=site,
                                            media_id=url,
                                            media_status=STATUS['uncertain'])
                    except KeyboardInterrupt:
                        sys.exit()
                    except Exception as exception_sql:
                        pass
                    print(
                        f'{datetime.now()} {Fore.YELLOW}UNCERTAIN{Style.RESET_ALL}: {site} {url} ({os.path.basename(path)[0:print_path_length]}) - {result_str}',
                        end='\n')
                ### End of set media status according to error count ###

            # MP4 path non-existent is not an error, due to the "Plex Dance" this media should re-appear later and be verified properly then!
            else:
                print(f'{datetime.now()} {Fore.MAGENTA}ERROR{Style.RESET_ALL}: Cannot access {path}!', end='\n')
                # TODO: We used to update media status to "missing" here, but it should be found automatically later.

        # Generic unforeseen error catch-all
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_general:
            print(
                f'{datetime.now()} {Fore.MAGENTA}CRITICAL{Style.RESET_ALL}: {site} {url} ({os.path.basename(path)[0:print_path_length]}) - Unexpected exception',
                end='\n')

    # Relaxed approach to an infinite loop
    print(f'{datetime.now()} {Fore.YELLOW}No more media to verify!{Style.RESET_ALL} '
          f'Waiting {sleep_time_verification}s before next SQL SELECT...',
          end='\n')
    time.sleep(sleep_time_verification)
    return


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Zahhak")

    parser.add_argument("--vpn",
                        help="Enable VPN reconnecting for this instance",
                        action=argparse.BooleanOptionalAction, )

    parser.add_argument("--mode",
                        choices=('A', 'M', 'D', 'V', 'J'),
                        help="'A' for Add Subscriptions, "
                             "'M' for Monitor Subscriptions, "
                             "'D' for Download Media, "
                             "'V' for Verify Files, "
                             "'J' for Juggle Files, "
                             "EMPTY to run in serial mode. ",
                        type=str,
                        required=False, )

    parser.add_argument("--letter_low",
                        type=str,
                        help="Enter low starting letter for URL",
                        nargs='?',
                        default=' ',
                        const=0, )

    parser.add_argument("--letter_high",
                        type=str,
                        help="Enter high starting letter for URL",
                        nargs='?',
                        default=' ',
                        const=0, )

    parser.add_argument("--status",
                        help="Enter a list of status values to consider",
                        nargs='+', )

    args = parser.parse_args()

    init(convert=True)
    just_fix_windows_console()

    # Skips ALL processing of known media to speed up skript
    create_download_archive()

    '''Parse enable VPN'''
    if args.vpn:
        enable_vpn = True
    else:
        enable_vpn = False

    '''Parse status values for download'''
    if args.status:
        for status in args.status:
            if status not in STATUS.values():
                print(f'{datetime.now()} {Fore.RED}UNKNOWN STATUS VALUE{Style.RESET_ALL}: '
                      f'{status} not in ({STATUS.values()}) aborting to avoid database errors!')
                sys.exit()
        status_values = args.status
    else:
        status_values = [STATUS['broken'], STATUS['wanted'], STATUS['private']]

    '''Parse URL regex for verification'''
    # TODO: This should probably be done with argparse error instead!
    letter_low = args.letter_low.lower()
    if not letter_low:
        # print(f'Missing parameter "--letter_low"!')
        # sys.exit()
        letter_low = ' '
    letter_high = args.letter_high.lower()
    if not letter_high:
        # print(f'Missing parameter "--letter_high"!')
        # sys.exit()
        letter_high = ' '
    if ord(letter_low) > ord(letter_high):
        print(f'Invalid input, low letter {letter_low} is not preceding high letter {letter_high}!')
        sys.exit()
    if letter_low == ' ' and letter_high == ' ':
        regex_filter_media = fr'^[a-z0-9\-\_]'
        regex_filter_channel = fr'^UC[a-z0-9\-\_]'
    elif letter_low == '0' and letter_high == '9':
        regex_filter_media = fr'^[{letter_low}-{letter_high}\-\_]'
        regex_filter_channel = fr'^UC[{letter_low}-{letter_high}\-\_]'
    else:
        regex_filter_media = fr'^[{letter_low}-{letter_high}]'
        regex_filter_channel = fr'^UC[{letter_low}-{letter_high}]'

    '''Parse mode'''
    if not args.mode:
        INPUT_POSSIBLE = True
        print(f'{datetime.now()} {Fore.YELLOW}WARNING{Style.RESET_ALL}: '
              f'no operating mode was set. Running in user interactive mode!')
        while True:
            add_subscriptions()
            update_subscriptions(regex_channel_url=regex_filter_channel)
            download_all_media(status_values=status_values, regex_media_url=regex_filter_media)
            verify_fresh_media(regex_media_url=regex_filter_media)
            juggle_verified_media()

    elif len(args.mode) == 1:
        INPUT_POSSIBLE = False
        if args.mode == 'A':
            print(f'{datetime.now()} {Fore.CYAN}MODE{Style.RESET_ALL}: '
                  f'Add Subscriptions')
            while True:
                add_subscriptions()

        elif args.mode == 'M':
            print(f'{datetime.now()} {Fore.CYAN}MODE{Style.RESET_ALL}: '
                  f'Monitor Subscriptions')
            while True:
                update_subscriptions(regex_channel_url=regex_filter_channel)

        elif args.mode == 'D':
            print(f'{datetime.now()} {Fore.CYAN}MODE{Style.RESET_ALL}: '
                  f'Download Media')
            while True:
                download_all_media(status_values=status_values, regex_media_url=regex_filter_media)

        elif args.mode == 'V':
            print(f'{datetime.now()} {Fore.CYAN}MODE{Style.RESET_ALL}: '
                  f'Verify Files')

            while True:
                verify_fresh_media(regex_media_url=regex_filter_media)

        elif args.mode == 'J':
            print(f'{datetime.now()} {Fore.CYAN}MODE{Style.RESET_ALL}: '
                  f'Juggle Files')
            while True:
                juggle_verified_media()

        else:
            print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL}: '
                  f'No mode "{args.mode}" exists')

    else:
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL}: '
              f'Malformed arguments found!')
