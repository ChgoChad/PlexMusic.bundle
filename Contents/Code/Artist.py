#
# Copyright (c) 2014 Plex Development Team. All rights reserved.
#

from urllib import quote
from Utils import normalize_artist_name

LASTFM_ARTWORK_SIZE_RANKING = { 'mega':0 , 'extralarge':1 , 'large':2 }


def fetch_artist_posters(metadata, media, gracenote_result, lang, debug):

    valid_keys = []

    # Gracenote.
    gracenote_keys = []
    artist_poster_url = gracenote_result.xpath('//Directory[@type="album"]')[0].get('parentThumb')
    try:
      if len(artist_poster_url) > 0:
        metadata.posters[artist_poster_url] = Proxy.Media(HTTP.Request(artist_poster_url))
        gracenote_keys.append(artist_poster_url)
        valid_keys.append(artist_poster_url)
    except Exception, e:
      Log('Error fetching Gracenote artist poster (%s): %s' % (artist_poster_url, str(e)))
    Log('Found artist posters from Gracenote: %s' % gracenote_keys)

    # Last.fm.
    lastfm_keys = []
    if len(valid_keys) == 0 or debug:
      albums = [a.title for a in media.children]  # The Last.fm agent uses album titles to refine artist search results.
      try:
        Log('running LFM search with artist: %s and albums: %s' % (metadata.title, albums))
        lastfm_artist = Core.messaging.call_external_function('com.plexapp.agents.lastfm', 'MessageKit:ArtistSearch', kwargs = dict(artist=metadata.title, albums=albums, lang=lang))
        if lastfm_artist['name'] != 'Various Artists':
          image_urls = [image['#text'] for image in lastfm_artist['image'] if image['size'] == 'mega']
          image_urls.extend([image['#text'] for image in lastfm_artist['image'] if image['size'] == 'extralarge'])
          for image_url in image_urls:
            try:
              metadata.posters[image_url] = Proxy.Media(HTTP.Request(image_url))
              lastfm_keys.append(image_url)
              valid_keys.append(image_url)
            except Exception, e:
              Log('Error fetching Last.fm artist poster (%s): %s' % (image_url, str(e)))
      except Exception, e:
        Log('Error fetching Last.fm artist posters: %s' % str(e))
      Log('Found artist posters from Last.fm: %s' % lastfm_keys)

    # Discogs cache.
    discogs_keys = []
    if len(valid_keys) == 0 or debug:
      try:
        images = XML.ElementFromURL('http://meta.plex.tv/a/' + quote(normalize_artist_name(metadata.title))).xpath('//image')
        image_urls = [image.get('url') for image in images if image.get('primary') == '1']
        image_urls.extend([image.get('url') for image in images if image.get('primary') == '0'])
        for image_url in image_urls:
          try:
            metadata.posters[image_url] = Proxy.Media(HTTP.Request(image_url))
            discogs_keys.append(image_url)
            valid_keys.append(image_url)
          except Exception, e:
            Log('Error fetching Discogs artist poster (%s): %s' % (image_url, str(e)))    
      except Exception, e:
        if e.code != 404:
          Log('Error fetching Discogs artist posters: %s' % str(e))
      Log('Found artist posters from Discogs: %s' % discogs_keys)

    if len(valid_keys) == 0 and debug:
      dummy_poster_url = 'https://dl.dropboxusercontent.com/u/8555161/no_artist.png'
      metadata.posters[dummy_poster_url] = Proxy.Media(HTTP.Request(dummy_poster_url))
      valid_keys.append(dummy_poster_url)

    metadata.posters.validate_keys(valid_keys)