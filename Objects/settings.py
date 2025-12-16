import os

'''Directory settings'''
directory_download_temp = os.getenv('ZAHHAK_DIR_DOWNLOAD_TEMP')
directory_download_home = os.getenv('ZAHHAK_DIR_DOWNLOAD_HOME')
directory_final = os.getenv('ZAHHAK_DIR_FINAL')  # TODO: How to handle multiple final directories?
'''MySQL settings'''
mysql_host = os.getenv('ZAHHAK_MYSQL_HOSTNAME', 'localhost')
mysql_database = os.getenv('ZAHHAK_MYSQL_DATABASE', 'zahhak')
mysql_user = os.getenv('ZAHHAK_MYSQL_USERNAME', 'admin')
mysql_password = os.getenv('ZAHHAK_MYSQL_PASSWORD', 'admin')
# Sleep time after failed MySQL requests (in seconds)
sleep_time_mysql = 3
'''VPN settings'''
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
# Timeout connecting VPN
timeout_vpn = 15
'''YT-DLP Settings'''
MEDIA_FORMAT = "bestvideo*[ext=mp4][height>=900][height<=1100][vcodec~='^(av01|vp9|h265|hevc)']+bestaudio[ext=m4a]"
# Frequency to reconnect VPN (in seconds)
sleep_time_vpn = 10
# How often to retry connecting to a VPN country before giving up
retry_reconnect_new_vpn_node = 5
# Frequency to check if switch from downloading secondary to primary media is needed (in seconds)
select_newest_media_frequency = 900
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