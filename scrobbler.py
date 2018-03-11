# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with Kodi; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html

import urllib, urllib2, socket, hashlib, time
import xbmc, xbmcgui, xbmcaddon
import inspect

import listenbrainz

ADDON        = xbmcaddon.Addon()
ADDONID      = ADDON.getAddonInfo('id')
ADDONVERSION = ADDON.getAddonInfo('version')
LANGUAGE     = ADDON.getLocalizedString

socket.setdefaulttimeout(10)

def log(txt, level=xbmc.LOGDEBUG):
    if isinstance (txt,str):
        txt = txt.decode("utf-8")
    message = u'%s: %s' % (ADDONID, txt)
    xbmc.log(msg=message.encode("utf-8"), level=level)

class Main:
    def __init__( self ):
        self._service_setup()
        while (not self.Monitor.abortRequested()) and (not self.Exit):
            xbmc.sleep(1000)

    def _service_setup( self ):
        self.ListenBrainzURL      = 'https://api.listenbrainz.org/'
        self.Exit                 = False
        self.Monitor              = MyMonitor(action = self._get_settings)
        self._get_settings()

    def _get_settings( self ):
        log('reading settings')
        service    = []
        ListenBrainzSubmitSongs = ADDON.getSetting('listenbrainzsubmitsongs') == 'true'
        ListenBrainzSubmitRadio = ADDON.getSetting('listenbrainzsubmitradio') == 'true'
        ListenBrainzToken       = ADDON.getSetting('listenbrainztoken').strip()
        if (ListenBrainzSubmitSongs or ListenBrainzSubmitRadio) and ListenBrainzToken:
            # [TODO:remove, url, token, TODO:remove, submitsongs, submitradio, sessionkey, np-url, submit-url, auth-fail, failurecount, timercounter, timerexpiretime, queue]
            service = ['TODO:REMOVE', self.ListenBrainzURL, ListenBrainzToken, 'TODO:REMOVE', ListenBrainzSubmitSongs, ListenBrainzSubmitRadio, '', '', '', False, 0, 0, 0, []]
            self.Player = MyPlayer(action = self._service_scrobble, service = service)

    def _service_scrobble( self, tags, service ):
        tstamp = int(time.time())
        # don't proceed if we had an authentication failure
        if not service[9]:
            # check if there's something in our queue for submission
            if len(service[13]) != 0:
                service = self._service_submit(service, tstamp)
            # nowplaying announce if we still have a valid session key after submission and have an artist and title
            if tags and tags[0] and tags[2]:
                service = self._service_nowplaying(service, tags)
                # check if the song qualifies for submission
                if (service[4] and not (tags[7].startswith('http://') or tags[7].startswith('rtmp://'))) or (service[5] and (tags[7].startswith('http://') or tags[7].startswith('rtmp://'))):
                    # add track to the submission queue
                    service[13].extend([tags])

    def _service_nowplaying( self, service, tags ):
        try:
            data = listenbrainz.playing_now(self.ListenBrainzURL, service[2], tags[0], tags[1], tags[2])
            log('nowplaying announce result %s' % (data))
        except listenbrainz.ListenBrainzException as error:
            log('Error: ' + repr(error), level=xbmc.LOGERROR)

        return service

    def _service_submit( self, service, tstamp ):
        # iterate through the queue
        while len(service[13]) > 0:
            tags = service[13][0]

            # only submit items that are at least 30 secs long and have been played at least half or at least 4 minutes
            if (int(tags[3]) > 30) and ((tstamp - int(tags[8]) > int(int(tags[3])/2)) or (tstamp - int(tags[8]) > 240)):
                try:
                    data = listenbrainz.submit(self.ListenBrainzURL, service[2], tags[0], tags[1], tags[2], tags[8])
                    log('submit result %s' % (data))
                    service[13].pop(0)
                except listenbrainz.ListenBrainzException as error:
                    log('Error: ' + repr(error), level=xbmc.LOGERROR)
                    return service
            else:
                service[13].pop(0)

        return service

class MyPlayer(xbmc.Player):
    def __init__( self, *args, **kwargs ):
        xbmc.Player.__init__( self )
        self.action = kwargs['action']
        self.service = kwargs['service']
        self.Audio = False
        self.Count = 0
        log('Player Class Init')

    def onPlayBackStarted( self ):
        # only do something if we're playing audio
        if self.isPlayingAudio():
            # we need to keep track of this bool for stopped/ended notifications
            self.Audio = True
            # keep track of onPlayBackStarted events http://trac.xbmc.org/ticket/13064
            self.Count += 1
            log('onPlayBackStarted: %i' % self.Count)
            # tags are not available instantly and we don't what to announce right away as the user might be skipping through the songs
            xbmc.sleep(2000)
            # don't announce if user already skipped to the next track
            if self.Count == 1:
                # reset counter
                self.Count = 0
                # get tags
                tags = self._get_tags()
                # announce song
                self.action(tags, self.service)
            else:
                # multiple onPlayBackStarted events occurred, only act on the last one
                log('skipping onPlayBackStarted event')
                self.Count -= 1

    def onPlayBackEnded( self ):
        if self.Audio:
            self.Audio = False
            log('onPlayBackEnded')
            self.action(None, self.service)

    def onPlayBackStopped( self ):
        if self.Audio:
            self.Audio = False
            log('onPlayBackStopped')
            self.action(None, self.service)

    def _get_tags( self ):
        # get track tags
        artist      = self.getMusicInfoTag().getArtist()
        album       = self.getMusicInfoTag().getAlbum()
        title       = self.getMusicInfoTag().getTitle()
        duration    = str(self.getMusicInfoTag().getDuration())
        # get duration from xbmc.Player if the MusicInfoTag duration is invalid
        if int(duration) <= 0:
            duration = str(int(self.getTotalTime()))
        track       = str(self.getMusicInfoTag().getTrack())
        #TODO: Implement mbids through .getDbId() and subsequent db query
        mbid        = '' # musicbrainz id is not available
        comment     = self.getMusicInfoTag().getComment()
        path        = self.getPlayingFile()
        timestamp   = int(time.time())
        source      = 'P'
        # streaming radio of provides both artistname and songtitle as one label
        if title and not artist:
            try:
                artist = title.split(' - ')[0]
                title = title.split(' - ')[1]
            except:
                pass
        tracktags   = [artist, album, title, duration, track, mbid, comment, path, timestamp, source]
        log('tracktags: %s' % tracktags)
        return tracktags

class MyMonitor(xbmc.Monitor):
    def __init__( self, *args, **kwargs ):
        xbmc.Monitor.__init__( self )
        self.action = kwargs['action']

    def onSettingsChanged( self ):
        log('onSettingsChanged')
        self.action()

if ( __name__ == "__main__" ):
    log('script version %s started' % ADDONVERSION)
    Main()
log('script stopped')

