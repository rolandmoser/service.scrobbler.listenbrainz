import time
import requests
from requests.auth import HTTPDigestAuth

import xbmcaddon
ADDON        = xbmcaddon.Addon()
useragent    = '%s/%s (https://github.com/rolandmoser/service.scrobbler.listenbrainz)' % (ADDON.getAddonInfo('id'), ADDON.getAddonInfo('version'))

class ListenBrainzException(Exception):
    pass

def playing_now(lbUrl, lbToken, artist, album, title, timestamp):
    url = "%s/1/submit-listens" % (lbUrl)

    payload = [
        {
#            "listened_at": int(timestamp),
            "track_metadata": {
                "artist_name": artist,
                "track_name": title,
                "release_name": album
            }
        }
    ]
#            "additional_info": {
#                "release_mbid": "bf9e91ea-8029-4a04-a26a-224e00a83266",
#                "artist_mbids": [
#                    "db92a151-1ac2-438b-bc43-b82e149ddd50"
#                ],
#                "recording_mbid": "98255a8c-017a-4bc7-8dd6-1fa36124572b",
#                "tags": [ "you", "just", "got", "rick rolled!"]
#            },

    listen_type = "playing_now"

    resp = requests.post(
        url=url,
        json={
            "listen_type": listen_type,
            "payload": payload,
        },
        headers={
            "Authorization": "Token {0}".format(lbToken)
        }
    )

    if resp.status_code == 401:
        raise ListenBrainzException('Unauthorized')
    elif resp.status_code == 400:
        raise ListenBrainzException('Bad Request')
    elif resp.status_code <> 200:
        raise ListenBrainzException(resp.status_code)

    return (resp.json()['status'] == 'ok')

