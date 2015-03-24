#
# Copyright (c) 2014 Plex Development Team. All rights reserved.
#

from urllib import urlencode  # TODO: expose urlencode for dicts in the Framework?
from collections import Counter
from Utils import normalize_artist_name
from Artist import find_artist_posters, find_artist_art

DEBUG = Prefs['debug']
LFM_RED_POSTER_HASHES = ['1c117ac7c5303f4a273546e0965c5573', '833dccc04633e5616e9f34ae5d5ba057']


def Start():
  HTTP.CacheTime = 30

def album_search(tree, album, lang, album_results, artist_guids=[], fingerprint='1', artist_thumbs=[]):

  args = {}

  if hasattr(album, 'artist'):
    artist = album.artist
    title = album.title
  else:
    artist = tree.title
    title = tree.albums.values()[0].title

  for i, track in enumerate(album.children):
    args['tracks[%d].path' % i]        = track.items[0].parts[0].file
    args['tracks[%d].userData' % i]    = track.id
    args['tracks[%d].track' % i]       = track.title
    if hasattr(track, 'originalTitle'):
      args['tracks[%d].artist' % i]    = track.originalTitle
    args['tracks[%d].albumArtist' % i] = artist
    args['tracks[%d].album' % i]       = title
    if hasattr(track, 'index'):
      args['tracks[%d].index' % i]     = track.index
    args['lang']                       = lang

  querystring = urlencode(args).replace('%5B','[').replace('%5D',']')
  url = 'http://127.0.0.1:32400/services/gracenote/search?fingerprint=%s&%s' % (fingerprint, querystring)
  
  try:
    res = XML.ElementFromURL(url)
    if DEBUG:
      Log(XML.StringFromElement(res))
    track_xml = res.xpath('//Track')
    if len(track_xml) > 0:
      first_track = [0]
    else:
      Log('No matches from Gracenote search')
      return
  except Exception, e:
    Log('Exception running Gracenote search: ' + str(e))
    return

  # Go back and get the full album for more reliable metadata and so we can populate any missing tracks in the SearchResult.
  album_guid_consensus = Counter([t.get('parentGUID') for t in res.xpath('//Track')]).most_common()[0][0]
  Log('Got consensus on album GUID: %s' % album_guid_consensus)
  album_res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(album_guid_consensus))
  album_elm = album_res.xpath('//Directory')[0]

  if DEBUG:
    Log(XML.StringFromElement(album_res))

  # No album art from gracenote, clear out the thumb.
  thumb = album_elm.get('thumb')
  if thumb == 'http://': 
    thumb = ''

  artist_thumbs.append(album_elm.get('parentThumb'))

  track_results = []
  matched_guids = [t.get('guid') for t in album_res.xpath('//Track')]
  for track in sorted(album_res.xpath('//Track'), key=lambda i: int(i.get('index'))):
    matched = '1' if track.get('guid') in matched_guids else '0'
    track_results.append(SearchResult(matched=matched, type='track', name=track.get('title'), id=track.get('userData'), guid=track.get('guid'), index=track.get('index')))

  # Score based on number of matched tracks.  Used when checking against a threshold for automatically matching after renaming/reparenting.
  album_score = int((len([t for t in track_results if t.matched == '1']) / float(max(len(track_results), len(album.children)))) * 100)
  album_result = SearchResult(id=album.id, type='album', parentName=album_elm.get('parentTitle'), name=album_elm.get('title'), guid=album_guid_consensus, thumb=thumb, year=album_elm.get('year'), parentGUID=album_elm.get('parentGUID'), score=album_score)
  for track_result in track_results:
    album_result.add(track_result)

  Log('Got album result: %s (score: %d)' % (album_result.name, album_result.score))
  album_results.append(album_result)
  artist_guids.append(album_elm.get('parentGUID'))


