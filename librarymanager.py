#!/usr/bin/env python3

#import libraries
import os
import asyncio
from decouple import config
from tmdbv3api import TMDb, Movie, TV, Season
import math
import re
import argparse
import hashlib
import sqlite3

#global flags for command-line arguments
no_ffmpeg = False
delete_old = True
check_db = False
no_hash = False#

#global variable for db connection
db=None

###Function for getting the md5 hash for a file of arbitrary size
def hash_md5(file):
    md5 = hashlib.md5()
    with open(file, "rb") as f: #open the file
        for chunk in iter(lambda: f.read(4096), b""): #read in next 4096 bytes from file
            md5.update(chunk) #add the 4096 bytes to the hash
    return md5.hexdigest() #return the hex version of the hash

###Function for handling tv shows
def process_series(path):
    files = os.listdir(path) #get list of files in directory
    tv = TV() #get the tv show api
    name = path
    season_match = re.search("(?i)series|season", path, re.IGNORECASE) #check directory name for the word season or series
    if season_match != None: #If one is present, get the season number from the directory name
        name = path[:season_match.span()[0]]
        season_number = int(re.search("^[^\d]*(\d+)", path[season_match.span()[1]:]).group(0))
    else: #if 'season' or 'series' aren't present, assume season 1
        season_number=1
    if season_number == None: #catch potential error with regex
        season_number = 1
    show = tv.search(name) #use the TMDb API to search for the shows details
    if not show: #if the show can't be found, let the user know and move on
        print(f"Show '{path}' not found!\n")
        return
    if not no_hash or check_db: #connect to the database if needed
        db = sqlite3.connect("MediaLibrary.db")
    show_season = Season().details(show[0].id, season_number) #get the details of the specific season
    order_of_mag_of_episode_count = math.ceil(math.log(len(files),10)) #this allows us to pad the episode number with the correct amount of leading zeros
    for x in range(0,len(files)): #iterate over the the files
        episode = show_season.episodes[x] #Get the details for each episode
        newfilename = f"({show[0].name}) [S{season_number}E{str(episode.episode_number).zfill(order_of_mag_of_episode_count)}] {episode.name}{files[x][-4:]}"
        print(f"{files[x]} -> {newfilename}") #generate a newfile name using the episode details and show the user
        if not no_ffmpeg: #if running ffmpeg
            ffmpeg_command = f'ffmpeg -loglevel quiet -i "{path}/{files[x]}" -metadata title="{episode.name}" -metadata show="{show[0].name}" -metadata episode_id={episode.episode_number} -c copy -map 0 "{path}/{newfilename}"'
            print(f"Running: {ffmpeg_command}") #generate a command to fill in the correct metadata from the episode info
            os.system(ffmpeg_command) #and run it
            if delete_old and files[x] != newfilename:
                os.remove(f"{path}/{files[x]}") #if deleting old files and it's filename doesn't match the generated one, delete it
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

###Function for handling movies
def process_movie(path):
    movie = Movie()
    results = movie.search(path)
    if not results:
        print(f"Movie {path} not found!")
        return
    movie_file = os.listdir(path)[0]
    newfilename = results[0].title+movie_file[-4:]
    print(f"{movie_file} -> {newfilename}")
    if not no_ffmpeg:
        ffmpeg_command = f'ffmpeg -loglevel quiet -i "{path}/{movie_file}" -metadata title="{results[0].title}" -metadata year="{results[0].release_date[:4]}" -c copy -map 0 "{path}/{newfilename}"'
        print(f"Running: {ffmpeg_command}")
        os.system(ffmpeg_command)
        if delete_old and movie_file != newfilename:
            os.remove(f"{path}/{movie_file}")
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

###Function for determining if a directory is for a tv show or a movie
def check_dir(path):
    print(path) #display current directory for user
    num_of_video_files = 0
    for x in os.walk(path): #iterate over all files in directory 
        for i in x[2]:
            if re.search(".mkv$|.mov$|.wmv$|.mp4$", i): #and count all of the video files
                num_of_video_files += 1
    if num_of_video_files == 0: #if there are no video files, skip directory
        return
    elif num_of_video_files > 1: #if there's more than one, assume it's a tv show
        process_series(path)
    else: #otherwise assume it's a movie
        process_movie(path)
    
    

if __name__ == "__main__": #entry point for script
    #setup the arguments parser and add appropriate flags
    parser = argparse.ArgumentParser(prog='LibraryManager', description='A tool for helping manage large media libraries by renaming media files and adding appropriate metadata!')
    parser.add_argument("dir", help="The directory of the media library to scan")
    parser.add_argument('--hash', metavar='Hash', action='store_const', const=True, default=False, required=False, help="If present, Hashes all media files and stores their hashes to a database")
    parser.add_argument('--check', metavar='Check', action='store_const', const=True, default=False, required=False, help="If present, check file hashes against existing database, will also not hash")
    args = parser.parse_args() #parse the arguments handed to the program
    #set global flags appropriately
    no_ffmpeg = args.hash or args.check #This handles whether or not to run ffmpeg
    delete_old = not no_ffmpeg #This handles whether the old video files should be deleted
    check_db = args.check #This handles whether or not the hashes should be checked against an existing database
    no_hash = check_db or not no_ffmpeg #This handles whether or not the files should be hashed and added to a database
    os.chdir(args.dir) #change the working directory of this script to the media library directory passed into the script
    dirs = [x[0] for x in os.walk('.') if x[0] != '.' and x[0] != '..' and "librarymanager" not in x[0]] #get a list of potential media directories
    if not dirs: #If not directories were found
        print(f"No directories to scan in media library directory {args.dir}!\n")
        os.exit(1)
    if not no_hash: #If the script is supposed to hash the files
        db = sqlite3.connect("MediaLibrary.db") #connect to the database
        cur = db.cursor()
        cur.execute("DROP TABLE IF EXISTS tvhashes") #remove outdated tables
        cur.execute("DROP TABLE IF EXISTS moviehashes")
        db.commit()
        cur.execute("CREATE TABLE tvhashes (filename text, hash text)") #create new tables for this run
        cur.execute("CREATE TABLE moviehashes (filename text, hash text)")
        db.commit()
        db.close()
    tmdb = TMDb() #connect to The Movie Database API
    tmdb.api_key = config('API_KEY')
    for dir in dirs: #iterate over the directories and process them
        check_dir(dir)
