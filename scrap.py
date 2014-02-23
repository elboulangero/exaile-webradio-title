import sys
import threading
from HTMLParser import HTMLParser # Python 3: HTMLParser becomes html.parser

try:
    import requests
except ImportError:
    requests = None

try:
    from BeautifulSoup import BeautifulSoup
except ImportError:
    BeautifulSoup = None

import logging
logger = logging.getLogger(__name__)



class ScrapperThread(threading.Thread):
    def __init__(self, scrappercls, plugin, track):
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()
        self.html_parser = HTMLParser()
        self.scrapper = scrappercls
        self.plugin = plugin
        self.track = track
        self.infos = {}
        self.req_failures = 100

    def run(self):
        if not requests:
            logger.error("Requests is not available")
            return
        if not BeautifulSoup:
            logger.error("BeautifulSoup is not available")
            return

        logger.debug("-> Scrapping " + self.scrapper.name);
        while not self._stopevent.isSet():
            # Init infos
            infos = self.scrapper.init_infos()

            # Request data
            data = self.request()

            # Extract infos
            if data:
                self.req_failures = 0
                self.scrapper.extract(infos, data)
            else:
                self.req_failures += 1
                if self.req_failures < 3:
                    # Request may fail from time to time, we can ignore
                    # it silently instead of resetting track infos.
                    infos = self.infos
            
            # Post-process infos
            self.postprocess(infos)

#            logger.debug("infos: " +
#                         "{ artist: " + infos['artist'] +
#                         ", title: " + infos['title'] +
#                         ", album: " + infos['album'] +
#                         ", date: " + infos['date'] })

            # Check if anything has changed
            if any(infos.get(k) != self.infos.get(k) for k in infos):
                self.infos = infos
                self.plugin.update_track('updated', self.track, self.infos)

            # Sleep until next request
            self._stopevent.wait(self.scrapper.period)

        self.plugin.update_track('stopped', self.track, self.scrapper.init_infos())
        logger.debug("-> Done with " + self.scrapper.name);

    def stop(self):
        self._stopevent.set()

    def request(self):
        uri = self.scrapper.scrapuri
        headers = self.scrapper.headers
        datatype = self.scrapper.datatype

#            logger.debug("Starting request")

        try:
            response = requests.get(uri, headers=headers, timeout=5)
#            logger.debug("resp data: " + str(response.text))
#            logger.debug("resp header: " + str(sorted(response.headers.items())))
#            logger.debug("req header: " + str(sorted(response.request.headers.items())))
#            logger.debug("apparent encoding: " + str(response.apparent_encoding))
#            logger.debug("encoding: " + str(response.encoding))
        except:
            logger.debug("Request error: " + str(sys.exc_info()[0]) + " on URI " + uri)
            return None

        if datatype == "json":
            return response.json()
        else:
            return response.text

    def postprocess(self, infos):
        for key, value in infos.items():
            # Escape HTML entities
            value = self.html_parser.unescape(value)
            infos[key] = value.strip()



class WebRadioScrapper(object):
    @classmethod
    def match(cls, fileuri):
        return fileuri.startswith(cls.uri)

    @classmethod
    def init_infos(cls):
        return {
            'artist' : cls.name,
            'title'  : cls.name,
            'album'  : cls.name,
            'date'   : ""
            }

    @classmethod
    def extract(cls, infos, data):
        raise NotImplementedError



class FIPScrapper(WebRadioScrapper):
    name = "FIP Radio"
    uri = "http://mp3.live.tv-radio.com/fip/all/"
    scrapuri = "http://www.fipradio.fr/sites/default/files/direct-large.json"
    headers = {'Host': 'www.fipradio.fr',
               'Referer': 'http://www.fipradio.fr/'}
    period = 45
    datatype = "json"

    @classmethod
    def extract(cls, infos, jsdata):
        # Get HTML stuff
        html = jsdata.pop("html")
        if not html:
            return

        html.replace('\n', '')
        #logger.debug("html: " + str(html))

        # Parse HTML stuff
        soup = BeautifulSoup(html).find(attrs = { "class" : "direct-current" })
        if not soup:
            return
        #logger.debug("soup: " + soup.prettify())

        tag_artist = soup.find(attrs = { "class" : "artiste" })
        if tag_artist:
            infos['artist'] = str(tag_artist.string)

        tag_title = soup.find(attrs = { "class" : "titre" })
        if tag_title:
            infos['title'] = str(tag_title.string)

        tag_album = soup.find(attrs = { "class" : "album" })
        if tag_album:
            infos['album'] = str(tag_album.string)

        tag_date = soup.find(attrs = { "class" : "annee" })
        if tag_date:
            infos['date'] = str(tag_date.string).strip().strip('()')
        


class NovaScrapper(WebRadioScrapper):
    name = "Radio Nova"
    uri = "http://broadcast.infomaniak.net:80/radionova"
    scrapuri = "http://www.novaplanet.com/radionova/ontheair"
    headers = {'Host': 'www.novaplanet.com',
               'Referer': 'http://www.novaplanet.com/radionova/player'}
    period = 30
    datatype = "json"

    @classmethod
    def extract(cls, infos, jsdata):
        # Dig for the HTML stuff
        track = jsdata.pop("track")
        if not track:
            return
        
        markup = track.pop("markup")
        if not markup:
            return

        markup.replace('\n', '')

        # Parse HTML
        soup = BeautifulSoup(markup)
        if not soup:
            return

        tag_artist = soup.find(attrs = { "class" : "artist" })
        if tag_artist:
            if not tag_artist.string:
                tag_artist = tag_artist.find('a')
            infos['artist'] = str(tag_artist.string)

        tag_title = soup.find(attrs = { "class" : "title" })
        if tag_title:
            infos['title'] = str(tag_title.string)

        # Get more info about the current show
        shows = jsdata.pop("shows")
        if not shows:
            return

        # Program title
        title = shows[0].pop("title")
        if title:
            infos['album'] += " - " + title

        # Program diffusion time
        diff_time = shows[0].pop("field_emission_diff_texte_value")
        if diff_time:
            infos['album'] += " (" + diff_time + ")"



class GrenouilleScrapper(WebRadioScrapper):
    name = "Radio Grenouille"
    uri = "http://live.radiogrenouille.com:80/live"
    scrapuri = "http://www.radiogrenouille.com/wp-content/themes/radiogrenouille-new/cestpasse.php"
    headers = {'Host': 'www.radiogrenouille.com',
               'Referer': 'http://www.radiogrenouille.com/'}
    period = 5
    datatype = "json"

    @classmethod
    def extract(cls, infos, jsdata):
        current = jsdata[0]
        if not current:
            return

        tag_artist = current.pop("artiste")
        if tag_artist:
            infos['artist'] = tag_artist

        tag_title = current.pop("titre")
        if tag_title:
            infos['title'] = tag_title

        tag_album = current.pop("album")
        if tag_album:
            infos['album'] = tag_album

        label = current.pop("label")
        if label:
            infos['album'] += " " + label