class GracenoteArtistAgent(Agent.Artist):

  name = 'Plex Premium Music'
  languages = [Locale.Language.English,Locale.Language.NoLanguage]
  contributes_to = ['com.plexapp.agents.localmedia']

  def search(self, results, media, lang='en', manual=False, tree=None, primary=True):

    # Don't do automatic matching for this agent.
    if not manual:
      return

    # Good match when being used as a secondary agent.
    if not primary:
      results.add(SearchResult(id=tree.id, score=100))

    if Prefs['debug']:
      Log('tree -> albums: %s, all_parts: %d, children: %d, guid: %s, id: %s, originally_available_at: %s, title: %s' % (tree.albums, len(tree.all_parts()), len(tree.children), tree.guid, tree.id, tree.originally_available_at, tree.title))

    album_results = []
    artist_guids = []
    artist_thumbs = []
    for j, album in enumerate(tree.albums.values()):
      album_search(tree, album, lang, album_results, artist_guids, artist_thumbs=artist_thumbs)

      # Limit to five albums for artist consensus. TODO: This may be too many, it takes a while.
      if j > 4:
        break

    if not artist_guids:
      Log('No Gracenote artists found for %s' % tree.title)
      return

    artist_guid_counter = Counter(artist_guids).most_common()
    artist_guid_consensus = artist_guid_counter[0][0]
    Log('Got consensus on artist GUID: %s' % artist_guid_consensus)  # TODO: Gracenote is returning all different GnUId's for these :(
    for album_result in album_results:
      if album_result.parentGUID == artist_guid_consensus:
        artist_name = album_result.parentName
        break
      
    # Score based on the proportion of albums that matched.
    artist_score = int(50 + 50 * (artist_guid_counter[0][1] / float(len(tree.albums))))

    artist_thumb = artist_thumbs[0] if artist_thumbs else ''
    artist_result = SearchResult(id=tree.id, type='artist', name=artist_name, guid=artist_guid_consensus, score=artist_score, thumb=artist_thumb)
    for album_result in album_results:
      artist_result.add(album_result)

    Log('Got artist result: %s (score: %d)' % (artist_result.name, artist_result.score))
    results.add(artist_result)


  def update(self, metadata, media, lang):

    Log('Updating: %s (GUID: %s)' % (media.title, media.guid))

    posters = []
    arts = []

    # Special art for VA.
    if metadata.title == 'Various Artists':
      posters.append('http://music.plex.tv/pixogs/various_artists_poster.jpg')
      arts.append('http://music.plex.tv/pixogs/various_artists_art.jpg')
      return

    # Do nothing for unknown.
    elif metadata.title == '[Unknown Artist]':
      return

    gracenote_guids = [c.guid for c in media.children if c.guid.startswith('com.plexapp.agents.plexmusic://gracenote/')]
    if len(gracenote_guids) > 0:
  
      # Fetch an album (use the given child_guid if we have it) and use the artist data from that.
      res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(gracenote_guids[0]))

      if DEBUG:
        Log('Raw GN result:')
        Log(XML.StringFromElement(res))

      # Artist name.
      artist_name = res.xpath('//Directory[@type="album"]')[0].get('parentTitle')
      if metadata.title is None:
        metadata.title = artist_name

      # Artist bio.
      metadata.summary = res.xpath('//Directory[@type="album"]')[0].get('parentSummary')

      # Artist country.
      metadata.countries.clear()
      metadata.countries.add(res.xpath('//Directory[@type="album"]')[0].get('parentCountry'))

      # Artist poster.
      gracenote_poster = res.xpath('//Directory[@type="album"]')[0].get('parentThumb')

    # Find artist posters and art from other sources.
    album_titles = [a.title for a in media.children]
    find_artist_art(arts, metadata.title, album_titles, lang)
    find_artist_posters(posters, metadata.title, album_titles, lang)

    # If we had a Gracenote poster, add it last.
    if len(gracenote_poster) > 0:
      posters.append(gracenote_poster)

    # Placeholder image if we're in DEBUG mode.
    if len(posters) == 0 and DEBUG:
      posters.append('https://dl.dropboxusercontent.com/u/8555161/no_artist.png')

    # Add posters.
    valid_keys = []
    for i, poster in enumerate(posters):
      try:
        poster_req = HTTP.Request(poster)
        poster_req.load()
        poster_data = poster_req.content
        poster_hash = Hash.MD5(poster_data)

        # Avoid the Last.fm placeholder image.
        if poster_hash not in LFM_RED_POSTER_HASHES:
          Log('Adding poster with hash: %s' % poster_hash)
          metadata.posters[poster] = Proxy.Media(poster_data, sort_order='%02d' % (i + 1))
          valid_keys.append(poster)
        else:
          Log('Skipping Last.fm Red Poster of Death: %s' % poster)

      except Exception, e:
        Log('Couldn\'t add poster (%s): %s' % (poster, str(e)))
    
    metadata.posters.validate_keys(valid_keys)

    # Add art.
    valid_keys = []
    for i, art in enumerate(arts):
      try:
        metadata.art[art[0]] = Proxy.Preview(HTTP.Request(art[1]), sort_order='%02d' % (i + 1))
        valid_keys.append(art[0])
      except Exception, e:
        Log('Couldn\'t add art (%s): %s' % (art[0], str(e)))

    metadata.art.validate_keys(valid_keys)


