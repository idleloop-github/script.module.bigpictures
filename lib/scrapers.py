#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#     Copyright (C) 2012 Tristan Fischer (sphere@dersphere.de)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program. If not, see <http://www.gnu.org/licenses/>.
#

import re
import json
import urllib2
import time
from random import randint
from BeautifulSoup import BeautifulSoup
from CommonFunctions import parseDOM, stripTags
import HTMLParser

try:
    import xbmc
    XBMC_MODE = True
except ImportError:
    XBMC_MODE = False

RETRY_TIME = 5.0

ALL_SCRAPERS = (
    'TheBigPictures',
    'AtlanticInFocus',
    'TotallyCoolPix',
    'NewYorkTimesLens',
    'Reddit',
)


class BasePlugin(object):

    _title = ''
    _id = 0

    def __init__(self, _id):
        self._albums = []
        self._photos = {}
        self._id = _id
        self._parser = HTMLParser.HTMLParser()

    def get_albums(self):
        return self._albums or self._get_albums()

    def get_photos(self, album_url):
        return self._photos.get(album_url) or self._get_photos(album_url)

    def _get_albums(self):
        raise NotImplementedError

    def _get_photos(self, album_url):
        raise NotImplementedError

    def _get_tree(self, url, language='html'):
        html = self._get_html(url)
        try:
            tree = BeautifulSoup(html, convertEntities=language)
        except TypeError:
            # Temporary fix for wrong encoded utf-8 chars in NewYork
            # Times Lens Blog. Shame on you.
            html = html.decode('utf-8', 'ignore')
            tree = BeautifulSoup(html, convertEntities=language)
        return tree

    def _get_html(self, url, retries=5):
        self.log('_get_html opening url "%s"' % url)
        req = urllib2.Request(url)
        html = ''
        retry_counter=0
        while True:
            try:
                html = urllib2.urlopen(req).read()
                self.log('get_tree received %d bytes' % len(html))
                break
            except urllib2.HTTPError as ex:
                self.log('_get_html error: %s' % ex)
                if (re.match(r'.+HTTP Error 301.+', str(ex))):
                    raise
                retry_counter += retry_counter
                time.sleep(RETRY_TIME + randint(0, 2*retries))
                pass
            if retry_counter >= retries:
                break
        return html

    def _collapse(self, iterable):
        return u''.join([e.string.strip() for e in iterable if e.string])

    @property
    def title(self):
        return self._title

    def log(self, msg):
        if XBMC_MODE:
            try:
                xbmc.log('TheBigPictures ScraperPlugin[%s]: %s' % (
                    self.__class__.__name__, msg
                ))
            except UnicodeEncodeError:
                xbmc.log('TheBigPictures ScraperPlugin[%s]: %s' % (
                    self.__class__.__name__, msg.encode('utf-8', 'ignore')
                ))
        else:
            try:
                print('TheBigPictures ScraperPlugin[%s]: %s' % (
                    self.__class__.__name__, msg
                ))
            except UnicodeEncodeError:
                print('TheBigPictures ScraperPlugin[%s]: %s' % (
                    self.__class__.__name__, msg.encode('utf-8', 'ignore')
                ))

    @classmethod
    def get_scrapers(cls, name_list):
        enabled_scrapers = []
        for sub_class in cls.__subclasses__():
            if sub_class.__name__ in name_list:
                enabled_scrapers.append(sub_class)
        return enabled_scrapers


