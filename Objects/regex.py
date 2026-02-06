import re
'''Error messages'''
# Channel
channel_no_media = re.compile(r'This channel does not have a videos tab')
channel_no_playlists = re.compile(r'This channel does not have a playlists tab')
channel_unavailable = re.compile(r'This channel is not available')
channel_removed = re.compile(r'This channel was removed because it violated our Community Guidelines')
channel_deleted = re.compile(r'This channel does not exist')
# Playlist
playlist_deleted = re.compile(r'The playlist does not exist')
# Media
media_format_unavailable = re.compile(r'Requested format is not available')
media_private = re.compile(r'Private video')
media_removed = re.compile(r'This video has been removed')
media_unavailable = re.compile(r'Video unavailable')
media_unavailable_live = re.compile(r'This live stream recording is not available')
media_unavailable_geo = re.compile(r'The uploader has not made this video available in your country')
media_unavailable_geo_fix = re.compile(r'(?<=This video is available in ).*(?<!\.)')
media_age_restricted = re.compile(r'Sign in to confirm your age')
media_members_only = re.compile(r'Join this channel to get access to members-only content like this video')
media_members_tier = re.compile(r'This video is available to this channel.s members on level')
media_paid = re.compile(r'This video requires payment to watch')
media_live_not_started = re.compile(r'This live event will begin in a few moments')
# Networking
bot = re.compile(r"Sign in to confirm you.re not a bot")
offline = re.compile(r"Offline")
error_timeout = re.compile(r'The read operation timed out')
error_get_addr_info = re.compile(r'getaddrinfo failed')
error_connection = re.compile(r'Remote end closed connection without response')
error_http_403 = re.compile(r'HTTP Error 403')
error_http_429 = re.compile(r'HTTP Error 429')
# Storage
json_write = re.compile(r'Cannot write video metadata to JSON file')
error_win_2 = re.compile(r'WinError 2')
error_win_5 = re.compile(r'WinError 5')
error_win_32 = re.compile(r'WinError 32')
error_win_10054 = re.compile(r'WinError 10054')
# MySQL
sql_duplicate = re.compile(r'Duplicate entry')
sql_unavailable = re.compile(r'MySQL Connection not available')
'''Other'''
# Channel names
live_channel = re.compile(r'.* LIVE$')
fake_channel = re.compile(r'^#.*$')
fake_playlist = re.compile(r'^#.*$')
handle_as_id = re.compile(r'^@.*$')
# noinspection RegExpRedundantEscape
val = re.compile(r'[^\.a-zA-Z0-9 -]')
caps = re.compile(r'[A-Z][A-Z]+')
# File extensions
mp4 = re.compile(r'\.mp4$')
json = re.compile(r'\.info\.json$')
nfo = re.compile(r'\.nfo$')
show_nfo = re.compile(r'^tvshow\.nfo$')
season_nfo = re.compile(r'^season\.nfo$')
# NFO components
# noinspection RegExpRedundantEscape
date_present = re.compile(r'<aired>\d{4}-\d{2}-\d{2}<\/aired>')
# noinspection RegExpRedundantEscape
date_value = re.compile(r'(?<=<aired>)(.*)(?=<\/aired>)')
# noinspection RegExpRedundantEscape
date_add_position = re.compile(r'(?<=<\/season>).*')
# noinspection RegExpRedundantEscape
network_present = re.compile(r'<studio>.*<\/studio>')
# noinspection RegExpRedundantEscape
network_value = re.compile(r'(?<=<studio>)(.*)(?=<\/studio>)')
# noinspection RegExpRedundantEscape
network_add_position = re.compile(r'(?<=<\/runtime>).*')