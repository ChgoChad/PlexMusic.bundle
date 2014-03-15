from gracenote import GracenoteConnection
import time

VARIOUS_ARTISTS_POSTER = 'http://userserve-ak.last.fm/serve/252/46209667.png'
GN = GracenoteConnection()

def Start():
  HTTP.CacheTime = CACHE_1WEEK


class GracenoteArtistAgent(Agent.Artist):
  name = 'Gracenote'
  languages = [Locale.Language.English]

  def search(self, results, media, lang, manual):
    
    # Handle a couple of edge cases where artist search will give bad results.
    if media.artist == '[Unknown Artist]': 
      return
    if media.artist == 'Various Artists':
      results.Append(MetadataSearchResult(id = String.Encode('Various Artists'), name= 'Various Artists', thumb = VARIOUS_ARTISTS_POSTER, lang  = lang, score = 100))
      return

    artist_results = []
    score = 100
    tracks = [t.title for t in media.children[0].children]

    # TODO: manual searches should return more than one result
    GN.ArtistSearch(media.artist,media.children[0].title,tracks,lang,artist_results,manual)
    for artist in sorted(artist_results, key=lambda k: k.score, reverse=True):
      Log('Adding artist match: %s, Score: %s' % (artist.name, score))
      artist.score = score
      score += -5
      results.Append(artist)


  def update(self, metadata, media, lang):

    # Use a generic poster for "Various Artists"
    if metadata.title == 'Various Artists':
        metadata.posters[VARIOUS_ARTISTS_POSTER] = Proxy.Media(HTTP.Request(VARIOUS_ARTISTS_POSTER))
        return

    # Gracenote only allows searching by album, so pass along the album title hint.
    title,summary,poster,genres = GN.ArtistDetails(metadata.id,media.children[0].title)

    # Name.
    metadata.title = title

    # Artist bio.
    metadata.summary = summary

    # Artwork.
    try:
      metadata.posters[0] = Proxy.Media(HTTP.Request(poster))
    except:
      pass

    # Genres.
    for genre in genres:
      metadata.genres.add(genre)

  
class GracenoteAlbumAgent(Agent.Album):
  name = 'Gracenote'
  languages = [Locale.Language.English]
  
  def search(self, results, media, lang, manual):
    album_results = []
    score = 100
    tracks = [t.title for t in media.children]

    # TODO: manual searches should return more than one result
    GN.AlbumSearch(media.artist,media.title,tracks,lang,album_results,manual)
    for album in sorted(album_results, key=lambda k: k.score, reverse=True):
      Log('Adding album match: %s, Score: %s' % (album.name, score))
      album.score = score
      score += -5
      results.Append(album)


  def update(self, metadata, media, lang):
    
    title,poster,originally_available_at,genres = GN.AlbumDetails(metadata.id)
    
    # Album title.
    metadata.title = title
    
    # Cover art.
    try:
      metadata.posters[0] = Proxy.Media(HTTP.Request(poster))
    except:
      pass
    
    # Release date.
    try:
      metadata.originally_available_at = originally_available_at
    except:
      pass

    # Genres.
    for genre in genres:
      metadata.genres.add(genre)
    
