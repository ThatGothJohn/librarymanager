#!/usr/bin/env python3

import os
import asyncio
from decouple import config
from tmdbv3api import TMDb, Movie, TV, Season
import math
import re
import argparse
import hashlib
import sqlite3

no_ffmpeg = False
delete_old = True
check_db = False
no_hash = False
db=None

def hash_md5(file):
    md5 = hashlib.md5()
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()

def process_series(path):
    files = os.listdir(path)
    tv = TV()
    name = path
    season_match = re.search("(?i)series|season", path, re.IGNORECASE)
    if season_match != None:
        name = path[:season_match.span()[0]]
        season_number = int(re.search("^[^\d]*(\d+)", path[season_match.span()[1]:]).group(0))
    else:
        season_number=1
    if season_number == None:
        season_number = 1
    show = tv.search(name)
    if not show:
        print(f"Show '{path}' not found!\n")
        return
    if not no_hash or check_db:
        db = sqlite3.connect("MediaLibrary.db")
    show_season = Season().details(show[0].id, season_number)
    order_of_mag_of_episode_count = math.ceil(math.log(len(files),10)) #this allows us to pad the episode number with the correct amount of leading zeros
    for x in range(0,len(files)):
        episode = show_season.episodes[x]
        newfilename = f"({show[0].name}) [S{season_number}E{str(episode.episode_number).zfill(order_of_mag_of_episode_count)}] {episode.name}{files[x][-4:]}"
        print(f"{files[x]} -> {newfilename}")
        if check_db:
            print(f"Checking hash for {files[x]}")
            file_hash = hash_md5(os.getcwd()+"/"+path[2:]+"/"+files[x])
            cur = db.cursor()
            sql = f'SELECT hash from tvhashes WHERE filename = "{files[x]}"'
            cur.execute(sql)
            if file_hash != cur.fetchall()[0][0]:
                print(f"\n\n{files[x]} failed hash check!\n\n")
            else:
                print(f"\t{files[x]} passed hash check!")
        if not no_ffmpeg:
            ffmpeg_command = f'ffmpeg -loglevel quiet -i "{path}/{files[x]}" -metadata title="{episode.name}" -metadata show="{show[0].name}" -metadata episode_id={episode.episode_number} -c copy -map 0 "{path}/{newfilename}"'
            print(f"Running: {ffmpeg_command}")
            os.system(ffmpeg_command)
            if delete_old:
                os.remove(f"{path}/{files[x]}")
        if not no_hash:
            print(f"Hashing {files[x]}")
            file_hash = hash_md5(os.getcwd()+"/"+path[2:]+"/"+files[x])
            cur = db.cursor()
            sql = f"INSERT INTO tvhashes(filename,hash) VALUES(?,?)"            
            if no_ffmpeg:
                cur.execute(sql, (files[x], file_hash))
            else:
                cur.execute(sql, (newfilename, file_hash))
            db.commit()
    if not no_hash or check_db:
        db.close()

def process_movie(path):
    movie = Movie()
    results = movie.search(path)
    if not results:
        print(f"Movie {path} not found!")
        return
    movie_file = os.listdir(path)[0]
    newfilename = results[0].title+movie_file[-4:]
    print(f"{movie_file} -> {newfilename}")
    if check_db:
        db = sqlite3.connect("MediaLibrary.db")
        print(f"Checking hash for {movie_file}")
        file_hash = hash_md5(os.getcwd()+"/"+path[2:]+"/"+movie_file)
        cur = db.cursor()
        sql = f'SELECT hash from moviehashes WHERE filename = "{movie_file}"'
        cur.execute(sql)
        if file_hash != cur.fetchall()[0][0]:
            print(f"\n\n{movie_file} failed hash check!\n\n")
        else:
            print(f"\t{movie_file} passed hash check!")
        db.close()
    if not no_ffmpeg:
        ffmpeg_command = f'ffmpeg -loglevel quiet -i "{path}/{movie_file}" -metadata title="{results[0].title}" -metadata year="{results[0].release_date[:4]}" -c copy -map 0 "{path}/{newfilename}"'
        print(f"Running: {ffmpeg_command}")
        os.system(ffmpeg_command)
        if delete_old:
            os.remove(f"{path}/{movie_file}")
    if not no_hash:
            db = sqlite3.connect("MediaLibrary.db")
            print(f"Hashing {movie_file}")
            file_hash = hash_md5(os.getcwd()+"/"+path[2:]+"/"+movie_file)
            cur = db.cursor()
            sql = f"INSERT INTO moviehashes(filename,hash) VALUES(?,?)"            
            if no_ffmpeg:
                cur.execute(sql, (movie_file, file_hash))
            else:
                cur.execute(sql, (newfilename, file_hash))
            db.commit()
            db.close()

def check_dir(path):
    files = os.listdir(path)
    print(path)
    num_of_video_files = 0
    for x in os.walk(path):
        for i in x[2]:
            if re.search(".mkv$|.mov$|.wmv$|.mp4$", i):
                num_of_video_files += 1
    tmdb = TMDb()
    tmdb.api_key = config('API_KEY')
    if num_of_video_files > 1:
        process_series(path)
    else:
        process_movie(path)
    
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='LibraryManager', description='A tool for helping manage large media libraries by renaming media files and adding appropriate metadata!')
    parser.add_argument("dir", help="The directory of the media library to scan")
    parser.add_argument('--hash', metavar='Hash', action='store_const', const=True, default=False, required=False, help="If present, Hashes all media files and stores their hashes to a database")
    parser.add_argument('--check', metavar='Check', action='store_const', const=True, default=False, required=False, help="If present, check file hashes against existing database, will also not hash")
    args = parser.parse_args()
    no_ffmpeg = args.hash or args.check
    delete_old = not no_ffmpeg 
    check_db = args.check
    no_hash = check_db or not no_ffmpeg
    os.chdir(args.dir)
    dirs = [x[0] for x in os.walk('.') if x[0] != '.' and x[0] != '..' and "librarymanager" not in x[0]]
    
    if not dirs:
        print(f"No directories to scan in media library directory {args.dir}!\n")
        os.exit(1)
    if not no_hash:
        db = sqlite3.connect("MediaLibrary.db")
        cur = db.cursor()
        cur.execute("DROP TABLE IF EXISTS tvhashes")
        cur.execute("DROP TABLE IF EXISTS moviehashes")
        db.commit()
        cur.execute("CREATE TABLE tvhashes (filename text, hash text)")
        cur.execute("CREATE TABLE moviehashes (filename text, hash text)")
        db.commit()
        db.close()
    for dir in dirs:
        check_dir(dir)
    if not no_ffmpeg:
        print("NOTE: Important due to a bug in the current version, don't run this command with no flags more than once!")


