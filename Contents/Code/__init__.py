#
# Copyright (c) 2014 Plex Development Team. All rights reserved.
#

from urllib import urlencode # TODO: expose urlencode for dicts in the Framework?


def Start():
  HTTP.CacheTime = 30


class GracenoteArtistAgent(Agent.Artist):

  name = 'Gracenote'
  languages = [Locale.Language.English,Locale.Language.NoLanguage]
  version = 2

  def search(self, results, tree, hints, lang, manual):

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

    artist = MetadataItem(id=tree.id, title=first_track.get('grandparentTitle'), guid=first_track.get('grandparentGUID'), index='1', score=100)

    # TODO: Return real artist thumb URLs.
    artist.thumb = 'http://cdn.last.fm/flatness/responsive/2/noimage/default_artist_140_g2.png'

    album = MetadataItem(id=tree.albums.values()[0].id, title=first_track.get('parentTitle'), guid=first_track.get('parentGUID'), originally_available_at=first_track.get('year'))

    # TODO: Return real album thumb URLs.
    album.thumb = 'http://cdn.last.fm/flatness/responsive/2/noimage/default_album_140_g2.png'

    for track in res.xpath('//Track'):
      album.add(MetadataItem(matched='1', title=track.get('title'), id=track.get('userData'), guid=track.get('guid'), index=track.get('index')))

    artist.add(album)
    results.add(artist)


  def update(self, metadata, media, lang, child_guid=None):

    Log('Updating: ' + media.guid)

    # Fetch the first Album to use for Artist data.
    res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(media.children[0].guid))
    metadata.title = res.xpath('//Directory[@type="album"]')[0].get('parentTitle')
    metadata.summary = res.xpath('//Directory[@type="album"]')[0].get('parentSummary')
    try:
      metadata.posters[0] = Proxy.Media(HTTP.Request(res.xpath('//Directory[@type="album"]')[0].get('parentThumb')))
    except Exception, e:
      Log('Couldn\'t add artist art: ' + str(e))

    for album in media.children:
      if not child_guid or child_guid == album.guid:

        Log('Updating album: ' + album.title)
        res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(album.guid))
        # Log('Got album metadata:\n' + XML.StringFromElement(res))

        # Add album metadata.
        a = metadata.albums[album.guid]
        a.title = res.xpath('//Directory[@type="album"]')[0].get('title')
        a.summary = res.xpath('//Directory[@type="album"]')[0].get('summary')
        a.studio = res.xpath('//Directory[@type="album"]')[0].get('studio')
        a.originally_available_at = Datetime.ParseDate(res.xpath('//Directory[@type="album"]')[0].get('year'))
        try:
          a.posters[0] = Proxy.Media(HTTP.Request(res.xpath('//Directory[@type="album"]')[0].get('thumb')))
        except Exception, e:
          Log('Couldn\'t add album art: ' + str(e))
        
        # Genres.
        a.genres.clear()
        for genre in res.xpath('//Directory[@type="album"]/Genre/@tag'):
          a.genres.add(genre)

        # Add the tracks.
        for track in res.xpath('//Track'):
          
          i = track.get('index')
          t = a.tracks[i]
          
          t.index = int(i)
          t.name = track.get('title')
          t.tempo = int(track.get('bpm') or 0)
          
          # Moods.
          t.moods.clear()
          for mood in track.xpath('./Mood/@tag'):
            t.moods.add(mood)
