import json
import pickle
from collections import defaultdict
import requests
import time

from rich.progress import track

import os
from dotenv import load_dotenv

load_dotenv()

DICT_PATH = os.getenv("DICT_PATH")
API_KEY = os.getenv("WANIKANI_API_KEY")

#subject API doesn't map study materials, so we should get them beforehand to manually map
def get_study_materials() -> list[dict]:
    base_url = "https://api.wanikani.com/v2/study_materials"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Wanikani-Revision": "20170710"
    }
    params = {
        "subject_types": "vocabulary,kana_vocabulary"
    }

    url = base_url
    study_map = [] #empty array to hold subject_id:study_material
    #if there's more than 1000 entries it paginates, so loop
    while url:
        response = requests.get(url,headers=headers,params=params).json()
        
        #add entries
        for item in response.get("data",[]):
            study_map.append({
                "subject_id": item.get("data").get("subject_id"),
                "study_material_id": item.get("id"),
                "meaning_synonyms": item.get("data").get("meaning_synonyms"),
            })

        #follow pagination due to 1000 api limit
        url = response.get("pages", {}).get("next_url")

    return study_map

#get the vocab of specific levels
def get_vocab(levels: str, study_map: list[dict]) -> list[dict]:
    #build url for request
    base_url = "https://api.wanikani.com/v2/subjects"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Wanikani-Revision": "20170710"
    }
    params = {
        "types":"vocabulary,kana_vocabulary"
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
                #walk through study materials (should use a map here but the list is so small we don't mind the performance hit for now)
                study_material_id = None
                study_material_definitions = None
                for study_material in study_map:
                    #if there's a matching study material for this subject, add it to dict
                    if study_material.get("subject_id") == id:
                        study_material_id = study_material.get("study_material_id"),
                        study_material_definitions = study_material.get("meaning_synonyms")
                        break
                
                #collect the wanikani definitions
                wanikani_definitions = []
                data = item.get("data",{})
                meanings = [m["meaning"] for m in data.get("meanings",[]) if m["accepted_answer"]]
                auxiliary_meanings = [m["meaning"] for m in data.get("auxiliary_meanings",[]) if m["type"] == "whitelist"]
                wanikani_definitions = meanings + auxiliary_meanings

                #add to list
                vocab.append({
                    "id":id,
                    "term": char,
                    "study_material_id": study_material_id,
                    "study_material_definitions": study_material_definitions,
                    "wanikani_definitions": wanikani_definitions
                })

        #follow pagination due to 1000 api limit
        url = response.get("pages", {}).get("next_url")

    return vocab

#generate a lookup index to map the jp word and english defs from jmdict
def generate_index(vocab: list[dict]) -> list[dict]:
    #set of wanikani vocab terms
    vocab_terms = {item["term"] for item in vocab if item.get("term")}

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

        #skip to next entry if there's somehow no definitions
        if not glosses:
           continue

        #dedupe definitions within this entry
        unique_glosses = []
        seen_gloss = set()
        for g in glosses:
            if g not in seen_gloss:
                if len(g) > 64: #wanikani has a 64 character max for definition
                    continue
                seen_gloss.add(g)
                unique_glosses.append(g)

        #save term to index
        for term in set(terms):
            print(f"adding {term} definitions to local index")
            index[term].extend(unique_glosses)
    
    #dedupe terms
    for term, defs in index.items():
        seen = set()
        unique = []
        for d in defs:
            if d not in seen:
                seen.add(d)
                unique.append(d)
                if len(unique) == 5: 
                    break
        index[term] = unique

    #add definition to original vocab list
    for item in vocab:
        term = item.get("term")
        if term in index:
            item["dictionary_definitions"] = index[term]
    
    return vocab

#check existing wanikani definitions (and user synonyms) against dictionary definitions to add more user synonyms
def update_definitions(index:list[dict]) -> list[dict]:
    for entry in index:
        #can't iterate over None, have to make it empty list instead
        if entry.get("study_material_definitions") is None:
            entry["study_material_definitions"] = []
        
        #normalize case
        wani_defs = {w.lower() for w in entry.get("wanikani_definitions",[])}
        synonyms = {s.lower() for s in entry.get("study_material_definitions",[])}

        additions = [] #for tracking to see if we need to update on wanikani

        #walk through dictionary defs and add if not already represented
        for definition in entry.get("dictionary_definitions",[]):
            #API allows a max of 8 user synonyms, break the loop early if we're there
            if len(entry["study_material_definitions"]) >= 8:
                break
            
            if definition.lower() not in wani_defs and definition.lower() not in synonyms:
                entry["study_material_definitions"].append(definition)
                synonyms.add(definition.lower())
                additions.append(definition.lower())
    
        entry["update_wanikani"] = bool(additions) #create boolean flag for updating wanikani
    return index

def sleep_with_countdown(wait):
    for _ in track(range(wait), description="Waiting..."):
        time.sleep(1)

#API has a strict limit, this slows down based on limits in headers
def wanikani_request(method, url, headers=None, json=None):
    #make the request
    response = requests.request(method, url, headers=headers, json=json)

    #parse rate limit headers
    remaining = response.headers.get("RateLimit-Remaining")
    reset_ts = response.headers.get("RateLimit-Reset")

    try:
        remaining = int(remaining) if remaining is not None else None
    except ValueError:
        remaining = None
    try:
        reset_ts = int(reset_ts) if reset_ts is not None else None
    except ValueError:
        reset_ts = None
    
    #if we're out of remaining tries, sleep until reset
    if remaining == 0 and reset_ts:
        now = int(time.time())
        wait = max(1, reset_ts - now)
        print(f"Rate limit reached, {wait} seconds until reset.")
        sleep_with_countdown(wait)
        #retry
        response = requests.request(method, url, headers=headers, json=json)

    #429 handling just in case the sleep doesn't work
    if response.status_code == 429:
        reset_ts = response.headers.get("RateLimit-Reset")
        if reset_ts:
            try:
                reset_ts = int(reset_ts)
                now = int(time.time())
                wait = max(1, reset_ts - now)
                print(f"Sleeping {wait} seconds due to 429")
                sleep_with_countdown(wait)
                response = requests.request(method,url,headers=headers,json=json)
            except ValueError:
                #give up and wait a full minute
                print("Bad reset timestamp, sleeping 60s")
                time.sleep(60)
                response = requests.request(method,url,headers=headers,json=json)
        else:
            print("No reset header on code 429, sleeping 60s")
            sleep_with_countdown(wait)
            response = requests.request(method,url,headers=headers,json=json)

    return response


#push new definitions to the API
def push_updates(index:list[dict]):
    headers = {
        "Wanikani-Revision": "20170710",
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {API_KEY}",
    }

    for entry in index:
        #skip this entry if updating isn't needed
        if entry.get("update_wanikani") == False:
            print(f"Skipping {entry.get('term')}, no update needed on WaniKani")
            continue
        
        #payload is the same regardless if PUSH or POST      
        payload = {
            "study_material": {
                "subject_id": entry.get("id"),
                "meaning_synonyms": entry.get("study_material_definitions")
            }
        }

        #if there's no study material, we use POST and generic endpoint
        if not entry.get("study_material_id"):
            #print(f"{entry.get('term')} has no study material, using POST")
            url = "https://api.wanikani.com/v2/study_materials/"        
            response = wanikani_request("POST",url,headers=headers,json=payload)
        
        #if study material already exists, we add to it with PUT
        if entry.get("study_material_id"):
            #print(f"{entry.get('term')} has study material {entry.get('study_material_id')}, using PUT")
            url = f"https://api.wanikani.com/v2/study_materials/{entry.get('study_material_id')[0]}"
            #print(url)
            response = wanikani_request("PUT",url,headers=headers,json=payload)

        if response.status_code in (200,201):
            print(f"Successfully updated {entry.get('term')} on WaniKani") 
        else:
            print(f"Error updating {entry.get('term')}:", response.status_code)
            print(response.text)


if __name__ == "__main__":
    levels = input("Which levels? (enter as a comma separated string, no spaces, blank for every level) ")
    
    print("Retrieving existing user synonyms")
    study_materials = get_study_materials()
    
    print("Retrieving vocabulary items")
    vocab = get_vocab(levels,study_materials)
    
    print("Building JP->EN mappings")
    index = generate_index(vocab)
    
    print("Updating definitions")
    index = update_definitions(index)
    
    with open("output.json", "w",encoding="utf-8") as f:
        print("Writing new dictionary to output.json")
        json.dump(index,f,indent=4,ensure_ascii=False)

    answer = input("Please review output.json for changes before continuing, changes are irreversible \nProceed? (y/n): ").lower().strip() in ('y', 'yes', 'true', '1')
    if answer:
        push_updates(index)

