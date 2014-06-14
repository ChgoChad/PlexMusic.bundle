#
# Copyright (c) 2014 Plex Development Team. All rights reserved.
#

from urllib import urlencode # TODO: expose urlencode for dicts in the Framework?

def Start():
  HTTP.CacheTime = 30

class GracenoteArtistAgent(Agent.Artist):
  name = 'Gracenote'
  languages = [Locale.Language.English,Locale.Language.NoLanguage]
  modern = True

  def search(self, results, media, lang, manual):
    
    # TODO: [Unknown Artist] and Various Artists.  Hmmmmm....
    if media.artist == '[Unknown Artist]' or media.artist == 'Various Artists': 
      return

    # TODO: Manual matches should re-run the AlbumID search with any newly entered criteria.
    # For now, just pass so we get the GUID back.
    if manual:
      pass

    # Make sure all albums have Gracenote ID's, search for them if not.
    for album in media.children:
      if not album.guid.startswith('com.plexapp.agents.gracenote'):
        Log('Found guid: ' + album.guid + ', running Gracenote search...')
        gracenote_search(media, album, lang, fingerprint=manual)

    results.Append(MetadataSearchResult(
      id = media.guid,
      score = 100
    ))


  def update(self, metadata, media, lang):

    Log('UPDATING!')
    Log('metadata is: ' + str(metadata))
    for album in metadata.children:
      res = HTTP.Request('http://127.0.0.1/gracenote/update?guid=%' + album.id)
      Log('Got album metadata: ' + XML.StringFromElement(res))
      summary = res.xpath('//Directory[@type="album"]')[0].get('summary')
      Log('Upadting with summary: ' + summary)
      album.summary = summary

def gracenote_search(media, album, lang, fingerprint=False):

  args = {}
  for i,track in enumerate(album.children):
    args['tracks[%d].path' % i]        = track.items[0].parts[0].file
    args['tracks[%d].userData' % i]    = i
    args['tracks[%d].track' % i]       = track.title
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
