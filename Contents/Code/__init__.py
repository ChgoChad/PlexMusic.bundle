#
# Copyright (c) 2014 Plex Development Team. All rights reserved.
#

from urllib import urlencode  # TODO: expose urlencode for dicts in the Framework?
from collections import Counter
from Utils import normalize_artist_name
from Artist import find_artist_posters, find_artist_art

DEBUG = True


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

    # Artist name.
    metadata.title = res.xpath('//Directory[@type="album"]')[0].get('parentTitle')

    # Artist bio.
    metadata.summary = res.xpath('//Directory[@type="album"]')[0].get('parentSummary')

    # Artist country.
    metadata.countries.clear()
    metadata.countries.add(res.xpath('//Directory[@type="album"]')[0].get('parentCountry'))

    # Primary artist poster.
    posters = []
    gracenote_poster = res.xpath('//Directory[@type="album"]')[0].get('parentThumb')
    if len(gracenote_poster) > 0:
      posters.append(gracenote_poster)

    # Find posters from fallback sources.
    if len(posters) == 0 or DEBUG:
      album_titles = [a.title for a in media.children]
      find_artist_posters(posters, metadata.title, album_titles, lang)

    # Placeholder image if we're in DEBUG mode.
    if len(posters) == 0 and DEBUG:
      posters.append('https://dl.dropboxusercontent.com/u/8555161/no_artist.png')

    # Add posters.
    valid_keys = []
    for poster in posters:
      try:
        metadata.posters[poster] = Proxy.Media(HTTP.Request(poster))
        valid_keys.append(poster)
      except Exception, e:
        Log('Couldn\'t add poster (%s): %s' % (poster, str(e)))
    
    metadata.posters.validate_keys(valid_keys)

    # Find and add artist art.
    arts = []
    valid_keys = []
    find_artist_art(arts, metadata.title, album_titles, lang)
    for art in arts:
      try:
        metadata.art[art[0]] = Proxy.Preview(HTTP.Request(art[1]))
        valid_keys.append(art[0])
      except Exception, e:
        Log('Couldn\'t add art (%s): %s' % (art[0], str(e)))

    metadata.art.validate_keys(valid_keys)

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
