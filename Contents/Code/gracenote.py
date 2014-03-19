from lxml.builder import E
import subprocess

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


  def build_search_request(self,mode,artist=None,album=None,tracks=None,**kwargs):
    query = E.QUERY(E.MODE(mode),CMD='ALBUM_SEARCH')
    for key,value in kwargs.iteritems():
      query.append(E.OPTION(E.PARAMETER(key),E.VALUE(value)))
    if artist:
      query.append(E.TEXT(artist,TYPE='ARTIST'))
    if album:
      query.append(E.TEXT(album,TYPE='ALBUM_TITLE'))
    if tracks:
      for track in tracks:
        query.append(E.TEXT(track,TYPE='TRACK_TITLE'))
    queries = E.QUERIES(E.AUTH(E.CLIENT(self.CLIENT_ID),E.USER(self.user_id)),query)
    Log('Built query XML:' + XML.StringFromElement(queries))
    return queries


  def build_fetch_request(self,gnid,**kwargs):
    query = E.QUERY(E.GN_ID(gnid),CMD='ALBUM_FETCH')
    for key,value in kwargs.iteritems():
      query.append(E.OPTION(E.PARAMETER('SELECT_EXTENDED'),E.VALUE('COVER')))
    queries = E.QUERIES(E.AUTH(E.CLIENT(self.CLIENT_ID),E.USER(self.user_id)),query)
    Log('Built query XML:' + XML.StringFromElement(queries))
    return queries


  def execute_query(self,request_body):
    try:
      res = HTTP.Request(self.BASE_URL,data=XML.StringFromElement(request_body))
      Log('Got result XML: ' + res.content)
      return XML.ElementFromString(res.content)
    except Exception, e:
      Log('Problem executing query: ' + str(e))


  def ArtistSearch(self,artist,album,tracks,lang,results,manual):
    Log('Artist search: ' + artist)
    artist,album,tracks = self.unicodize(artist,album,tracks)
    request_body = self.build_search_request('SINGLE_BEST_COVER',artist=artist,album=album,tracks=tracks)
    response = self.execute_query(request_body)
    try:
      name = response.xpath('//ARTIST')[0].text
      guid = String.Encode(name)
      results.append(MetadataSearchResult(id=guid,name=name,thumb='',lang=lang,score=100))
    except Exception, e:
      Log('Problem searching for artist: ' + str(e))


  def ArtistDetails(self,artist,album):
    artist = String.Decode(artist)
    Log('Getting artist details for: ' + artist)
    request_body = self.build_search_request('SINGLE_BEST',artist=artist,album=album,SELECT_EXTENDED='ARTIST_BIOGRAPHY,ARTIST_IMAGE')
    response = self.execute_query(request_body)
    title,summary,poster,genres = None,None,None,[]
    try:
      title = response.xpath('//ARTIST')[0].text
      try:
        summary = HTTP.Request(response.xpath('//URL[@TYPE="ARTIST_BIOGRAPHY"]')[0].text).content
      except:
        pass
      try:
        poster = response.xpath('//URL[@TYPE="ARTIST_IMAGE"]')[0].text
      except:
        pass
      try:
        genres.append(response.xpath('//GENRE')[0].text)
      except:
        pass
    except Exception, e:
      Log('Problem getting artist details: ' + str(e))
    return title,summary,poster,genres


  def AlbumSearch(self,artist,album,tracks,lang,results,manual):
    Log('Album search: %s - %s' % (artist,album))
    artist,album,tracks = self.unicodize(artist,album,tracks)
    request_body = self.build_search_request('SINGLE_BEST_COVER',artist=artist,album=album,tracks=tracks,COVER_SIZE='XLARGE')
    response = self.execute_query(request_body)
    try:
      guid = response.xpath('//ALBUM/GN_ID')[0].text
      name = response.xpath('//ALBUM/TITLE')[0].text
      results.append(MetadataSearchResult(id=guid,name=name,thumb='',lang=lang,score=100))
    except Exception, e:
      Log('Problem searching for album: ' + str(e))      


  def AlbumDetails(self,gnid):
    Log('Getting album details for: ' + gnid)
    request_body = self.build_fetch_request(gnid,SELECT_EXTENDED='COVER')
    response = self.execute_query(request_body)
    title,poster,originally_available_at,genres = None,None,None,[]
    try:
      title = response.xpath('//TITLE')[0].text
      try:
        poster = response.xpath('//URL[@TYPE="COVERART"]')[0].text
      except:
        pass
      try:
        originally_available_at = Datetime.ParseDate(response.xpath('//DATE')[0].text)
      except:
        pass
      try:
        genres.append(response.xpath('//GENRE')[0].text)
      except:
        pass
    except Exception, e:
      Log('Problem getting album details: ' + str(e))
    return title,poster,originally_available_at,genres

class GracenoteSDKRunner(object):

  gn_binary_path = None
  gn_temp_path = None
  gn_user_path = None

  def __init__(self):
    Log('Plex support files are in ' + Core.app_support_path)

    bundle_dir = Core.storage.join_path(Core.app_support_path, Core.config.bundles_dir_name)
    self.gn_binary_path = Core.storage.join_path(bundle_dir,'Gracenote.bundle','Contents','MacOS','lookup')
    Log('Using lookup binary: ' + self.gn_binary_path)

    plugin_support_dir = Core.storage.join_path(Core.app_support_path, Core.config.plugin_support_dir_name)
    self.gn_temp_path = Core.storage.join_path(plugin_support_dir,'Data','com.plexapp.agents.gracenote','Temp')
    Core.storage.ensure_dirs(self.gn_temp_path)
    Log('Using temp directory: ' + self.gn_temp_path)
    
    self.gn_user_path = Core.storage.join_path(plugin_support_dir,'Data','com.plexapp.agents.gracenote','User')
    Core.storage.ensure_dirs(self.gn_user_path)
    Log('Using user directory: ' + self.gn_user_path)

  def unicodize(self,artist,album,tracks):
    try:
      artist = unicode(artist,'utf-8')
      album = unicode(artist,'utf-8')
      for i,track in enumerate(tracks):
        tracks[i] = unicode(track,'utf-8')
    except:
      pass    
    return (artist,album,tracks)

  def runGNSDK(self,artist,album,tracks):
    # Random output directory.
    out_dir = Core.storage.join_path(self.gn_temp_path,'%010x' % Util.RandomInt(0,16**10))
    args = [self.gn_binary_path,artist,album,self.gn_user_path,out_dir] + [t for t in tracks]

    # Call the SDK lookup app and wait for it to return.
    Log('Calling GNSDK lookup with args: ' + str(args))
    rc = subprocess.Popen(args).wait()
    Log('GNSDK returned with ' + str(rc))

    return out_dir

  def ArtistSearch(self,artist,album,tracks,lang,results,manual):
    Log('Artist search: ' + artist)
    artist,album,tracks = self.unicodize(artist,album,tracks)

    # Call the lookup and parse the resulting output files.
    out_dir = self.runGNSDK(artist,album,tracks)
    xml = XML.ElementFromString(Core.storage.load(Core.storage.join_path(out_dir,'album_gdo.xml')))
    try:
      name = xml.xpath('//ARTIST/NAME_OFFICIAL/DISPLAY')[0].text
      guid = String.Encode(name)
      results.append(MetadataSearchResult(id=guid,name=name,thumb='',lang=lang,score=100))
    except Exception, e:
      Log('Problem searching for artist: ' + str(e))

  def ArtistDetails(self,artist,album):
    pass

  def AlbumSearch(self,artist,album,tracks,lang,results,manual):
    pass

  def AlbumDetails(self,gnid):
    pass








