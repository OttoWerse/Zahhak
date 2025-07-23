from colorama import init, just_fix_windows_console, Fore, Style
import zahhak
from zahhak import check_channel_availability

# WIP Main
if __name__ == "__main__":
    init(convert=True)
    just_fix_windows_console()

    while True:
        playlists_monitored = zahhak.get_monitored_playlists_from_db()

        channels = zahhak.get_monitored_channels_from_db()
        for channel in channels:
            database = zahhak.connect_database()

            if check_channel_availability(channel):
                videos_channel_unmonitored = []
                videos_channel_all = zahhak.get_all_channel_videos_from_youtube(channel=channel)
                videos_channel_download = videos_channel_all

                playlists_channel_all = zahhak.get_all_channel_playlists_from_youtube(channel=channel, ignore_errors=False)
                for playlist in playlists_channel_all:

                    videos_playlist_download = []
                    videos_playlist_all = zahhak.get_all_playlist_videos_from_youtube(playlist=playlist)
                    for video in videos_playlist_all:
                        if playlist not in playlists_monitored:
                            videos_channel_download.remove(video)
                            videos_channel_unmonitored.append(video)
                        else:
                            videos_playlist_download.append(video)
                            videos_channel_download.remove(video)
                            if video in videos_channel_unmonitored:
                                videos_channel_unmonitored.remove(video)

                    zahhak.add_playlist_videos(videos_playlist_download, playlist_id)
                    zahhak.update_playlist(playlist)

            zahhak.add_channel_videos(videos_channel_download)
            zahhak.update_channel(channel)