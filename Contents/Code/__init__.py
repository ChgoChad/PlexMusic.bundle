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


  def search(self, results, media, lang, manual):

    Log('Matching Artist: ' + str(media.artist))
    Log('Albums: ' + str(len(media.children)))

    # TODO: [Unknown Artist] and Various Artists.  Hmmmmm....
    if media.artist == '[Unknown Artist]' or media.artist == 'Various Artists': 
      return

    # TODO: Manual matches should re-run the AlbumID search with any newly entered criteria.
    # For now, just pass so we get the GUID back.
    if manual:
      pass

    # Make sure all albums have Gracenote ID's, search for them if not.
    result_guid = media.guid
    for album in media.children:
      if not album.guid.startswith('com.plexapp.agents.gracenote'):
        Log('Found guid: ' + album.guid + ', running Gracenote search...')
        result_guid = gracenote_search(media, album, lang, fingerprint=manual)
        Log('Found artist guid: ' + result_guid)

    results.Append(MetadataSearchResult(
      id = result_guid,
      name = media.artist,
      score = 100
    ))

    Log('Result 0 id: ' + str(results[0].id))
    Log('Result 0 name: ' + str(results[0].name))


  def update(self, metadata, media, lang):

    Log('Updating: ' + media.guid)

    # Fetch the first Album to use for Artist data.
    res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(media.children[0].guid))
    metadata.title = res.xpath('//Directory[@type="album"]')[0].get('parentTitle')
    metadata.summary = res.xpath('//Directory[@type="album"]')[0].get('parentSummary')

    # Fetch the art if we have it.
    for i in range(int(res.xpath('//Directory[@type="album"]')[0].get('artistArtCount'))):
      image = HTTP.Request('http://127.0.0.1:32400/services/gracenote/thumb?guid=%s&type=artist&ord=%d' % (String.URLEncode(media.children[0].guid), i+1)).content
      metadata.posters[i] = Proxy.Media(image, sort_order=i)

    for album in media.children:

      Log('Updating album: ' + album.title)
      res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(album.guid))
      # Log('Got album metadata:\n' + XML.StringFromElement(res))

      # Add album metadata.
      a = metadata.albums[album.guid]
      a.title = res.xpath('//Directory[@type="album"]')[0].get('title')
      a.summary = res.xpath('//Directory[@type="album"]')[0].get('summary')
      a.studio = res.xpath('//Directory[@type="album"]')[0].get('studio')
      a.originally_available_at = Datetime.ParseDate(res.xpath('//Directory[@type="album"]')[0].get('year'))
      
      # Genres.
      a.genres.clear()
      for genre in res.xpath('//Directory[@type="album"]/Genre/@tag'):
        a.genres.add(genre)

      # Fetch the art if we have it.
      for i in range(int(res.xpath('//Directory[@type="album"]')[0].get('albumArtCount'))):
        image = HTTP.Request('http://127.0.0.1:32400/services/gracenote/thumb?guid=%s&type=album&ord=%d' % (String.URLEncode(album.guid), i+1)).content
        a.posters[i] = Proxy.Media(image, sort_order=i)

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


def gracenote_search(media, album, lang, fingerprint=False):

  args = {}
  for i,track in enumerate(album.children):
    args['tracks[%d].path' % i]        = track.items[0].parts[0].file
    args['tracks[%d].userData' % i]    = i
    args['tracks[%d].track' % i]       = track.title
    if hasattr(track, 'originalTitle'):
      args['tracks[%d].artist' % i]      = track.originalTitle
    args['tracks[%d].albumArtist' % i] = media.title
    args['tracks[%d].album' % i]       = album.title
    args['tracks[%d].index' % i]       = track.index
    args['lang']                       = lang

  querystring = urlencode(args).replace('%5B','[').replace('%5D',']')
  url = 'http://127.0.0.1:32400/services/gracenote/search?' + querystring
  if fingerprint:
    Log('requesting fingerprinting for manual search')
    url += '&fingerprint=1'
  
  res = XML.ElementFromURL(url)
  guid = res.xpath('//Track')[0].get('parentGUID')

  # Make sure all the tracks claim to come from the same album.
  for track in res.xpath('//Track'):
    if track.get('parentGUID') != guid:
      # TODO: Handle this case...
      Log('Found a track that doesn\'t seem to come from the same album (guid of %s vs %s)' % (track.get('parentGUID'),guid))

  if guid:
    Log('Updating album guid %s -> %s' % (album.guid,guid))
    album.guid = guid

  return res.xpath('//Track')[0].get('grandparentGUID')
