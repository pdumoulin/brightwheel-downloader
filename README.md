# brightwheel-sync

Download [brightwheel](https://mybrightwheel.com/) activity feed metadata and media about your children.

### Setup

Create virtual env and install requirements.
```
$ python -m venv env
$ source env/bin/activate
$ (env) pip install -r requirements.txt
```

Install [exiftool](https://exiftool.org/) via your favourite package manager. See [exif_notes](https://github.com/pdumoulin/gphotos-uploader/tree/main/exif_notes) for details about why. If you don't want to set exif data, use the `-s` flag when downloading media.

### Download Activities Metadata

Authenticate with API and download metadata into sqlite database.

```
usage: download.py metadata [-h] --login LOGIN --student STUDENT [--start-date START_DATE] [--end-date END_DATE] [-n] [-l] [-f]

optional arguments:
  -h, --help            show this help message and exit
  --login LOGIN         guardian login to API (default: None)
  --student STUDENT     student name substring to select (default: None)
  --start-date START_DATE
                        UTC start date window to query YYYY-MM-DD default: today (default: None)
  --end-date END_DATE   UTC end date window to query YYYY-MM-DD (inclusive) (default: None)
  -n                    do not allow interactive login (default: False)
  -l                    ignore stored auth (default: False)
  -f                    clear all data for student before saving again (default: False)
```

### Process Activities

Process previously downloaded activities from sqlite database. 

Currently, downloading images in the only feature.

:bulb: Date created exif data compatible with Google Photos automatically added.

```
usage: download.py media [-h] [--dl-dir DL_DIR] [-s] [-f] [--lat LAT] [--lon LON]

optional arguments:
  -h, --help       show this help message and exit
  --dl-dir DL_DIR  directory to download media into (default: /home/pi/projects/brightwheel-downloader/media)
  -s               skip setting exif tags via exiftool (default: False)
  -f               download even if file already exists (default: False)
  --lat LAT        Latitude metadata to add, used for timezone offsetting (default: None)
  --lon LON        Longitude metadata to add, used for timezone offsetting (default: None)
```

:bulb: Google Photos for Android mixes all your albums together and ignores timezone data. Set `--lat` and `--lon` to set timezone.

### Auto Sync with Google Photos

* https://photos.google.com/apps
* https://github.com/pdumoulin/gphotos-uploader
