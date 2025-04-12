import json
import os
import random
import re
import sys
import time
from datetime import datetime
from subprocess import STDOUT, check_output

import mysql.connector
import yt_dlp
from colorama import init, just_fix_windows_console, Fore, Style

# TODO: Extract Flat causes only first page to be loaded. Bug is old, but certainly back: https://github.com/ytdl-org/youtube-dl/issues/28075
# TODO: Look into using logger, progress_hooks, progress (https://github.com/yt-dlp/yt-dlp/issues/66)
# TODO: Ignoring no format error leads to unavailable videos to also be in entries (videos) list (for playlists at least), this is now handled by checking the date and passing if none can be found. Since this leaves us a bit open to ignoring date oddities, we should look into filtering these unavailable videos out (do NOT remove ingore no format error option, it will lead to ABORTION!) https://github.com/yt-dlp/yt-dlp/issues/9810
# TODO https://www.reddit.com/r/youtubedl/comments/1berg2g/is_repeatedly_downloading_api_json_necessary/

'''Download directory settings'''
directory_download_temp = os.getenv('ZAHHAK_DIR_DOWNLOAD_TEMP', 'C:\#Temp\YouTube')
directory_download_home = os.getenv('ZAHHAK_DIR_DOWNLOAD_HOME', 'D:\Plex\#Incomplete\YouTube')

'''MySQL settings'''
mysql_host = os.getenv('ZAHHAK_MYSQL_HOSTNAME', 'localhost')
mysql_database = os.getenv('ZAHHAK_MYSQL_DATABASE', 'zahhak')
mysql_user = os.getenv('ZAHHAK_MYSQL_USERNAME', 'admin')
mysql_password = os.getenv('ZAHHAK_MYSQL_PASSWORD', 'admin')

'''Variables'''
# Enable or disable VPN reconnect functionality
enable_vpn = True
# Frequency to reconnect VPN (in seconds)
sleep_time_vpn = 0
# How often to retry connecting to a VPN country before giving up
retry_reconnect_new_vpn_node = 5

# Countries to connect to with NordVPN
vpn_countries = [
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
    'Moldova',
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
retry_channel_before_ignoring_errors = len(vpn_countries) * 1 * retry_channel_before_reconnecting_vpn
# Times to try channel video page processing before giving up entirely
retry_channel_before_giving_up = len(vpn_countries) * 2 * retry_channel_before_reconnecting_vpn  #

# Timeout for channel video page extraction (in seconds)
timeout_playlist = 24
# YT-DLP internal retry for full playlist page extraction
retry_extraction_playlist = 2
# Times to try playlist page processing before reconnecting NordVPN (if enabled) - this repeats every X tries!
retry_playlist_before_reconnecting_vpn = 1
# Times to try full playlist page processing before switching to using ignore_errors to accept partial processing
retry_playlist_before_ignoring_errors = len(vpn_countries) * 1 * retry_playlist_before_reconnecting_vpn
# Times to try playlist page processing before giving up entirely
retry_playlist_before_giving_up = len(vpn_countries) * 2 * retry_playlist_before_reconnecting_vpn  #

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

# Use 0.0.0.0 to force IPv4
external_ip = '0.0.0.0'

# Only log warnings from yt-dlp and wrapper messages from Ilus
quiet_check_channel_info = True
quiet_check_channel_warnings = True
quiet_channel_info = True
quiet_channel_warnings = True
quiet_playlist_info = True
quiet_playlist_warnings = True
quiet_download_info = False
quiet_download_warnings = False

# Extract FLAT
# TODO: Combined with ignore Errors != False sometimes only loads first page?!?!?!
extract_flat_channel = True  # Can be True for faster processing IF ignore_errors is False and NOT 'only_download'! (causes frequent incomplete checks of channel state, which can prevent playlist checking from happening!)
extract_flat_playlist = False  # Leave as False to avoid extraction of every single video AFTER playlist (often detected as bot!)

# Availability Filter
# filter_availability = 'availability=public,unlisted,needs_auth,subscriber_only,premium_only'
filter_availability = 'availability=public,unlisted'

# Set ignore error options
# TODO: Look into what happens if you use False, catch an error like "Private Video" and then do nothing with it. e.g. will yt-dlp continue on
# TODO: Maybe revert to ignoring errors on channel pages for faster runs? (channels will be checked frequently, and new videos should always be on 1st page. Eventually we will get a full list, given enough reruns)
# False --> Getting full list of videos ends when one will not load, is private, is age restricted, etc. we get NO list of videos at all! (IDK is this can be made to work so private videos etc. are filtered out using filter, we need to TEST this!)
DEFAULT_ignore_errors_channel = False
DEFAULT_ignore_errors_playlist = False
# 'only_download' --> We do not always get a full list of videos, but at least we get A list at all!
# DEFAULT_ignore_errors_channel           = 'only_download'
# DEFAULT_ignore_errors_playlist          = 'only_download'


'''REGEX'''
# Channel names
regex_live_channel = re.compile(r'.* LIVE$')
regex_fake_channel = re.compile(r'^#.*$')

# YT-DLP Error messages
regex_empty_channel = re.compile(r'This channel does not have a videos tab')
regex_channel_deleted = re.compile(r'This channel is not available')
regex_playlist_deleted = re.compile(r'The playlist does not exist')
regex_video_age_restricted = re.compile(r'Sign in to confirm your age')
regex_video_private = re.compile(r'Private video')
regex_video_unavailable = re.compile(r'Video unavailable')
regex_video_removed = re.compile(r'This video has been removed')
regex_video_members_only = re.compile(
    r'Join this channel to get access to members-only content like this video, and other exclusive perks')
regex_video_members_tier = re.compile(r'This video is available to this channel')
regex_video_duplicate = re.compile(r'Duplicate entry')
regex_error_connection = re.compile(r'Remote end closed connection without response')
regex_error_timeout = re.compile(r'The read operation timed out')
regex_error_getaddrinfo = re.compile(r'getaddrinfo failed')
# noinspection RegExpRedundantEscape
regex_val = re.compile(r'[^\.a-zA-Z0-9 -]')
regex_caps = re.compile(r'[A-Z][A-Z]+')

'''STRINGS'''
playlist_name_livestreams = 'Livestreams'
playlist_name_shorts = 'Shorts'

'''DEBUG'''
DEBUG_empty_video = False
DEBUG_add_video = False
DEBUG_force_date = False
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
DEFAULT_vpn_frequency = 100
vpn_frequency = DEFAULT_vpn_frequency


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
            print(f'{datetime.now()} Creating download archive from DB', end="\n")

            mydb = connect_database()
            mysql_cursor = mydb.cursor()
            sql = "SELECT videos.site AS 'site', videos.url AS 'url' FROM videos;"
            mysql_cursor.execute(sql)

            result_archive = mysql_cursor.fetchall()

            counter_archive = 0
            for x in result_archive:
                counter_archive += 1
                print(f'Creating download archive from DB ({counter_archive}/{len(result_archive)})', end="\r")
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


def update_channel(date, channel):
    """Updates last checked date for channel"""

    channel_site = channel[0]
    channel_id = channel[1]
    channel_name = channel[2]

    # Update DB
    try:
        mydb = connect_database()
        mysql_cursor = mydb.cursor()

        sql = "UPDATE channels SET date_checked = %s WHERE site = %s AND url = %s;"
        val = (date, channel_site, channel_id)

        if DEBUG_update_channel:
            input(val)

        mysql_cursor.execute(sql, val)
        mydb.commit()

        print(f'{datetime.now()} {Fore.CYAN}MARKED{Style.RESET_ALL} channel '
              f'"{channel_site} {channel_id}" as checked on {date}')
        return True

    except KeyboardInterrupt:
        sys.exit()

    except Exception as exception_update_channel:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while marking channel '
              f'"{channel_name}" ({channel_site} {channel_id}): {exception_update_channel}')
        return False


