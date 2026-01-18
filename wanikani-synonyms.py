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
def get_vocab(levels: str) -> list[dict]:
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
    vocab = [] #empty array of vocab to be returned

    #if it's over 1000 entries it paginates, so need a loop
    while url:
        response = requests.get(url, headers=headers,params=params).json()

        #extract vocab from response
        for item in response.get("data",[]):
            id = item.get("id")
            char = item.get("data",{}).get("characters")
            if id is not None and char:
                vocab.append({
                    "id":id,
                    "characters": char
                })

        #follow pagination due to 1000 api limit
        url = response.get("pages", {}).get("next_url")

    return vocab

#generate a lookup index that just holds the jp word and english defs from jmdict
def generate_index(vocab: list[dict]):
    #set of wanikani vocab terms
    vocab_terms = {item["characters"] for item in vocab if item.get("characters")}

    #open dictionary file
    with open(DICT_PATH, encoding="utf-8") as f:
        data = json.load(f)

    #save just the words array
    words = data["words"]

    #index of 日本語 -> 英語
    index = defaultdict(list)

    #walk through each dictionary entry
    for entry in words:
        terms = []
        
        #check to see if entry is in vocab list, if it is, add to terms
        kanji_list = entry.get("kanji",[])
        if kanji_list:
            for k in kanji_list:
                text = k.get("text")
                if text and text in vocab_terms:
                    terms.append(text)
        else: #entries that are just kana (like あっさり) don't have a "kanji" entry but we still want them
            for k in entry.get("kana",[]):
                text = k.get("text")
                if text and text in vocab_terms:
                    terms.append(text)

        if not terms:
            continue

        #term is in list, now save definitions ("gloss" in jmdict)
        glosses = []
        for sense in entry.get("sense",[]):
           for gloss in sense.get("gloss",[]):
               text = gloss.get("text")
               if text:
                   glosses.append(text)

        if not glosses:
           continue

        #dedupe definitions within this entry
        unique_glosses = []
        seen_gloss = set()
        for g in glosses:
            if g not in seen_gloss:
                seen_gloss.add(g)
                unique_glosses.append(g)

        #save term to index
        for term in set(terms):
            print(f"adding {term}")
            index[term].extend(unique_glosses)
    
    #dedupe terms
    for term, defs in index.items():
        seen = set()
        unique = []
        for d in defs:
            if d not in seen:
                seen.add(d)
                unique.append(d)
                if len(unique) == 5: #some common things like "上げる" have roughly one septillion possible definitions, so I've set an arbitrary cap
                    break
        index[term] = unique

    #add definition to original vocab list
    for item in vocab:
        term = item.get("characters")
        if term in index:
            item["definitions"] = index[term]
    
    #save the vocab list for later loading
    with open(INDEX_PATH, "wb") as f:
        pickle.dump(vocab, f, protocol=pickle.HIGHEST_PROTOCOL)

if not os.path.isfile(INDEX_PATH):
    levels = input("Which levels? (enter as a comma separated string, no spaces) ")
    vocab = get_vocab(levels)
    generate_index(vocab)

with open(INDEX_PATH, "rb") as f:
    index = pickle.load(f)

print(json.dumps(index,indent=3,ensure_ascii=False))

