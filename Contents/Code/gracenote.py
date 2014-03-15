from lxml.builder import E

class GracenoteConnection(object):

  CLIENT_ID = '4563968-0DACA396732FF5D84D6BE5EFCCCE386F'
  API_KEY = 'd5310352469c2631e5976d0f4a599773'
  BASE_URL = 'https://c4412416.ipg.web.cddbp.net/webapi/xml/1.0/'

  user_id = None

  def __init__(self):
    if 'USER_ID' not in Dict:
      Log('Requesting Gracenote user ID')
      query = (E.QUERIES(E.QUERY(E.CLIENT(self.CLIENT_ID),CMD='REGISTER')))
      try:
          res = HTTP.Request(self.BASE_URL,data=XML.StringFromElement(query))
          uid = XML.ElementFromString(res.content).xpath('//USER')[0].text
          Dict['USER_ID'] = uid
      except Exception, e:
        Log('Problem getting Gracenote user ID: ' + str(e))
  
    self.user_id = Dict['USER_ID']
    Log('Using gracenote user ID: ' + self.user_id)


  def unicodize(self,artist,album,tracks):
    try:
      artist = unicode(artist,'utf-8')
      album = unicode(artist,'utf-8')
      for i,track in enumerate(tracks):
        tracks[i] = unicode(track,'utf-8')
    except:
      pass    
    return (artist,album,tracks)


  def album_search(self,artist,album,tracks):
    artist,album,tracks = self.unicodize(artist,album,tracks)
    query = E.QUERY(E.MODE('SINGLE_BEST_COVER'),E.OPTION(E.PARAMETER('COVER_SIZE'),E.VALUE('XLARGE')),CMD='ALBUM_SEARCH')
    query.append(E.TEXT(artist,TYPE='ARTIST'))
    query.append(E.TEXT(album,TYPE='ALBUM_TITLE'))
    for track in tracks:
      query.append(E.TEXT(track,TYPE='TRACK_TITLE'))
    queries = E.QUERIES(E.AUTH(E.CLIENT(self.CLIENT_ID),E.USER(self.user_id)),query)
    Log('Built query XML:' + XML.StringFromElement(queries))
    try:
      res = HTTP.Request(self.BASE_URL,data=XML.StringFromElement(queries))
      Log('Got result XML: ' + res.content)
      return XML.ElementFromString(res.content)
    except Exception, e:
      Log('Problem running album search: ' + str(e))
    

  def artist_details(self,artist):
    query = E.QUERY(E.MODE('SINGLE_BEST_COVER'),E.OPTION(E.PARAMETER('SELECT_EXTENDED'),E.VALUE('REVIEW,ARTIST_BIOGRAPHY,ARTIST_IMAGE')),CMD='ALBUM_SEARCH')
    query.append(E.TEXT(artist,TYPE='ARTIST'))
    queries = E.QUERIES(E.AUTH(E.CLIENT(self.CLIENT_ID),E.USER(self.user_id)),query)
    Log('Built query XML:' + XML.StringFromElement(queries))
    try:
      res = HTTP.Request(self.BASE_URL,data=XML.StringFromElement(queries))
      Log('Got result XML: ' + res.content)
      return XML.ElementFromString(res.content)
    except Exception, e:
      Log('Problem getting album to extract artist details: ' + str(e))


  def album_details(self,gnid):
    query = E.QUERY(E.GN_ID(gnid),E.OPTION(E.PARAMETER('SELECT_EXTENDED'),E.VALUE('COVER')),CMD='ALBUM_FETCH')
    queries = E.QUERIES(E.AUTH(E.CLIENT(self.CLIENT_ID),E.USER(self.user_id)),query)
    Log('Built query XML:' + XML.StringFromElement(queries))
    try:
      res = HTTP.Request(self.BASE_URL,data=XML.StringFromElement(queries))
      Log('Got result XML: ' + res.content)
      return XML.ElementFromString(res.content)
    except Exception, e:
      Log('Problem fetching album details: ' + str(e))


  def ArtistSearch(self,artist,album,tracks,lang,results,manual):
    Log('Artist search: ' + artist)
    xml = self.album_search(artist,album,tracks)
    try:
      name = xml.xpath('//ARTIST')[0].text
      guid = String.Quote(name)
      results.append(MetadataSearchResult(id=guid,name=name,thumb='',lang=lang,score=100))
    except Exception, e:
      Log('Problem searching for artist: ' + str(e))


  def ArtistDetails(self,artist):
    Log('Getting artist details for: ' + artist)
    artist = String.Unquote(artist)
    xml = self.artist_details(artist)
    title,summary,poster,genres = None,None,None,[]
    try:
      title = xml.xpath('//ARTIST')[0].text
      try:
        summary = HTTP.Request(xml.xpath('//URL[@TYPE="ARTIST_BIOGRAPHY"]')[0].text).content
      except:
        raise
      try:
        poster = xml.xpath('//URL[@TYPE="ARTIST_IMAGE"]')[0].text
      except:
        pass
      try:
        genres.append(xml.xpath('//GENRE')[0].text)
      except:
        pass
    except Exception, e:
      Log('Problem getting artist details: ' + str(e))
    return title,summary,poster,genres


  def AlbumSearch(self,artist,album,tracks,lang,results,manual):
    Log('Album search: %s - %s' % (artist,album))
    xml = self.album_search(artist,album,tracks)
    try:
      guid = xml.xpath('//ALBUM/GN_ID')[0].text
      name = xml.xpath('//ALBUM/TITLE')[0].text
      results.append(MetadataSearchResult(id=guid,name=name,thumb='',lang=lang,score=100))
    except Exception, e:
      Log('Problem searching for album: ' + str(e))      


  def AlbumDetails(self,gnid):
    Log('Getting album details for: ' + gnid)
    xml = self.album_details(gnid)
    title,poster,originally_available_at,genres = None,None,None,[]
    try:
      title = xml.xpath('//TITLE')[0].text
      try:
        poster = xml.xpath('//URL[@TYPE="COVERART"]')[0].text
      except:
        pass
      try:
        originally_available_at = Datetime.ParseDate(xml.xpath('//DATE')[0].text)
      except:
        pass
      try:
        genres.append(xml.xpath('//GENRE')[0].text)
      except:
        pass
    except Exception, e:
      Log('Problem getting album details: ' + str(e))
    return title,poster,originally_available_at,genres
