#
# Copyright (c) 2014 Plex Development Team. All rights reserved.
#

from urllib import urlencode, quote # TODO: expose urlencode for dicts in the Framework?
from collections import Counter
import unicodedata
import re

DEBUG = True

# Normalization regexes
RE_A_AN_THE = re.compile(r'^(an |a |the )|(, an |, a |, the)$')
RE_PARENS = re.compile(r'\([^\)]+\)$|\{[^\}]+\}$|\[[^\]]+ \]$')
RE_PUNCTUATION = re.compile(r'[!@#\$%\^\*\_\+=\{\}\[\]\|<>`\:\-\(\)\?/\\\&\~\,\'\']')
RE_MULTI_SPACE = re.compile(r'\s+')


def number_to_text(n):
  if n < 0:
    return 'minus ' + number_to_text(-n)
  elif n == 0:
    return ''
  elif n <= 19:
    return ('one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen')[n - 1] + ' '
  elif n <= 99:
    return ('twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety')[n / 10 - 2] + ' ' + number_to_text(n % 10)
  elif n <= 199:
    return 'one hundred ' + number_to_text(n % 100)
  elif n <= 999:
    return number_to_text(n / 100) + 'hundred ' + number_to_text(n % 100)
  elif n <= 1999:
    return 'one thousand ' + number_to_text(n % 1000)
  elif n <= 999999:
    return number_to_text(n / 1000) + 'thousand ' + number_to_text(n % 1000)
  elif n <= 1999999:
    return 'one million ' + number_to_text(n % 1000000)
  elif n <= 999999999:
    return number_to_text(n / 1000000) + 'million ' + number_to_text(n % 1000000)
  elif n <= 1999999999:
    return 'one billion ' + number_to_text(n % 1000000000)
  else:
    return number_to_text(n / 1000000000) + 'billion ' + number_to_text(n % 1000000000)


def normalize_artist_name(artist_name):
  if not isinstance(artist_name, basestring):
    return ''

  artist_name = artist_name.strip().lower().replace('&', 'and').strip()

  artist_name = RE_A_AN_THE.sub('', artist_name)

  tmp_artist_name = RE_PARENS.sub('', artist_name)

  artist_name = tmp_artist_name if len(tmp_artist_name.strip()) > 0 else artist_name

  tmp_artist_name = RE_PUNCTUATION.sub(' ', artist_name)

  artist_name = tmp_artist_name if len(tmp_artist_name.strip()) > 0 else artist_name

  artist_name = re.sub(r'\b\d+\b', lambda m: number_to_text(int(m.group())).replace('-', ' '), artist_name)
  
  try:
    normalized = unicodedata.normalize('NFKD', artist_name.decode('utf-8'))
  except UnicodeError:
    normalized = unicodedata.normalize('NFKD', artist_name)

  corrected = ''
  for i in range(len(normalized)):
    if not unicodedata.combining(normalized[i]):
      corrected += normalized[i]
  artist_name = corrected

  # artist_name = artist_name.encode('utf-8')

  artist_name = RE_MULTI_SPACE.sub(' ', artist_name).strip()

  artist_name = artist_name.replace(' ', '_')

  return artist_name


def Start():
  HTTP.CacheTime = 30


