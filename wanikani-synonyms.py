import json
import pickle
from collections import defaultdict
import requests

import os
from dotenv import load_dotenv

load_dotenv()

DICT_PATH = os.getenv("DICT_PATH")
INDEX_PATH = os.getenv("INDEX_PATH")

#get the vocab of specific levels
def get_vocab(levels: str) -> list[str]:
    #build url for request
    API_KEY = os.getenv("WANIKANI_API_KEY") 
    base_url = "https://api.wanikani.com/v2/subjects"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Wanikani-Revision": "20170710"
    }
    params = {
        "types":"vocabulary"
    }

    #only add levels if user passed in specific level, otherwise a blank "levels" returns nothing from api
    if levels:
        params["levels"] = levels

    url = base_url
    characters = [] #empty array of vocab to be returned

    #if it's over 1000 entries it paginates, so need a loop
    while url:
        response = requests.get(url, headers=headers,params=params).json()

        #extract vocab from response
        for item in response.get("data",[]):
            char = item.get("data",{}).get("characters")
            if char:
                characters.append(char)

        #follow pagination due to 1000 api limit
        url = response.get("pages", {}).get("next_url")

    return characters

#generate a lookup index that just holds the jp word and english defs from jmdict
def generate_index():
    #open dictionary file
    with open(DICT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    #save just the words array
    words = data["words"]

    #index of 日本語 -> 英語
    index = defaultdict(list)

    #walk through each entry
    for entry in words:
       #collect all english definitions ("glosses in jmdict") for entry
        glosses = []
        for sense in entry.get("sense",[]):
           for gloss in sense.get("gloss",[]):
               txt = gloss.get("text")
               if txt:
                   glosses.append(txt)

        if not glosses:
           continue

        #attach to 日本語 term(s)
        for k in entry.get("kanji",[]):
            term = k.get("text")
            if term:
                index[term].extend(glosses)

        #entries that are just kana (like あっさり) don't have a "kanji" entry but we still want them
        #so index their kana instead
        if not entry.get("kanji"):
            for k in entry.get("kana",[]):
                term = k.get("text")
                if term:
                    index[term].extend(glosses)

        #dedupe definitions
        for term, defs in index.items():
            seen = set()
            unique = []
            for d in defs:
                if d not in seen:
                    seen.add(d)
                    unique.append(d)
            index[term] = unique
            print(f"adding {term}")
    
    #save the index for later loading
    with open(INDEX_PATH, "wb") as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)

levels = input("Which levels? (enter as a comma separated string, no spaces)")
vocab = get_vocab(levels)
print(vocab)