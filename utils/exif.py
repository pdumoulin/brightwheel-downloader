"""Docstring."""

import json
import sys

from PIL import ExifTags
from PIL import Image

filename = sys.argv[1]

# https://exiv2.org/tags.html
with Image.open(filename) as im:
    exif = im.getexif()
    tags = {
        k: {
            ExifTags.TAGS[k]: v
        }
        for k, v in exif.items()
        if k in ExifTags.TAGS
    }
    print(json.dumps(tags, indent=4))
