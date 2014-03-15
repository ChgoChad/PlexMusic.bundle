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
      results.Append(MetadataSearchResult(id = String.Quote('Various Artists'), name= 'Various Artists', thumb = VARIOUS_ARTISTS_POSTER, lang  = lang, score = 100))
      return

    artist_results = []
    score = 100
    tracks = [t.title for t in media.children[0].children]
    
    GN.ArtistSearch(media.artist,media.children[0].title,tracks,lang,artist_results,manual)
    for artist in sorted(artist_results, key=lambda k: k.score, reverse=True):
      Log('Adding artist match: %s, Score: %s' % (artist.name, score))
      artist.score = score
      score += -5
      results.Append(artist)


  def update(self, metadata, media, lang):
    title,summary,poster,genres = GN.ArtistDetails(metadata.id)
    metadata.title = title
    metadata.summary = summary
    try:
      metadata.posters[0] = Proxy.Media(HTTP.Request(poster))
    except:
      pass
    for genre in genres:
      metadata.genres.add(genre)

  
class GracenoteAlbumAgent(Agent.Album):
  name = 'Gracenote'
  languages = [Locale.Language.English]
  

  def search(self, results, media, lang, manual):
    album_results = []
    score = 100
    tracks = [t.title for t in media.children]

    GN.AlbumSearch(media.artist,media.title,tracks,lang,album_results,manual)
    for album in sorted(album_results, key=lambda k: k.score, reverse=True):
      Log('Adding album match: %s, Score: %s' % (album.name, score))
      album.score = score
      score += -5
      results.Append(album)


  def update(self, metadata, media, lang):
    title,poster,originally_available_at,genres = GN.AlbumDetails(metadata.id)
    metadata.title = title
    try:
      metadata.posters[0] = Proxy.Media(HTTP.Request(poster))
    except:
      pass
    try:
      metadata.originally_available_at = Datetime.ParseDate(originally_available_at)
    except:
      pass
    for genre in genres:
      metadata.genres.add(genre)
    