class GracenoteArtistAgent(Agent.Artist):

  name = 'Gracenote'
  languages = [Locale.Language.English,Locale.Language.NoLanguage]
  version = 2

  def search(self, results, tree, hints, lang, manual=False):

    if DEBUG:
      Log('tree -> albums: %s, all_parts: %d, children: %d, guid: %s, id: %s, index: %s, originally_available_at: %s, title: %s' % (tree.albums, len(tree.all_parts()), len(tree.children), tree.guid, tree.id, tree.index, tree.originally_available_at, tree.title))
      Log('hints -> album: %s, artist: %s, filename: %s, guid: %s, hash: %s, id: %s, index: %s, originally_available_at: %s, parent_metadata: %s, primary_agent: %s' % (hints.album, hints.artist, hints.filename, hints.guid, hints.hash, hints.id, hints.index, hints.originally_available_at, hints.parent_metadata, hints.primary_agent))

    if len(tree.albums) > 1:
      Log('Multi-album search request (%d albums) not yet implemented.' % len(tree.albums))
      return

    Log('Running single-item search with artist: %s, album: %s (%d tracks)' % (tree.title, tree.albums.values()[0].title, len(tree.all_parts())))

    args = {}
    for i, track in enumerate(tree.albums.values()[0].children):
      args['tracks[%d].path' % i]        = track.items[0].parts[0].file
      args['tracks[%d].userData' % i]    = track.id
      args['tracks[%d].track' % i]       = track.title
      if hasattr(track, 'originalTitle'):
        args['tracks[%d].artist' % i]    = track.originalTitle
      args['tracks[%d].albumArtist' % i] = tree.title
      args['tracks[%d].album' % i]       = tree.albums.values()[0].title
      args['tracks[%d].index' % i]       = track.index
      args['lang']                       = lang

    querystring = urlencode(args).replace('%5B','[').replace('%5D',']')
    url = 'http://127.0.0.1:32400/services/gracenote/search?fingerprint=1&' + querystring
    
    try:
      res = XML.ElementFromURL(url)
      # Log(XML.StringFromElement(res))
      first_track = res.xpath('//Track')[0]
    except Exception, e:
      Log('Exception running Gracenote search: ' + str(e))
      return

    # Go back and get the full album for more reliable metadata and so we can populate any missing tracks in the SearchResult.
    album_guid_consensus = Counter([t.get('parentGUID') for t in res.xpath('//Track')]).most_common()[0][0]
    Log('Got consensus on album GUID: ' + album_guid_consensus)
    album_res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(album_guid_consensus))
    album_elm = album_res.xpath('//Directory')[0]
    # Log(XML.StringFromElement(album_elm))

    # No album art from gracenote, clear out the thumb.
    thumb = album_elm.get('thumb')
    if thumb == 'http://': 
      thumb = ''

    album = SearchResult(id=tree.albums.values()[0].id, type='album', parentName=album_elm.get('parentTitle'), name=album_elm.get('title'), guid=album_guid_consensus, thumb=thumb, year=album_elm.get('year'), parentGUID=album_elm.get('parentGUID'), parentID=tree.id, score=100)

    matched_guids = [t.get('guid') for t in res.xpath('//Track')]
    for track in sorted(album_res.xpath('//Track'), key=lambda i: int(i.get('index'))):
      matched = '1' if track.get('guid') in matched_guids else '0'
      album.add(SearchResult(matched=matched, type='track', name=track.get('title'), id=track.get('userData'), guid=track.get('guid'), index=track.get('index')))

    results.add(album)

  def update(self, metadata, media, lang, child_guid=None):

    Log('Updating: %s (GUID: %s)' % (media.title, media.guid))
    Log('Child GUID: %s' % child_guid)

    # Find child albums and check that we have at least one Gracenote guid to work with.
    child_guids = [c.guid for c in media.children if c.guid.startswith('com.plexapp.agents.gracenote://')]
    if not child_guids:
      Log('Couldn\'t find an album by this artist with a Gracenote guid, aborting.')
      return

    # Artist data. Fetch an album (use the given child_guid if we have it) and use the artist data from that.
    res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(child_guid or child_guids[0]))

    if DEBUG:
      Log('Raw update result:')
      Log(XML.StringFromElement(res))

    metadata.title = res.xpath('//Directory[@type="album"]')[0].get('parentTitle')
    metadata.summary = res.xpath('//Directory[@type="album"]')[0].get('parentSummary')
    metadata.countries.clear()
    metadata.countries.add(res.xpath('//Directory[@type="album"]')[0].get('parentCountry'))

    # Artist art.
    valid_keys = []
    artist_poster_url = res.xpath('//Directory[@type="album"]')[0].get('parentThumb')
    try:
      if len(artist_poster_url) > 0:
        metadata.posters[artist_poster_url] = Proxy.Media(HTTP.Request(artist_poster_url))
        valid_keys.append(artist_poster_url)
    except Exception, e:
      Log('Couldn\'t fetch artist poster: %s' % artist_poster_url)

    # Artist image fallback.
    if len(valid_keys) == 0:
      Log('Falling back to artist artwork cache for artist: %s' % metadata.title)
      try:
        images = XML.ElementFromURL('http://meta.plex.tv/a/' + quote(normalize_artist_name(metadata.title))).xpath('//image')
        image_urls = [image.get('url') for image in images if image.get('primary') == '1']
        image_urls.extend([image.get('url') for image in images if image.get('primary') == '0'])
        for image_url in image_urls:
          metadata.posters[image_url] = Proxy.Media(HTTP.Request(image_url))
          valid_keys.append(image_url)
      except Exception, e:
        Log('Problem adding artwork from fallback cache: %s' % str(e))

    if len(valid_keys) == 0 and DEBUG:
      dummy_poster_url = 'https://dl.dropboxusercontent.com/u/8555161/no_artist.png'
      metadata.posters[dummy_poster_url] = Proxy.Media(HTTP.Request(dummy_poster_url))
      valid_keys.append(dummy_poster_url)

    metadata.posters.validate_keys(valid_keys)

    # Album data.
    for album in media.children:

      Log('Updating album: ' + album.title)
      Log('With guid: ' + album.guid)

      try:
        res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(album.guid))
      except Exception, e:
        Log('Error issuing album update request: ' + str(e))
        continue
      
      if DEBUG:
        Log('Got album metadata:\n' + XML.StringFromElement(res))

      a = metadata.albums[album.guid]
      a.title = res.xpath('//Directory[@type="album"]')[0].get('title')
      a.summary = res.xpath('//Directory[@type="album"]')[0].get('summary')
      a.studio = res.xpath('//Directory[@type="album"]')[0].get('studio')
      a.originally_available_at = Datetime.ParseDate(res.xpath('//Directory[@type="album"]')[0].get('year'))
      try:
        a.posters[0] = Proxy.Media(HTTP.Request(res.xpath('//Directory[@type="album"]')[0].get('thumb')))
      except Exception, e:
        if DEBUG:
          a.posters[0] = Proxy.Media(HTTP.Request('https://dl.dropboxusercontent.com/u/8555161/no_album.png'))
        Log('Couldn\'t add album art: ' + str(e))
      
      # Genres.
      a.genres.clear()
      for genre in res.xpath('//Directory[@type="album"]/Genre/@tag'):
        a.genres.add(genre)

      # Add the tracks.
      for track in res.xpath('//Track'):
        
        i = track.get('index')
        t = a.tracks[i]
        
        t.name = track.get('title')
        t.tempo = int(track.get('bpm') or -1)

        # Moods.
        t.moods.clear()
        for mood in track.xpath('./Mood/@tag'):
          t.moods.add(mood)