def update_playlist(date, playlist):
    """Updates last checked date for playlist"""

    playlist_site = playlist[0]
    playlist_id = playlist[1]
    playlist_name = playlist[2]

    # Update DB
    try:
        mydb = connect_database()

        mysql_cursor = mydb.cursor()

        sql = "UPDATE playlists SET date_checked = %s WHERE site = %s AND url = %s;"
        val = (date, playlist_site, playlist_id)

        if DEBUG_update_playlist:
            input(val)

        mysql_cursor.execute(sql, val)
        mydb.commit()

        print(f'{datetime.now()} {Fore.CYAN}MARKED{Style.RESET_ALL} playlist '
              f'"{playlist_name}" ({playlist_site} {playlist_id}) as checked on {date}')
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

    # Ingoring errors here would be uniwse, I think...
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
        'ignore_no_formats_error': True,
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
        ilus.close()
    except KeyboardInterrupt:
        # DEBUG: Skip problematic channels
        # return False
        sys.exit()
    except Exception as exception_missing_videos_channel:
        if regex_empty_channel.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}EMPTY{Style.RESET_ALL} channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            # TODO: Update checked date? Return number etc. and in this case, return special case?
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
        elif regex_error_getaddrinfo.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}GET ADDR INFO FAILED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return False
        elif regex_channel_deleted.search(str(exception_missing_videos_channel)):
            print(
                f'{datetime.now()} {Fore.RED}GEO BLOCKED{Style.RESET_ALL} while adding channel '
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

    # Filter out members only content on the channel lavel
    filter_text = filter_availability

    # Set channel URL
    channel_url = f'https://www.youtube.com/channel/{channel_id}/videos'

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
        'ignore_no_formats_error': True,
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
        ilus.close()
    except KeyboardInterrupt:
        # DEBUG: Skip problematic channels
        # return False
        sys.exit()
    except Exception as exception_missing_videos_channel:
        if regex_empty_channel.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}EMPTY{Style.RESET_ALL} channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            # TODO: Update checked date? Return number etc. and in this case, return special case?
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
        elif regex_error_getaddrinfo.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}GET ADDR INFO FAILED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
            vpn_frequency = DEFAULT_vpn_frequency
            return None
        elif regex_channel_deleted.search(str(exception_missing_videos_channel)):
            print(f'{datetime.now()} {Fore.RED}GEO BLOCKED{Style.RESET_ALL} while adding channel '
                  f'"{channel_name}" ({channel_site} {channel_id})')
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
                      f'"{channel_name}" ({channel_site} {channel_id})')
            else:
                print(f'{datetime.now()} {Fore.CYAN}NO{Style.RESET_ALL} new videos for channel '
                      f'"{channel_name}" ({channel_site} {channel_id})')

            return videos
        else:
            # TODO: IDK if channel handeling in main can handle this, so I am just sending None as in other error cases
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
        filter_text = filter_availability + ' & !is_live & tags !*= shorts'
    elif playlist_name == playlist_name_shorts:
        print(f'{datetime.now()} {Fore.CYAN}SHORTS{Style.RESET_ALL} playlist '
              f'"{playlist_name}" ({playlist_site} {playlist_id})')
        filter_text = filter_availability + ' & !is_live & !was_live'
    else:
        filter_text = filter_availability + ' & !is_live & !was_live & tags !*= shorts'

    # Set playlist URL
    # User Channel
    if re.search("^UC.*$", playlist_id):
        # Standard format for YouTube channel IDs (e.g. all videos "playlist")
        playlist_url = f'https://www.youtube.com/channel/{playlist_id}/videos'
        timeout = timeout_channel

        if counter > 3:
            # TODO: This needs to be aware of outer counter and only happen once variable retry_full_channel_before_ignoring_errors is reached (in next version maybe)
            ignore_errors = 'only_download'
    # Play List
    elif re.search("^PL.*$", playlist_id):
        # Standard format for YouTube playlist IDs
        playlist_url = f'https://www.youtube.com/playlist?list={playlist_id}'
        timeout = timeout_playlist

    else:
        # ID format unknown
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL}: Unknown ID format '
              f'"{playlist_name}" ({playlist_site} {playlist_id})')
        return []  # Return empty list to not trigger continuous retry on playlists with unknown format

    # Set download options for YT-DLP
    playlist_download_options = {
        'logger': VoidLogger(),
        'extract_flat': extract_flat_playlist,
        'skip_download': True,
        'allow_playlist_files': False,
        'lazy_playlist': True,
        'quiet': quiet_playlist_info,
        'no_warnings': quiet_playlist_warnings,
        'cachedir': False,
        'ignoreerrors': ignore_errors,
        'ignore_no_formats_error': True,
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
        ilus.close()

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

        elif regex_error_getaddrinfo.search(str(exception_missing_videos_playlist)):
            print(f'{datetime.now()} {Fore.RED}GET ADDR INFO FAILED{Style.RESET_ALL} while adding playlist '
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
            # TODO: IDK if playlist handeling in main can handle this, so I am just sending None as in other error cases
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

    print(f'{datetime.now()} Collecting channels...')

    mydb = connect_database()

    mysql_cursor = mydb.cursor()

    sql = ("SELECT channels.site, channels.url, channels.name, channels.priority "
           "FROM channels "
           "WHERE site = %s "
           "AND channels.url IN(SELECT playlists.channel FROM playlists GROUP BY playlists.channel HAVING count(*) > 0) "
           "ORDER BY channels.priority DESC, channels.date_checked ASC, RAND();")
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

    print(f'{datetime.now()} Collecting playlists for "{channel_name}" ({channel_site} {channel_id})')

    playlists = []
    retry_db = True
    while retry_db:
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
               "AND playlists.done IS NOT true "
               "AND NOT EXISTS ( SELECT 1 FROM videos WHERE videos.playlist = playlists.url ) "
               "ORDER BY playlists.priority DESC, playlists.date_checked ASC, RAND();")
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
               "AND playlists.done IS NOT true "
               "AND EXISTS ( SELECT 1 FROM videos WHERE videos.playlist = playlists.url ) "
               "ORDER BY playlists.priority DESC, playlists.date_checked ASC, RAND();")
        val = ('youtube', channel_id)
        mysql_cursor.execute(sql, val)
        mysql_result = mysql_cursor.fetchall()
        # playlists.append(mysql_result)
        for entry in mysql_result:
            playlists.append(entry)

        retry_db = False

    return playlists