class TheBigPictures(BasePlugin):

    _title = 'The Boston Globe: The Big Picture'

    def _get_albums(self):
        self._albums = []
        url = 'https://www.bostonglobe.com/news/bigpicture'
        html = self._get_html(url)
        for _id, album in enumerate(parseDOM(html, 'section')):
            title = parseDOM(album, 'a')[0]
            album_url = 'https://www.bostonglobe.com' + parseDOM(album, 'a', ret='href')[0]
            d = parseDOM(album, 'div', attrs={'class': 'subhead geor'})[0]
            if not d:
                continue
            description = stripTags(self._parser.unescape(d))
            pic = urllib2.quote(parseDOM(album, 'img', ret='src')[0])
            if not pic:
                continue
            self._albums.append({
                'title': title,
               'album_id': _id,
               'pic': 'http:' + pic,
               'description': description,
               'album_url': album_url
               })

        return self._albums

    def _get_photos(self, album_url):
        self._photos[album_url] = []
        html = self._get_html(album_url)
        album_title = parseDOM(html, 'title')[0]
        images = parseDOM(html, 'div', attrs={'class': 'photo'})
        descs = parseDOM(html, 'article', attrs={'class': 'pcaption'})
        for _id, photo in enumerate(images):
            pic = urllib2.quote(parseDOM(photo, 'img', ret='src')[0])
            description = stripTags(self._parser.unescape(parseDOM(descs[_id], 'div', attrs={'class': 'gcaption geor'})[0]))
            self._photos[album_url].append({
                'title': '%d - %s' % (_id + 1, album_title),
               'album_title': album_title,
               'photo_id': _id,
               'pic': 'http:' + pic,
               'description': description,
               'album_url': album_url
               })

        return self._photos[album_url]

class AtlanticInFocus(BasePlugin):

    _title = 'The Atlantic: In Focus'

    def _get_albums(self):
        self._albums = []
        url = 'https://www.theatlantic.com/infocus/'
        html = self._get_html(url)
        pattern = r'@media\(min-width:\s*1632px\)\s*{\s*#river1 \.lead-image\s*{\s*background-image:\s*url\((.+?)\)'
        for _id, li in enumerate(parseDOM(html, 'li', attrs={'class': 'article'})):
            headline = parseDOM(li, 'h1')[0]
            match = re.search(pattern.replace('river1', 'river%d' % (_id + 1)), html)
            if match:
                self._albums.append({
                   'title': parseDOM(headline, 'a')[0],
                   'album_id': _id,
                   'pic': match.group(1),
                   'description': stripTags(self._parser.unescape(parseDOM(li, 'p', attrs={'class': 'dek'})[0])),
                   'album_url': 'https://www.theatlantic.com' + parseDOM(headline, 'a', ret='href')[0]
                   })

        return self._albums

    def _get_photos(self, album_url):
        self._photos[album_url] = []
        html = self._get_html(album_url)
        pattern = r'data-share-image=\"(.+?)\"'
        match_image = re.findall(pattern, html)
        album_title = self._parser.unescape(parseDOM(html, 'title')[0])
        for _id, p in enumerate(parseDOM(html, 'p', attrs={'class': 'caption'})):
            match_description = re.search('<span>(.+?)</span>', p)
            if match_description:
                self._photos[album_url].append({'title': '%d - %s' % (_id + 1, album_title),
                   'album_title': album_title,
                   'photo_id': _id,
                   'pic': match_image[_id * 2],
                   'description': stripTags(self._parser.unescape(match_description.group(1))),
                   'album_url': album_url
                   })

        return self._photos[album_url]


class TotallyCoolPix(BasePlugin):

    _title = 'TotallyCoolPix.com'

    def _get_albums(self):
        self._albums = []
        url = 'https://totallycoolpix.com'
        tree = self._get_tree(url)
        albums = tree.findAll('div', {'class': 'item'})
        for id, album in enumerate(albums):
            if not album.find('a', {'class': 'open'}):
                continue
            title = album.find('h2').string
            album_url = album.find('a')['href']
            p = album.find('p')
            description = self._collapse(p.contents) if p else ''
            pic = album.find('img')['src']
            self._albums.append({
                'title': title,
                'album_id': id,
                'pic': pic,
                'description': description,
                'album_url': album_url}
            )
        return self._albums

    def _get_photos(self, album_url):
        self._photos[album_url] = []
        tree = self._get_tree(album_url)
        for id, photo in enumerate(tree.findAll('div', {'class': 'image'})):
            img = photo.find('img')
            if not img:
                continue
            if id == 0:
                album_title = photo.find('h2').string
                # jump first entry as it is a repetition of the album description
                continue
                description = stripTags(self._parser.unescape(str(tree.find('p', {'class': 'desc'}))))
            else:
                try:
                    description = self._parser.unescape(photo.find('p', {'class': 'info-txt'}).string)
                except:
                    description = ''

            self._photos[album_url].append({
                'title': '%d - %s' % (id + 1, album_title),
                'album_title': album_title,
                'photo_id': id,
                'pic': img['src'],
                'description': description,
                'album_url': album_url
            })
        if (id==1):
            # possibly a video:
            video = tree.find('iframe')['src']
            xbmc.log('possible video = ' + video)
            if re.match(r'.+youtube.com/.+', video):
                video_id = re.sub('.+/', '', video)
                xbmc.log('youtube video = ' + video_id)
                xbmc.executebuiltin('PlayMedia(plugin://plugin.video.youtube/play/?video_id=' + video_id + ')')
            elif re.match(r'.+vimeo.com/.+', video):
                video_id = re.sub('.+/', '', video)
                xbmc.log('vimeo video = ' + video_id)
                xbmc.executebuiltin('PlayMedia(plugin://plugin.video.vimeo/play/?video_id=' + video_id + ')')
            # if no match: previous processing have retrieved images
        return self._photos[album_url]


