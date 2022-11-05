# brightwheel-sync

Download [brightwheel](https://mybrightwheel.com/) activity feed metadata and media about your children.

### Setup

Create virtual env and install requirements.
```
$ python -m venv env
$ source env/bin/activate
$ (env) pip install -r requirements.txt
```

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
usage: download.py media [-h] [--dl-dir DL_DIR]

optional arguments:
  -h, --help       show this help message and exit
  --dl-dir DL_DIR  directory to download media into (default: ./media)
```

### Utils

Output exif photo data for debugging purposes.
```
$ (env) python utils/exif.py <path-to-image-file>
```

### Auto Sync with Google Photos

* https://photos.google.com/apps
* https://github.com/pdumoulin/gphotos-uploader