def get_video_details(video_id, archive_set):
    """Fills the details for a video by its ID"""

    # Try-Except Block to handle YT-DLP exceptions such as "playlist does not exist"
    # try:
    #
    video_url = f'https://www.youtube.com/watch?v={video_id}'

    # Set download options for YT-DLP
    video_download_options = {
        'skip_download': True,
        'allow_playlist_files': False,
        'cachedir': False,
        'ignoreerrors': False,
        'download_archive': archive_set,
        'extractor_args': {'youtube': {'skip': ['configs', 'webpage', 'js']}},
        'extractor_retries': retry_extraction_video,
        'socket_timeout': timeout_video,
        'source_address': external_ip
    }

    # Run YT-DLP
    with yt_dlp.YoutubeDL(video_download_options) as ilus:
        info_json = ilus.sanitize_info(ilus.extract_info(video_url, process=True, download=False))
    ilus.close()

    if DEBUG_json_video_details:
        with open('debug.json', 'w', encoding='utf-8') as json_file:
            # noinspection PyTypeChecker
            json.dump(info_json, json_file, ensure_ascii=False, indent=4)
        input(f'Dumped JSON... Continue?')

    return info_json
    # except KeyboardInterrupt:
    #    sys.exit()
    # except Exception as e:
    # print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while getting details for video "{video_id}": {e}')
    # return None


