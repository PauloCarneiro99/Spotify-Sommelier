import json
import pandas as pd
import requests

from loguru import logger
from spotipy.oauth2 import SpotifyClientCredentials

credentials = SpotifyClientCredentials()


def make_put_request(request_url, body):
    headers = {"Authorization": f"Bearer {credentials.get_access_token()}"}
    return requests.put(request_url, data=body, headers=headers)


def update_index(current_index, index):
    return current_index + 1 if current_index < index else current_index


def reorder_playlist(playlist_id, df):
    for index, row in df.iterrows():
        request_url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        body = {"range_start": row["index"], "range_length": 1, "insert_before": index}
        logger.debug(body)
        response = make_put_request(request_url, json.dumps(body))
        df["index"] = df["index"].apply(update_index, args=(row["index"],))


if __name__ == "__main__":
    df = pd.read_json("playlist.json")

    d = []
    for index, row in df.iterrows():
        for genre in row["genres"]:
            temp = dict(row.copy())
            temp.update({"index": index, "genre": str(genre)})
            d.append(temp)
    new_df = pd.DataFrame(d)
    new_df = new_df.sort_values("genre").drop_duplicates(subset=["track_id"]).reset_index()

    reorder_playlist("4ZMt8eMC3Vd1G40g527Msa", new_df)