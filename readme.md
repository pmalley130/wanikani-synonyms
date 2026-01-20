script to add more synonyms to wanikani vocab by doing jmdict lookups

get list of all wanikani vocab

if no index exists
    read dictionary json
    write index pickle where term = wanikani vocab
load pickle

read vocab item
    look up same item in dictionary
    if dictionary definition not in definition, auxiliary meanings, user synonyms
        add to user synonyms

current complete: get list of vocab and study materials
create and load pickle
update study_materials locally with dictionary definitions