def get_channel_details(channel_url, ignore_errors):
    print(f'{datetime.now()} Getting ID for channel "{channel_url}"')

    # Set download options for YT-DLP
    channel_download_options = {'extract_flat': True,
                                'skip_download': True,
                                'allow_playlist_files': False,
                                'quiet': True,
                                'no_warnings': True,
                                # 'noplaylist': True,
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
        ilus.close()

        if DEBUG_channel_id:
            with open('debug.json', 'w', encoding='utf-8') as f:
                json.dump(info_json, f, ensure_ascii=False, indent=4)
            input(f'Dumped JSON... Continue?')

        try:
            info_json['id']
            return info_json
        except:
            print(
                f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} cannot find channel ID in Info JSON "{info_json}"')
            return None
            # TODO: To make this work properly, we need to count retries and give up at some point, I guess?
            # return [] # This is to stop repeating to try in this (rare) case of not getting entries for playlist EVER (cause unknown, possibly related to single video lists or hidden videos etc.)

    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding channel from URL "{channel_url}": {e}')
        return None


def add_video(video, channel_site, channel_id, playlist_id, download, archive_set):
    """Adds a video to given playlist/channel in database"""
    if video is None:
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} no video!')
        if DEBUG_empty_video:
            input('Continue?')
        return False

    if DEBUG_json_video_add:
        with open('debug.json', 'w', encoding='utf-8') as json_file:
            # noinspection PyTypeChecker
            json.dump(video, json_file, ensure_ascii=False, indent=4)
        input(f'Dumped JSON... Continue?')

    try:
        video_site = channel_site
        video_id = video['id']
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_add_video:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding video "{video}": '
              f'{exception_add_video}')
        return False

    # Reset dates
    original_date = None
    upload_date = None
    release_date = None

    # Set info fields for use in database entry
    try:
        # This is NOT in flat playlist JSON, if we want to use flat, we need to extract videos individually!
        video_channel_id = video['channel_id']

        try:
            upload_date = video['upload_date']
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_date:
            print(exception_date)

        try:
            release_date = video['release_date']
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_date:
            print(exception_date)

    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_add_video:
        print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} reading local video details, retrying online '
              f'({exception_add_video})')
        try:
            # Get all info for video online (necessary in case of flat extraction)
            info_json = get_video_details(video_id, global_archive_set)

            if DEBUG_force_date:
                try:
                    with open('DEBUG_info_json.json', 'w', encoding='utf-8') as json_file:
                        # noinspection PyTypeChecker
                        json.dump(info_json, json_file, ensure_ascii=False, indent=4)
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_debug:
                    print(exception_debug)

                try:
                    with open('DEBUG_video.json', 'w', encoding='utf-8') as json_file:
                        # noinspection PyTypeChecker
                        json.dump(video, json_file, ensure_ascii=False, indent=4)
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_debug:
                    print(exception_debug)

                input(f'Dumped JSON... Continue?')

            video_channel_id = info_json['channel_id']

            if upload_date is None:
                try:
                    upload_date = info_json['upload_date']
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_date:
                    print(exception_date)

            if release_date is None:
                try:
                    release_date = info_json['release_date']
                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_date:
                    print(exception_date)

            # video_id = info_json['id']
            # site = info_json['extractor']

        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_add_video:
            if regex_video_members_only.search(str(exception_add_video)) or regex_video_members_tier.search(
                    str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}MEMBERS ONLY{Style.RESET_ALL} video "{video_id}"')
                return False

            elif regex_video_removed.search(str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}REMOVED{Style.RESET_ALL} video "{video_id}"')
                return False

            elif regex_video_unavailable.search(str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}UNAVAILABLE{Style.RESET_ALL} video "{video_id}"')
                return False

            elif regex_video_private.search(str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}PRIVATE{Style.RESET_ALL} video "{video_id}"')
                return False

            elif regex_video_age_restricted.search(str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}AGE RESTRICTED{Style.RESET_ALL} video "{video_id}"')

                # Update DB
                try:
                    mydb = connect_database()

                    mysql_cursor = mydb.cursor()

                    sql = ("INSERT INTO videos (channel, playlist, site, url, status, download) "
                           "VALUES (%s, %s, %s, %s, %s, %s);")
                    val = (channel_id, playlist_id, channel_site, video_id, 'age-restricted', download)

                    if DEBUG_unavailable:
                        input(val)

                    mysql_cursor.execute(sql, val)
                    mydb.commit()

                    archive_set.add(f'{channel_site} {video_id}')

                    print(f'{datetime.now()} {Fore.CYAN}ADDED AGE RESTRICTED{Style.RESET_ALL} video "{video_id}"')
                    return True

                except KeyboardInterrupt:
                    sys.exit()
                except Exception as exception_add_video:
                    if regex_video_duplicate.search(str(exception_add_video)):
                        print(f'{datetime.now()} {Fore.RED}DUPLICATE{Style.RESET_ALL} video "{video_id}"')
                        return True
                    else:
                        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding '
                              f'{Fore.RED}UNAVAILABLE{Style.RESET_ALL} video "{video_id}": {exception_add_video}')
                        return False

            else:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding video "{video}": '
                      f'{exception_add_video}')
                # Return None to trigger retry
                return None

    try:
        if video['availability'] is None:
            print(f'{datetime.now()} {Fore.RED}PRIVATE{Style.RESET_ALL} video "{video_id}"')
            return False
    except KeyboardInterrupt:
        sys.exit()
    except Exception as exception_check_private:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} checking private video: '
              f'{exception_check_private}')
        return True

    # Get date
    if original_date is None:
        try:
            original_date = datetime.strptime(upload_date, '%Y%m%d').strftime('%Y-%m-%d')
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_add_video:
            print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL}: No upload date in info JSON! '
                  f'({exception_add_video})')
    if original_date is None:
        try:
            original_date = datetime.strptime(release_date, '%Y%m%d').strftime('%Y-%m-%d')
        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_add_video:
            print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL}: No release date in info JSON! '
                  f'({exception_add_video})')

    # Update DB
    if original_date is not None:
        try:
            print(f'{datetime.now()} {Fore.GREEN}FOUND{Style.RESET_ALL} missing video {video_id}', end='\r')

            if download:
                video_status = 'wanted'
            else:
                video_status = 'unwanted'

            mydb = connect_database()

            mysql_cursor = mydb.cursor()
            sql = ("INSERT INTO videos (channel, playlist, site, url, status, original_date, download) "
                   "VALUES (%s, %s, %s, %s, %s, %s, %s)")
            val = (video_channel_id, playlist_id, video_site, video_id, video_status, original_date, download)
            if DEBUG_add_video:
                input(val)
            mysql_cursor.execute(sql, val)
            mydb.commit()

            archive_set.add(f'{video_site} {video_id}')

            print(f'{datetime.now()} {Fore.GREEN}ADDED{Style.RESET_ALL} video "{video_id}"')
            return True

        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_add_video:
            if regex_video_duplicate.search(str(exception_add_video)):
                print(f'{datetime.now()} {Fore.RED}DUPLICATE{Style.RESET_ALL} video "{video_id}"')
                return True
            else:
                print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding video "{video_id}": '
                      f'{exception_add_video}')
                return False


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
    except Exception as e:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding playlist '
              f'"{channel_name}" ({channel_site} {channel_id}): {e}')
        return None


