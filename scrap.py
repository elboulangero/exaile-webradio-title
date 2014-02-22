import sys
import threading

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



class WebRadioScrapper(threading.Thread):
    def __init__(self, plugin, track):
        threading.Thread.__init__(self)
        self._stopevent = threading.Event()
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

        logger.debug("-> Scrapping " + self.name);
        while not self._stopevent.isSet():
            # Init infos
            infos = self.default_infos()

            # Request data
#            logger.debug(self.name + ": request")
            data = self.request()
#            logger.debug(self.name + ": data: " + str(data))

            # Process data
            if data:
                self.req_failures = 0
                self.extract(infos, data)
                self.postprocess(infos)
            else:
                self.req_failures += 1
                if self.req_failures < 3:
                    # Request may fail from time to time, we can ignore
                    # it silently instead of resetting track infos.
                    infos = self.infos
            
#            logger.debug(self.name +
#                         ": artist: " + infos['artist'] +
#                         ", title: " + infos['title'] +
#                         ", album: " + infos['album'] +
#                         ", date: " + infos['date'])

            # Check if anything has changed
            if any(infos.get(k) != self.infos.get(k) for k in infos):
                self.infos = infos
                self.plugin.update_track('updated', self.track, self.infos)

            # Sleep until next request
            self._stopevent.wait(10)

        self.plugin.update_track('stopped', self.track, self.default_infos())
        logger.debug("-> Done with " + self.name);

    def stop(self):
        self._stopevent.set()

    @classmethod
    def match(cls, fileuri):
        return fileuri.startswith(cls.uri)

    def default_infos(self):
        return {
            'artist' : self.name,
            'title'  : self.name,
            'album'  : self.name,
            'date'   : ""
            }

    def request(self):
        try:
            response = requests.get(self.scrapuri, timeout=5)
#            logger.debug("resp header: " + str(sorted(response.headers.items())))
#            logger.debug("req header: " + str(sorted(response.request.headers.items())))
        except:
            logger.debug("Request error: " + str(sys.exc_info()[0]) + " on URI " + self.scrapuri)
            return None

        if self.datatype == "json":
            return response.json()
        else:
            return response.text

    def extract(self, data):
        raise NotImplementedError("Please implement that in the scrapper")

    def postprocess(self, infos):
        # TODO: is that code really doing something ?
        for k, v in infos.items():
            v = v or ''
            try:
                u = v.decode('iso-8859-1')
                v = u.encode('utf8')
                v = unicode(v)
            except UnicodeDecodeError:
                pass
            infos[k] = v.strip().title()
        return infos



class FIPScrapper(WebRadioScrapper):
    name = "FIP Radio"
    uri = "http://mp3.live.tv-radio.com/fip/all/"
    scrapuri = "http://www.fipradio.fr/sites/default/files/direct-large.json"
    datatype = "json"

    def __init__(self, *args, **kwargs):
        super(FIPScrapper, self).__init__(*args, **kwargs)

    def extract(self, infos, jsdata):
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
            infos['artist'] = str(tag_artist.string).strip()

        tag_title = soup.find(attrs = { "class" : "titre" })
        if tag_title:
            infos['title'] = str(tag_title.string).strip()

        tag_album = soup.find(attrs = { "class" : "album" })
        if tag_album:
            infos['album'] = str(tag_album.string).strip()

        tag_date = soup.find(attrs = { "class" : "annee" })
        if tag_date:
            infos['date'] = str(tag_date.string).strip().strip('()')
        


class NovaScrapper(WebRadioScrapper):
    name = "Radio Nova"
    uri = "http://broadcast.infomaniak.net:80/radionova"
    scrapuri = "http://www.novaplanet.com/radionova/ontheair"
    datatype = "json"

    def __init__(self, *args, **kwargs):
        super(NovaScrapper, self).__init__(*args, **kwargs)

    def extract(self, infos, jsdata):
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
            artist = tag_artist.string
            if not artist:
                artist = tag_artist.find('a').string
            infos['artist'] = str(artist).strip()

        tag_title = soup.find(attrs = { "class" : "title" })
        if tag_title:
            infos['title'] = str(tag_title.string).strip()

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
