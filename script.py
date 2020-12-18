import os
import json
import requests
import numpy as np
import pandas as pd
import urllib.parse as urlparse

from multiprocessing import Pool
from functools import partial
from base64 import b64encode
from urllib.parse import urlencode
from loguru import logger


def get_token():
    data = {
        "client_id": os.getenv("client_id"),
        "client_secret": os.getenv("client_secret"),
    }
    encoded_credentials = b64encode(
        f"{data['client_id']}:{data['client_secret']}".encode("ascii")
    ).decode("utf-8")
    headers = {"Authorization": f"Basic {encoded_credentials}"}
    return json.loads(
        requests.post(
            "https://accounts.spotify.com/api/token",
            headers=headers,
            data={"grant_type": "client_credentials"},
        ).text
    )


def make_request(route, params={}, token=None):
    if not token:
        token = get_token()
    headers = {"Authorization": f"{token['token_type']} {token['access_token']}"}

    # adding query params
    url_parse = urlparse.urlparse(route)
    query_dict = dict(urlparse.parse_qsl(url_parse.query))
    query_dict.update(params)
    query_dict = urlparse.urlencode(query_dict)
    route = urlparse.urlunparse(url_parse._replace(query=query_dict))

    logger.debug(f"Request {route}")

    return requests.get(route, headers=headers)


def get_palylist(playlist_id, **kwargs):
    request_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    response = json.loads(make_request(request_url, params=kwargs).text)
    results = response.get("items", [])
    while response.get("next"):
        response = json.loads(make_request(response.get("next"), params={}).text)
        results.extend(response.get("items", []))
    return results


def select_elements(record):
    return {
        "user": record.get("added_by", {}).get("uri"),
        "track_name": record.get("track", {}).get("name"),
        "track_id": record.get("track", {}).get("id"),
        "artists": list(
            map(
                lambda x: {"name": x["name"], "artist_id": x["id"]},
                record.get("track", {}).get("artists", []),
            )
        ),
        "album_id": record.get("track", {}).get("album", {}).get("id"),
        "album_name": record.get("track", {}).get("album", {}).get("name"),
    }


def get_track_info(track_id):
    request_url = f"https://api.spotify.com/v1/tracks/{track_id}"
    response = make_request(request_url)
    response = json.loads(response.text)
    return {"popularity": response.get("popularity")}


def get_album_genre(album_id):
    request_url = f"https://api.spotify.com/v1/albums/{album_id}"
    response = make_request(request_url)
    response = json.loads(response.text)
    return response.get("genres", [])


def get_genre_by_artist(row, **kwargs):
    genres = []
    if not isinstance(row, str):
        for artist in row.get("artists", []):
            try:
                request_url = f"https://api.spotify.com/v1/artists/{artist['artist_id']}"
                genres.extend(
                    json.loads(make_request(request_url, params=kwargs).text).get("genres", [])
                )
            except Exception as e:
                logger.error(e)
                continue
    else:
        request_url = f"https://api.spotify.com/v1/artists/{row}"
        genres.extend(json.loads(make_request(request_url, params=kwargs).text).get("genres", []))
    return list(set(genres))


def parallelize(data, func, num_of_processes=8):
    data_split = np.array_split(data, num_of_processes)
    pool = Pool(num_of_processes)
    data = pd.concat(pool.map(func, data_split))
    pool.close()
    pool.join()
    return data


def run_on_subset(func, data_subset):
    return data_subset.apply(func, axis=1)


def parallelize_on_rows(data, func, num_of_processes=8):
    return parallelize(data, partial(run_on_subset, func), num_of_processes)


if __name__ == "__main__":
    playlist_tracks_raw = get_palylist("4ZMt8eMC3Vd1G40g527Msa")
    playlist_tracks = list(map(select_elements, playlist_tracks_raw))

    df = pd.DataFrame(playlist_tracks)
    logger.info(f"Collected {df.shape[0]} musics from this playlist")

    logger.info("Getting genres")
    df["genres"] = parallelize_on_rows(df, get_genre_by_artist)
    df.to_json("playlist.json", orient="records")