def add_playlist(playlist_id, playlist_name, channel_id, download):
    playlist_site = 'youtube'

    if channel_id == playlist_id:
        playlist_priority = 0
    elif download:
        playlist_priority = 100
    else:
        playlist_priority = -1

    try:
        mydb = mysql.connector.connect(
            host=mysql_host,
            user=mysql_user,
            password=mysql_password,
            database=mysql_database)

        mysql_cursor = mydb.cursor()

        sql = "INSERT INTO playlists (site, url, name, channel, priority, download) VALUES (%s, %s, %s, %s, %s, %s)"
        val = (playlist_site, playlist_id, playlist_name, channel_id, playlist_priority, download)
        mysql_cursor.execute(sql, val)
        mydb.commit()

        print(f'{datetime.now()} {Fore.GREEN}NEW PLAYLIST{Style.RESET_ALL}: '
              f'"{playlist_name}" ({playlist_site} {playlist_id})')
        print()

    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while adding playlist '
              f'"{playlist_name}" ({playlist_site} {playlist_id}): {e}')
        return None


def sanitize_name(name, is_user=False):
    name_sane = name
    # TODO: This seems overcomplicated to implement ourselves, we should seek a pre-existing package that does this!

    if regex_val.search(name_sane) or regex_caps.search(name):
        # TODO: This way of doing things does not fix things written in ALL CAPS. We should look into how to best handle all ways of wirting

        # German Umlaute
        name_sane = re.sub(r'ä', 'ae', name_sane)
        name_sane = re.sub(r'Ä', 'AE', name_sane)
        name_sane = re.sub(r'ö', 'oe', name_sane)
        name_sane = re.sub(r'Ö', 'OE', name_sane)
        name_sane = re.sub(r'ü', 'ue', name_sane)
        name_sane = re.sub(r'Ü', 'UE', name_sane)
        name_sane = re.sub(r'ß', 'ss', name_sane)

        # English Apostrophs
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

        # Alternative hyphens to real hypens
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