class GracenoteAlbumAgent(Agent.Album):

  name = 'Plex Premium Music'
  languages = [Locale.Language.English,Locale.Language.NoLanguage]
  contributes_to = ['com.plexapp.agents.localmedia']


  def search(self, results, media, lang, manual=False, tree=None, primary=False):
    
    # Don't do automatic matching for this agent.
    if not manual:
      return

    # Good match when being used as a secondary agent.
    if not primary:
      results.add(SearchResult(id=tree.id, score=100))

    album_results = []
    for fingerprint in ['0', '1']:
      album_search(tree, media, lang, album_results, fingerprint=fingerprint)

    seen = []
    Log(str(seen))
    for album_result in album_results:
      if not (album_result.parentName, album_result.name) in seen:
        results.add(album_result)
        seen.append((album_result.parentName, album_result.name))


  def update(self, metadata, media, lang):

    Log('Updating album: ' + media.title)
    Log('With guid: ' + media.guid)

    # Even if this album itself is not a Gracenote album, we may have some tracks that came from one, or we may be post multi-disc merge.
    # Look through all the tracks for their parent GNIDs. Later, we'll load each one so we can update track data for everything.
    #
    album_gnids = set([track.guid.split('/')[-2] for track in media.children if 'com.plexapp.agents.plexmusic://gracenote' in track.guid])

    if len(album_gnids) == 0:
      Log('Didn\'t find any tracks from Gracenote albums, aborting')
      return

    try:
      res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(media.guid))
    except Exception, e:
      Log('Error issuing album update request: ' + str(e))
      return
    
    if DEBUG:
      Log('Got album metadata:\n' + XML.StringFromElement(res))

    if metadata.title is None:
      metadata.title = res.xpath('//Directory[@type="album"]')[0].get('title')
    metadata.summary = res.xpath('//Directory[@type="album"]')[0].get('summary')
    metadata.studio = res.xpath('//Directory[@type="album"]')[0].get('studio')
    metadata.originally_available_at = Datetime.ParseDate(res.xpath('//Directory[@type="album"]')[0].get('year'))

    # Posters.
    try:
      poster_url = res.xpath('//Directory[@type="album"]')[0].get('thumb')
      if len(poster_url) > 0:
        metadata.posters[0] = Proxy.Media(HTTP.Request(poster_url))
    except Exception, e:
      Log('Couldn\'t add album art: ' + str(e))

    if DEBUG and len(metadata.posters) == 0:
      metadata.posters[0] = Proxy.Media(HTTP.Request('https://dl.dropboxusercontent.com/u/8555161/no_album.png'))
    
    # Genres.
    metadata.genres.clear()
    genres = [genre for genre in res.xpath('//Directory[@type="album"]/Genre/@tag')]
    if len(genres) > 0 and Prefs['genre_level'] == 'Coarse (10 genres)':
      metadata.genres.add(genres[0])
    elif len(genres) > 1 and Prefs['genre_level'] == 'Medium (75 genres)':
      metadata.genres.add(genres[1])
    elif len(genres) > 2 and Prefs['genre_level'] == 'Fine (500 genres)':
      metadata.genres.add(genres[2])

    # Go back and get track metadata for any additional albums if needed.
    if 'com.plexapp.agents.plexmusic://gracenote' in media.guid:
      album_gnids.remove(media.guid.split('/')[-1].split('?')[0])

    for album_gnid in album_gnids:
      
      dummy_guid = 'com.plexapp.agents.plexmusic://gracenote/x/%s?%s' % (album_gnid, media.guid.split('?')[-1]) 
      try:
        additional_res = XML.ElementFromURL('http://127.0.0.1:32400/services/gracenote/update?guid=' + String.URLEncode(dummy_guid))
      except Exception, e:
        Log('Error issuing album update request: ' + str(e))
        continue
      
      for track in additional_res.xpath('//Track'):
        res.xpath('//Directory')[0].append(track)

    # Add the tracks.
    for track in res.xpath('//Track'):
      
      i = track.get('index')
      t = metadata.tracks[track.get('guid')]
      
      t.index = int(track.get('index'))
      t.name = track.get('title')
      t.tempo = int(track.get('bpm') or -1)

      # Moods.
      t.moods.clear()
      for mood in track.xpath('./Mood/@tag'):
        t.moods.add(mood)
