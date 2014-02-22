import time
import random

from xl import player, event

from scrap import FIPScrapper, NovaScrapper

import logging
logger = logging.getLogger(__name__)

PERIOD = 10  # seconds

_PLUGIN = None



PLAYBACK_START_CALLBACKS = (
        'playback_player_start',
        'playback_player_resume',
        )

PLAYBACK_STOP_CALLBACKS = (
        'playback_player_end',
        'playback_player_pause',
        )

def enable(exaile):
    if exaile.loading:
        event.add_callback(_enable, 'exaile_loaded')
    else:
        _enable(None, exaile, None)

def _enable(eventname, exaile, nothing):
    global _PLUGIN

    _PLUGIN = WebRadioTitlePlugin(exaile)

    for signal in PLAYBACK_START_CALLBACKS:
        event.add_callback(_PLUGIN.on_playback_start, signal)
    for signal in PLAYBACK_STOP_CALLBACKS:
        event.add_callback(_PLUGIN.on_playback_stop, signal)

def disable(exaile):
    global _PLUGIN

    for signal in PLAYBACK_START_CALLBACKS:
        event.remove_callback(_PLUGIN.on_playback_start, signal)
    for signal in PLAYBACK_STOP_CALLBACKS:
        event.remove_callback(_PLUGIN.on_playback_stop, signal)

    _PLUGIN.stop()
 


class WebRadioTitlePlugin(object):
 
    def __init__(self, exaile):
        logger.debug("")
        self.scrapper = None

    def __del__(self):
        logger.debug("")
        self.stop()

    def on_playback_start(self, type, object, data):
        logger.debug("Type: " + type)

        # Stop
        self.stop()

        # Get track
        track = player.PLAYER.current
        if not track:
            logger.debug("No track")
            return

        # Check if track is a webradio
        if not track.get_type() == "http":
            logger.debug("Track type is not http")
            return

        # Get URL
        url = track.get_loc_for_io()
        
        # Look for a web scrapper that knows this url
        for cls in [FIPScrapper, NovaScrapper]:
            if cls.match(url):
                self.start(cls, track)
                return
        logger.debug("Current track does not match any webradio scrapper")

    def on_playback_stop(self, type, object, data):
        logger.debug("Type: " + type)

        self.stop()

    def start(self, scrappercls, track):
        logger.debug("Start fetching titles")

        self.scrapper = scrappercls(self, track)
        self.scrapper.start()

    def stop(self):
        logger.debug("Stop fetching titles")

        if self.scrapper:
            self.scrapper.stop()
            self.scrapper = None

    def update_track(self, cause, track, infos):
        logger.debug("cause: " + cause + ", track: " + str(track) + ", infos: " + str(infos))

        # Ensure a track is defined
        if not track:
            logger.debug("No track")
            return

        # Set tags in track
        for tag in ['artist', 'title', 'album', 'date']:
            value = infos.get(tag)
            if value is not None:
                track.set_tag_raw(tag, value)
        track.set_tag_raw('__length', random.randint(180, 240))  # fake length

        # Trigger a notification
        if cause == 'updated':
            logger.debug("Simulate track change")
            event.log_event('playback_track_start', player.PLAYER, track)