def reconnect_vpn(counter):
    """Reconnects NordVPN to a random country from list"""

    if enable_vpn:
        timestamp = datetime.now()
        time_difference = (timestamp - vpn_timestamp).total_seconds()
        if time_difference < vpn_frequency:
            sleep_time = vpn_frequency - time_difference
            print(f'{datetime.now()} {Fore.YELLOW}WAITING{Style.RESET_ALL} {sleep_time}s before reconnecting', end='\n')
            time.sleep(sleep_time)

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


def get_wanted_videos_from_db():
    """
    Returns a list of all wanted YouTube videos als list of lists
    Inner list field order is as follows:
      - videos.site
      - videos.url
      - videos.original_date
      - channels.name
      - playlists.name
      """

    print(f'{datetime.now()} Collecting channels...')

    mydb = connect_database()

    mysql_cursor = mydb.cursor()

    sql = ("SELECT videos.site, videos.url, videos.original_date, channels.name, playlists.name, "
           "FROM videos "
           "INNER JOIN playlists ON videos.playlist=playlists.url "
           "INNER JOIN channels ON playlists.channel=channels.url "
           "WHERE videos.status = 'wanted' "
           "AND videos.download IS TRUE "
           "ORDER BY EXTRACT(year FROM videos.original_date) DESC, EXTRACT(month FROM videos.original_date) DESC, "
           "channels.priority DESC, channels.priority DESC, playlists.priority DESC, videos.original_date DESC;")
    mysql_cursor.execute(sql)
    mysql_result = mysql_cursor.fetchall()
    return mysql_result


def download_all_videos():
    all_videos = get_wanted_videos_from_db()
    for current_video in all_videos:
        download_video(video=current_video)


def download_video(video):
    video_site = video[0]
    video_id = video[1]
    video_date = video[2]
    channel_name = video[3]
    playlist_name = video[4]

    #  TODO: Clear temp directory

    print(f'{datetime.now()} {Fore.CYAN}DOWNLOADING{Style.RESET_ALL} video "{video_site} - {video_id}"')

    if video_site == 'youtube':
        # Set the full output path
        full_path = os.path.join(f'{channel_name} - {playlist_name}',
                                 f'Season %(release_date>%Y,upload_date>%Y)s [{channel_name}]',
                                 f'{channel_name} - {playlist_name} - '
                                 f'S%(release_date>%Y,upload_date>%Y)sE%(release_date>%j,upload_date>%j)s - '
                                 f'%(title)s.%(ext)s')
        print(f'Path for video "{video_site} {video_id}": {full_path}')

        video_url = f'https://www.youtube.com/watch?v={video_id}'

        # Set download options for YT-DLP
        video_download_options = {
            # 'logger': CaptureLogger(),
            'quiet': quiet_download_info,
            'no_warnings': quiet_download_warnings,
            'cachedir': False,
            'skip_unavailable_fragments': False, # To abort on missing video parts (largely avoids re-downloading)
            'ignoreerrors': False,
            'ignore_no_formats_error': True, # To skip unavailable videos
            'extractor_retries': retry_extraction_download,
            'socket_timeout': timeout_download,
            'source_address': external_ip,
            'nocheckcertificate': True,
            'restrictfilenames': True,
            'windowsfilenames': True,
            'throttledratelimit': 1000,
            'retries': 10,
            'concurrent_fragment_downloads': 20,
            'overwrites': False,
            'writethumbnail': True,
            'embedthumbnail': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'writeinfojson': True,
            'allow_playlist_files': False,
            #'check_formats': True,
            #'format': 'bv*[ext=mp4]+ba*[ext=m4a]/b'
            'format': 'bestvideo*[ext=mp4][height<=1080]+bestaudio[ext=m4a]',
            'allow_multiple_audio_streams': True,
            'merge_output_format': 'mp4',
            'subtitleslangs': ['de-orig','en-orig'],
            'paths': {
                'temp': directory_download_temp,
                'home': directory_download_home,
            },
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            }, {
                'key': 'FFmpegMetadata',
                'add_metadata': True,
            }, {
                'key': 'EmbedThumbnail',
            }, {
                'key': 'FFmpegThumbnailsConvertor',
                'format': 'png',
                'when': 'before_dl'
            }],
        }

        # Try-Except Block to handle YT-DLP exceptions such as "playlist does not exist"
        try:
            info_json = None
            # Run YT-DLP
            with yt_dlp.YoutubeDL(video_download_options) as ilus:
                info_json = ilus.sanitize_info(ilus.extract_info(video_url, process=True, download=True))
                #ilus.download(video_url)
            ilus.close()

        except KeyboardInterrupt:
            sys.exit()
        except Exception as exception_download:
            print(exception_download)

        # TODO: Update Database

    r'''# YT-DLP config
# Do not remove sponsored segments
--no-sponsorblock

--recode mp4

# Do not continue download started before (as this willl lead to corruption if initial download was interrupted in any way, including brief internet outages or packet loss)
--no-continue

# Update MySQL
--exec "after_move:python .\update_database.py %(extractor)q %(id)q %(filepath)q"

# Set Retry Handeling
--retry-sleep 1
--file-access-retries 1000
--fragment-retries 30
--extractor-retries 3

# Abort when redirected to "Video Not Available"-page, pieces of video are missing, or any other errors happen
--break-match-filters "title!*=Video Not Available"
    '''