class NewYorkTimesLens(BasePlugin):

    _title = "NewYorkTimes.com: Lens Blog"

    def _get_albums(self):
        self._albums = []
        url = 'https://lens.blogs.nytimes.com/'
        tree = self._get_tree(url)
        description = tree.findAll('span', {'class': 'excerpt-inner'})
        previous_description = ''
        for id, album in enumerate(tree.findAll('div', {'class': 'image'})):
            if id >= len(description):
                previous_description = album.h4.string
            else:
                # first description is 3x repeated
                while previous_description == description[id].string:
                    del description[id]
                previous_description = description[id].string
            self._albums.append({
               'title': album.h4.string,
               'album_id': id,
               'pic': album.img['src'],
               'description': self._parser.unescape(description[id].string) if id < len(description) else album.h4.string,
               'album_url': album.a['href']
               })

        return self._albums

    def _get_photos(self, album_url):
        self._photos[album_url] = []
        tree = self._get_tree(album_url)
        tree = json.loads(tree.find('script', {'id': 'slideshow-json'}).string)
        for id, slide in enumerate(tree['imageslideshow']['slides']):
            self._photos[album_url].append({
               'title': self._parser.unescape(tree['summary']),
               'album_title': self._parser.unescape(tree['headline']),
               'photo_id': id,
               'pic': slide['image_crops']['superJumbo']['url'],
               'description': stripTags(self._parser.unescape(slide['caption']['full'])),
               'album_url': album_url
               })

        return self._photos[album_url]


