#
# Copyright (c) 2014 Plex Development Team. All rights reserved.
#

from urllib import quote
from Utils import normalize_artist_name


def find_artist_posters(posters, artist, album_titles, lang):

    # Last.fm.
    lastfm_artist = Core.messaging.call_external_function('com.plexapp.agents.lastfm', 'MessageKit:ArtistSearch', kwargs = dict(artist=artist, albums=album_titles, lang=lang))
    if lastfm_artist and lastfm_artist['name'] != 'Various Artists':
      posters.extend([image['#text'] for image in lastfm_artist['image'] if image['size'] == 'mega'])
      posters.extend([image['#text'] for image in lastfm_artist['image'] if image['size'] == 'extralarge'])
    else:
      Log('No artist result from Last.fm')

    # Discogs cache.
    try:
      images = XML.ElementFromURL('http://meta.plex.tv/a/' + quote(normalize_artist_name(artist))).xpath('//image')
      posters.extend([image.get('url') for image in images if image.get('primary') == '1'])
      posters.extend([image.get('url') for image in images if image.get('primary') == '0'])
    except:
      Log('No artist result from Discogs cache')