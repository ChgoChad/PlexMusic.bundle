#
# Copyright (c) 2014 Plex Development Team. All rights reserved.
#

from urllib import urlencode # TODO: expose urlencode for dicts in the Framework?


DEBUG = True


def Start():
  HTTP.CacheTime = 30


class GracenoteArtistAgent(Agent.Artist):

  name = 'Gracenote'
  languages = [Locale.Language.English,Locale.Language.NoLanguage]
  version = 2

  def search(self, results, tree, hints, lang, manual=False):

#    return

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
      Log(XML.StringFromElement(res))
      first_track = res.xpath('//Track')[0]
    except Exception, e:
      Log('Exception running Gracenote search: ' + str(e))
      return

    album = SearchResult(id=tree.albums.values()[0].id, type='album', parentName=first_track.get('grandparentTitle'), name=first_track.get('parentTitle'), guid=first_track.get('parentGUID'), thumb=first_track.get('parentThumb'), year=first_track.get('year'), parentGUID=first_track.get('grandparentGUID'), parentID=tree.id, score=100)

    for track in sorted(res.xpath('//Track'), key=lambda i: int(i.get('index'))):
      album.add(SearchResult(matched='1', type='track', name=track.get('title'), id=track.get('userData'), guid=track.get('guid'), index=track.get('index')))

    results.add(album)

  def update(self, metadata, media, lang, child_guid=None):

    Log('Updating: %s (GUID: %s)' % (media.title, media.guid))
    Log('Child GUID: %s' % child_guid)

    return

    # Artist data.  Fetch an album (use the child_guid if we have it) and use the artist data from that.
    res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(child_guid or media.children[0].guid))
    metadata.title = res.xpath('//Directory[@type="album"]')[0].get('parentTitle')
    metadata.summary = res.xpath('//Directory[@type="album"]')[0].get('parentSummary')
    try:
      metadata.posters[0] = Proxy.Media(HTTP.Request(res.xpath('//Directory[@type="album"]')[0].get('parentThumb')))
    except Exception, e:
      if DEBUG:
        metadata.posters[0] = Proxy.Media(HTTP.Request('https://dl.dropboxusercontent.com/u/8555161/no_artist.png'))
      Log('Couldn\'t add artist art: ' + str(e))

    # Album data.
    for album in media.children:

      Log('Updating album: ' + album.title)

      # If we already asked for this album's data above, no need to do so again.
      if album.guid != child_guid and album.guid != media.children[0].guid:
        res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(album.guid))
      
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
          Proxy.Media(HTTP.Request('https://dl.dropboxusercontent.com/u/8555161/no_album.png'))
        Log('Couldn\'t add album art: ' + str(e))
      
      # Genres.
      a.genres.clear()
      for genre in res.xpath('//Directory[@type="album"]/Genre/@tag'):
        a.genres.add(genre)

      # # Add the tracks.
      # for track in res.xpath('//Track'):
        
      #   i = track.get('index')
      #   t = a.tracks[i]
        
      #   t.index = int(i)
      #   t.name = track.get('title')
      #   t.tempo = int(track.get('bpm') or 0)
        
      #   # Moods.
      #   t.moods.clear()
      #   for mood in track.xpath('./Mood/@tag'):
      #     t.moods.add(mood)
