# librarymanager
A Python script designed to automatically rename and edit the metadata of large media libraries, allowing for easier management of your movies and tv shows, as well as build a database of hashes of all of your media to ensure data integrity

# Dependancies
* ffmpeg
## pip packages:
* python-decouple
* tmdbv3api
* regex
* argparse
* hashlib
* sqlite3

# Setup
* Create a .env file in the same directory as the python file
* Add the line ```API_KEY='Your TMDb API Key'```

## Current limitations
* Requires movie folders to be named the name of the movie and only contain the movies video file
* Requires tv show folders to be named the name of the show and include either "season" or "series" (case-insensitive) followed by the season number excluding season 1's

# How to use
* Run ```librarymanager.py <media directory>```

If you are wanting to take advantage of the hashing functionality run: ```librarymanager.py --hash <media directory>``` to build a database of hashes of all of your media files

To check the integrity of your media files against the database run: ```librarymanager.py --check <media directory>```