class Reddit(BasePlugin):

    _title = 'Reddit'
    URL_PREFIX='http:'

    def _get_albums(self):
        self._albums = []
        #url = self.URL_PREFIX + '//www.reddit.com/r/EarthPorn'
        #tree = self._get_tree(url)
        #pic = tree.find('img')['src'] #not sure what this is used for, grab a random picture
        #if re.match('^//', pic):
        #    pic=self.URL_PREFIX + pic
        # reduce as much as possible unnecessary connections to reddit.com to avoid error HTTP 429:
        pic='https://www.redditstatic.com/icon.png'
        self._albums.append({
            'title': 'EarthPorn',
            'album_id': 1,
            'pic': pic,
            'description': 'Pictures of the earth',
            'album_url': self.URL_PREFIX + '//www.reddit.com/r/EarthPorn'}
        )
        self._albums.append({
            'title': 'SpacePorn',
            'album_id': 2,
            'pic': pic,
            'description': 'High Res Images of Space',
            'album_url': self.URL_PREFIX + '//www.reddit.com/r/SpacePorn'}
        )
        self._albums.append({
            'title': 'SeaPorn',
            'album_id': 3,
            'pic': pic,
            'description': 'Pictures of the sea',
            'album_url': self.URL_PREFIX + '//www.reddit.com/r/SeaPorn'}
        )
        self._albums.append({
            'title': 'BeachPorn',
            'album_id': 4,
            'pic': pic,
            'description': 'High-res images of Beaches from around the globe.',
            'album_url': self.URL_PREFIX + '//www.reddit.com/r/BeachPorn'}
        )
        self._albums.append({
            'title': 'AerialPorn',
            'album_id': 5,
            'pic': pic,
            'description': 'Pictures of the ground',
            'album_url': self.URL_PREFIX + '//www.reddit.com/r/AerialPorn'}
        )
        self._albums.append({
            'title': 'ExposurePorn',
            'album_id': 6,
            'pic': pic,
            'description': 'Long exposure photography',
            'album_url': self.URL_PREFIX + '//www.reddit.com/r/ExposurePorn'}
        )
        self._albums.append({
            'title': 'ViewPorn',
            'album_id': 7,
            'pic': pic,
            'description': 'Rooms with a view',
            'album_url': self.URL_PREFIX + '//www.reddit.com/r/ViewPorn'}
        )
        self._albums.append({
            'title': 'AdrenalinePorn',
            'album_id': 8,
            'pic': pic,
            'description': 'Eye candy for extreme athletes and adrenaline junkies!',
            'album_url': self.URL_PREFIX + '//www.reddit.com/r/AdrenalinePorn'}
        )
        self._albums.append({
            'title': 'SummerPorn',
            'album_id': 9,
            'pic': pic,
            'description': 'Soaking in the sun',
            'album_url': self.URL_PREFIX + '//www.reddit.com/r/SummerPorn'}
        )
        self._albums.append({
            'title': 'CityPorn',
            'album_id': 10,
            'pic': pic,
            'description': 'Beautifuly cityscapes',
            'album_url': self.URL_PREFIX + '//www.reddit.com/r/CityPorn'}
        )
        self._albums.append({
            'title': 'WaterPorn',
            'album_id': 11,
            'pic': pic,
            'description': 'Waterscapes and aquatics',
            'album_url': self.URL_PREFIX + '//www.reddit.com/r/WaterPorn'}
        )
        return self._albums

    def _get_photos(self, album_url):
        self._photos[album_url] = []
        tree = self._get_tree(album_url, language='html')
        album_title = tree.find('title').string
        match_size = re.compile(r'.+(([\d,]{4,})(\s?[x×]\s?)([\d,]{4,})).*', re.IGNORECASE) # grab all that are bigger than 1000x1000
        match_format = re.compile(r'\shref=\"(.+?\.jpe?g)\"', re.IGNORECASE) # picture format pattern
        self.log('album_title =' + album_title)
        for id, photo in enumerate(tree.findAll('div', {'class': re.compile(r'^ thing id-.+')})):

            try:
                description = self._collapse(photo.find('a', {'class': re.compile(r'title may-blank .*')}).contents)
            except:
                continue

            #match_resolution = match_size.match(description)
            #if not match_resolution: # skip pictures with low resolutions
            #    self.log('resolution too low: %s' % description)
            #    continue
            ##elif match_resolution.group(2) < match_resolution.group(4): # skip pictures with portrait aspect ratio
            ##    self.log('wrong aspect ratio or no picture title: %s' % description)
            ##    continue

            img = photo.find('div', {'class': 'expando expando-uninitialized'})
            if not img or not match_format.search(str(img)): # extract image href from pseudo-html
                self.log('no image or not a jpg')
                continue
            else:
                pic = match_format.search(str(img)).group(1)
            self.log('pic= %s' % pic)

            try:
                author = photo.find('a', {'class': re.compile(r'author may-blank.*')})
                if author:
                    author = author.contents[0]

                pic_time = photo.find('time')['title']

            except:
                author=''
                pic_time=''

            if author:
                description+="\n\n(Author: " + author + ")"
            if pic_time:
                description+="\n(@ " + pic_time + ")"

            self._photos[album_url].append({
                'title': '%d - %s' % (id + 1, album_title),
                'album_title': album_title,
                'photo_id': id,
                'author': author,
                'pic': pic,
                'description': description,
                'album_url': album_url,
            })

        return self._photos[album_url]


def get_scrapers(enabled_scrapers=None):
    if enabled_scrapers is None:
        enabled_scrapers = ALL_SCRAPERS
    scrapers = [
        scraper(i) for i, scraper
        in enumerate(BasePlugin.get_scrapers(enabled_scrapers))
    ]
    return scrapers
