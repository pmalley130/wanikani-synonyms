# WaniKani Synonym Enricher

This script enriches your WaniKani vocabulary items by adding extra English synonyms sourced from a local JMdict JP->EN dictionary. [Dictionaries available here](https://github.com/scriptin/jmdict-simplified/releases).

### What It Does

- Fetches vocabulary terms (per level) and your existing User Synonyms from the WaniKani API
- Matches additional dictionary definitions from a local JMdict JSON file
- Adds missing dictionary definitions per vocab term
- Avoids duplicates and stays under the WaniKani synonym limit (8 synonyms)
- Lets you review changes in `output.json` before applying them
- Pushes updates to WaniKani once updates are confirmed


## Requirements

### Environment Variables

Set the following in a `.env` file or your system environment:

```
WANIKANI_API_KEY=<your_api_key>
DICT_PATH=/path/to/jmdict.json
```

### Dependencies

Install with:

```
pip install requests python-dotenv rich
or
pip install -r requirements.txt
```

---

## Usage

Run the script:

```
python wanikani-synonyms.py
```

You will be prompted for levels:

```
Which levels? (enter as a comma separated string, no spaces, blank for every level)
```

Examples:

- `3` → level 3 only  
- `1,2,3` → levels 1, 2, and 3  
- (blank) → all levels  

Workflow:

1. Script builds JP->EN mappings
2. Writes proposed changes to `output.json`
3. Prompts for confirmation before pushing
4. Updates WaniKani via API (irreversible)

## Rate Limiting

The script detects WaniKani API rate headers and automatically waits when necessary. This makes large updates safe, but slow depending on how many changes you apply.


## Disclaimer

- All updates are performed **against your live WaniKani account**
- Synonym updates are **irreversible** 
- Always inspect `output.json` before confirming