def get_monitored_playlists_from_db():
    """Returns all playlists as list of lists

    Inner list field order is as follows:
      - playlists.site
      - playlists.url
      - playlists.name
      - playlists.priority
      - channels.url
      - channels.name
      - channels.priority
      - playlists.download"""

    print(f'{datetime.now()} Collecting all playlists')

    playlists = []
    retry_db = True
    while retry_db:
        mydb = connect_database()

        mysql_cursor = mydb.cursor()

        playlists = []

        # Get playlists with no videos in them
        sql = ("SELECT playlists.site, playlists.url, playlists.name, playlists.priority, "
               "channels.url, channels.name, channels.priority, playlists.download "
               "FROM playlists "
               "INNER JOIN channels on playlists.channel=channels.url "
               "WHERE playlists.site = %s "
               "AND playlists.done IS NOT true "
               "AND NOT EXISTS ( SELECT 1 FROM videos WHERE videos.playlist = playlists.url ) "
               "ORDER BY playlists.priority DESC, playlists.date_checked ASC, RAND();")
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
               "AND playlists.done IS NOT true "
               "AND EXISTS ( SELECT 1 FROM videos WHERE videos.playlist = playlists.url ) "
               "ORDER BY playlists.priority DESC, playlists.date_checked ASC, RAND();")
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


