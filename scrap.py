import threading
import urllib2
import json

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
    
    def run(self):
        logger.debug("-> Scrapping " + self.name);
        while not self._stopevent.isSet():
            logger.debug("Loop..." + self.name)
            
            data = self.download()
            infos = self.extract(data)
            infos = self.postprocess(infos)

            if any(infos.get(k) != self.infos.get(k) for k in infos):
                self.infos = infos
                self.plugin.update_track('updated', self.track, self.infos)

            self._stopevent.wait(10)

        self.plugin.update_track('stopped', self.track, self.default_infos())
        logger.debug("-> Done with " + self.name);

    def stop(self):
        self._stopevent.set()

    @classmethod
    def match(cls, fileuri):
        return False

    def default_infos(self):
        return {
            'artist' : self.name,
            'title'  : self.name,
            'album'  : self.name,
            'date'   : ""
            }

    def download(self):
        try:
            data = urllib2.urlopen(self.uri)
            return data.read()
        except:
            return None

    def extract(self, data):
        raise NotImplementedError("Please implement that in the scrapper")

    def postprocess(self, infos):
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
    def __init__(self, *args, **kwargs):
        super(FIPScrapper, self).__init__(*args, **kwargs)
        self.name = "FIP Radio"
        self.uri = "http://www.fipradio.fr/sites/default/files/direct-large.json"

    @classmethod
    def match(cls, fileuri):
        if not BeautifulSoup:
            raise NotImplementedError('BeautifulSoup is not available.')
            return False
        return fileuri.startswith("http://mp3.live.tv-radio.com/fip/all/")

    def extract(self, data):
        #logger.debug("data: " + data)

        infos = self.default_infos()

        html = json.loads(data).pop("html")
        if not html:
            return infos
        html.replace('\n', '')
        #logger.debug("html: " + html)

        soup = BeautifulSoup(html).find(attrs = { "class" : "direct-current" })
        if not soup:
            return infos
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

        tag_year = soup.find(attrs = { "class" : "annee" })
        if tag_year:
            infos['year'] = str(tag_year.string).strip().strip('()')
        
#        logger.debug("artist: " + infos['artist'] +
#                     ", title: " + infos['title'] +
#                     ", album: " + infos['album'] +
#                     ", date: " + infos['year'])

        return infos



class NovaScrapper(WebRadioScrapper):
    def __init__(self, *args, **kwargs):
        super(NovaScrapper, self).__init__(*args, **kwargs)
        self.name = "Radio Nova"
        self.uri = "http://www.novaplanet.com/radionova/ontheair"

    @classmethod
    def match(cls, fileuri):
        if not BeautifulSoup:
            raise NotImplementedError('BeautifulSoup is not available.')
            return False
        return fileuri.startswith("http://broadcast.infomaniak.net:80/radionova")

    def extract(self, data):
        infos = self.default_infos()
        
        html = json.loads(data).pop("track").pop("markup")
        if not html:
            return infos
        html.replace('\n', '')

        soup = BeautifulSoup(html)
        if not soup:
            return infos

        tag_artist = soup.find(attrs = { "class" : "artist" })
        if tag_artist:
            artist = tag_artist.string
            if not artist:
                artist = tag_artist.find('a').string
            infos['artist'] = str(artist).strip()

        tag_title = soup.find(attrs = { "class" : "title" })
        if tag_title:
            infos['title'] = str(tag_title.string).strip()

        return infos