def get_all_channel_playlists_from_youtube(channel, ignore_errors):
    """Returns a list of all online YouTube playlists for the given channel"""
    channel_id = channel[1]
    print(f'{datetime.now()} Collecting playlists for channel "{channel_id}"')

    channel_playlists_url = f'https://www.youtube.com/channel/{channel_id}/playlists'

    playlists = []

    # Set download options for YT-DLP
    channel_playlists_download_options = {'extract_flat': True,
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
        ilus.close()

        if DEBUG_channel_playlists:
            with open('debug.json', 'w', encoding='utf-8') as json_file:
                # noinspection PyTypeChecker
                json.dump(info_json, json_file, ensure_ascii=False, indent=4)
            input(f'Dumped JSON... Continue?')

        try:
            playlists = info_json['entries']
            if playlists[0] is not None:
                playlists_count = len(playlists)
                print(f'{datetime.now()} {Fore.GREEN}FOUND{Style.RESET_ALL} {playlists_count} playlists for channel '
                      f'"{channel_id}"')
                return playlists
        except KeyboardInterrupt:
            sys.exit()
        except Exception as e:
            print(f'{datetime.now()} {Fore.RED}ERROR{Style.RESET_ALL} cannot find entries in Info JSON "{info_json}": '
                  f'{e}')
            return None

    except KeyboardInterrupt:
        sys.exit()
    except Exception as e:
        print(f'{datetime.now()} {Fore.RED}EXCEPTION{Style.RESET_ALL} while getting playlists for channel '
              f'"{channel_id}": {e}')
        return None


def get_all_playlist_videos_from_youtube(playlist):
    get_new_playlist_videos_from_youtube(playlist=playlist,
                                         ignore_errors=DEFAULT_ignore_errors_channel,
                                         archive_set=set(),
                                         counter=0)


def add_playlist_videos(videos):
    pass


def add_channel_videos(videos):
    pass


def update_subscriptions():
    # Skips ALL processing of known videos to speed up skript
    create_download_archive()

    global vpn_timestamp
    global vpn_counter
    all_channels = get_monitored_channels_from_db()
    for current_channel in all_channels:
        # TESTING: random new order of countries each channel
        random.shuffle(vpn_countries)

        current_channel_site = current_channel[0]
        current_channel_id = current_channel[1]
        current_channel_name = current_channel[2]
        videos_added_channel = 0

        # Retry getting missing videos for channel from YouTube
        counter_process_channel = 0
        ignore_errors_channel = DEFAULT_ignore_errors_channel
        skip_channel = False
        missing_videos_channel = None
        while missing_videos_channel is None and not skip_channel:
            channel_available = check_channel_availability(channel=current_channel)
            if channel_available:
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

        if not missing_videos_channel:
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
                    current_playlist_checked_successfully = True

                    # If any playlist was not reachable (e.g. given up upon, once we can trust yt-dlp settings fully) do NOT process "Other" playlist!
                    if current_channel_id == current_playlist_id:
                        if not all_playlists_checked_successfully:
                            current_playlist_checked_successfully = False
                            continue

                    current_playlist_download = current_playlist[7]
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

                    if not missing_videos_playlist:
                        print(
                            f'{datetime.now()} {Fore.RED}CRITICAL ERROR{Style.RESET_ALL} while processing playlist "'
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

                                    video_added = add_video(channel_site=current_playlist_site,
                                                            video=missing_video_playlist,
                                                            channel_id=current_channel_id,
                                                            playlist_id=current_playlist_id,
                                                            download=current_playlist_download,
                                                            archive_set=global_archive_set)

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
                            update_playlist(date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                            playlist=current_playlist)
                        else:
                            print(f'{datetime.now()} {Fore.RED}INCOMPLETE CHECK{Style.RESET_ALL} on playlist '
                                  f'"{current_playlist_name}" ({current_playlist_site} {current_playlist_id})')

            # Channel is updated after
            # A: All playlists have been checked to completion (<= all videos was found on playlists)
            # B: All new channel videos have been found on a playlist
            # C: The channel had no new videos
            if all_playlists_checked_successfully:
                update_channel(date=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                               channel=current_channel)
            else:
                print(f'{datetime.now()} {Fore.RED}INCOMPLETE CHECK{Style.RESET_ALL} on channel '
                      f'"current_channel_name" ({current_channel_site} {current_channel_id})')


def add_subscriptions():
    database_channels = get_monitored_channels_from_db()
    database_playlists = get_monitored_playlists_from_db()
    channel_list = []
    use_database = None

    while use_database == None:
        use_database_input = input(
            f'Check playlists for all existing channels? {Fore.GREEN}Y{Style.RESET_ALL} or {Fore.RED}N{Style.RESET_ALL}: ')
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
        print()

        channel = get_channel_details(channel_url=channel_url, ignore_errors=DEFAULT_ignore_errors_channel)
        channel_id = channel['id']
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
            print(f'{datetime.now()} {Fore.CYAN}ATTENTION{Style.RESET_ALL} All "Other" videos are already being downloaded!')

        online_playlists = None
        online_playlists = get_all_channel_playlists_from_youtube(channel=channel, ignore_errors=DEFAULT_ignore_errors_playlist)

        if online_playlists is not None:
            for online_playlist in online_playlists:
                print()

                playlist_id = online_playlist['id']
                playlist_name_online = online_playlist['title']

                if playlist_id in database_playlists:
                    playlist_name_sane = database_playlists[playlist_id]
                    print(f'{datetime.now()} Playlist known as "{playlist_name_sane}"')
                else:
                    playlist_name_sane = sanitize_name(name=playlist_name_online)
                    skip_playlist = False
                    while not skip_playlist:
                        add_playlist_input = input(
                            f'Download "{playlist_name_sane}" ({playlist_id}) {Fore.GREEN}Y{Style.RESET_ALL} (Yes), {Fore.RED}N{Style.RESET_ALL} (No) or {Fore.CYAN}S{Style.RESET_ALL} (Skip): ')
                        if add_playlist_input.lower() == 'y':
                            download_playlist = True
                        elif add_playlist_input.lower() == 'n':
                            download_playlist = False
                        elif add_playlist_input.lower() == 's':
                            break
                        else:
                            continue

                        playlist_name_input = input(f'ENTER to keep default or type to change PLAYLIST name: ')

                        if playlist_name_input:
                            playlist_name_sane = sanitize_name(name=playlist_name_input, is_user=True)

                        add_playlist(playlist_id=playlist_id, playlist_name=playlist_name_sane, channel_id=channel_id,
                                     download=download_playlist)
                        skip_playlist = True

        # Handle "Other" playlist (channel video feed)
        playlist_id = channel_id
        playlist_name_online = 'Other'
        print(
            f'{datetime.now()} {Fore.CYAN}ATTENTION{Style.RESET_ALL} "Other" Playlist should only be added for channels where most videos are not on playlists!')

        if playlist_id in database_playlists:
            playlist_name_sane = database_playlists[playlist_id]
            print(f'{datetime.now()} Playlist known as "{playlist_name_sane}"')
        else:
            playlist_name_sane = sanitize_name(name=playlist_name_online)
            skip_playlist = False
            while not skip_playlist:
                add_playlist_input = input(
                    f'Download "{playlist_name_sane}" ({playlist_id}) {Fore.GREEN}Y{Style.RESET_ALL} (Yes), {Fore.RED}N{Style.RESET_ALL} (No) or {Fore.CYAN}S{Style.RESET_ALL} (Skip): ')
                if add_playlist_input.lower() == 'y':
                    download_playlist = True
                elif add_playlist_input.lower() == 'n':
                    download_playlist = False
                elif add_playlist_input.lower() == 's':
                    break
                else:
                    continue

                playlist_name_input = input(f'ENTER to keep default or type to change PLAYLIST name: ')

                if playlist_name_input:
                    playlist_name_sane = sanitize_name(name=playlist_name_input, is_user=True)

                add_playlist(playlist_id=playlist_id, playlist_name=playlist_name_sane, channel_id=channel_id,
                             download=download_playlist)
                skip_playlist = True


if __name__ == "__main__":
    init(convert=True)
    just_fix_windows_console()

    while True:
        update_subscriptions()
