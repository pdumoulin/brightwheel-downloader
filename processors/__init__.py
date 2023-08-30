"""Media processor classes."""

import glob
import os
import shlex
import subprocess
from datetime import datetime

import pytz

import requests

from timezonefinder import TimezoneFinder


class BaseProcessor(object):
    """Abstract class for processors."""

    def __init__(self):
        """Create new instance."""
        raise NotImplementedError()

    def set_tags(self, filename, event_datetime, lat_lon):
        """Add tags to file.

        Args:
            filename (str): file on disk to edit
            event_datetime (datetime): media create time
            lat_lon (tuple): latitude and longiture media created at
        """
        raise NotImplementedError()

    def media_filename(self, download_dir, media_url, event_datetime):
        """Determine filename from directory and metadata.

        Args:
            download_dir (str): directory media will be saved into
            media_url (str): url media will be downloaded from
            event_datetime (datetime): media create time
        """
        raise NotImplementedError()

    def get_url(self, event):
        """Extract url from activity.

        Args:
            event (object): full activity data
        """
        raise NotImplementedError()

    def process(
        self,
        download_dir, raw_data,
        write_tags=False, force_dl=False,
        latitude=None, longitude=None
    ):
        """Download and tag media.

        Args:
            download_dir (str): directory to save media into
            raw_data (object): full activity data
            write_tags (bool): save metadat tags into media file
            force_dl (bool): download if file already exists
            latitude (float): latitude where media was created
            longitude (float): longitude where media was created

        Returns:
            processed (bool): if media was extracted from activity
            downloaded (bool): if media was downloaded
            tagged (bool): if metadata tags were added to media
        """
        processed = False
        downloaded = False
        tagged = False

        media_url = self.get_url(raw_data)
        if media_url:
            event_datetime = datetime.strptime(
                raw_data['event_date'],
                '%Y-%m-%dT%H:%M:%S.%f%z'
            )
            media_filename = self.media_filename(
                download_dir,
                media_url,
                event_datetime
            )

            if not glob.glob(f'{media_filename}*') or force_dl:
                media_filename = self.download(media_url, media_filename)
                downloaded = True

            if write_tags:
                try:
                    self.set_tags(
                        media_filename,
                        event_datetime,
                        (latitude, longitude)
                    )
                    tagged = True
                except Exception as e:
                    os.remove(media_filename)
                    raise e
            processed = True
        return (processed, downloaded, tagged)

    def download(self, url, filename):
        """Save media to disk.

        Args:
            url (str): URL of media
            filename (str): file to download media into

        Raises:
            requests.exceptions.HTTPError
        """
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=16*1024):
                f.write(chunk)
        return self.repair_extension(response, filename)

    def repair_extension(self, response, old_filename):
        """Determine extension if not set already.

        Args:
            response (requests.response): HTTP response
            old_filename (str): filename containing response body

        Returns:
            str: new filename

        Raises
            exception
        """
        (split_filename, split_extension) = os.path.splitext(old_filename)
        if not split_extension:
            try:
                content_type = response.headers['Content-Type']
            except IndexError:
                raise Exception('Header not in response')
            try:
                extension = content_type.split('/')[1]
            except IndexError:
                raise Exception('Invalid header in response')
            if extension == 'jpeg':
                extension = 'jpg'
            new_filename = f'{split_filename}.{extension}'
            os.rename(old_filename, new_filename)
            return new_filename
        return old_filename

    def write_tags(self, filename, tags):
        """Write exif tags using exiftool.

        Args:
            filename (str): file to set tags on
            tags (list[tuple]): tag name + value pairs

        https://github.com/pdumoulin/gphotos-uploader/tree/main/exif_notes
        """
        tag_flags = ' '.join([
            f"-{x[0]}='{x[1]}'"
            for x in tags
        ])
        command = f'exiftool {tag_flags} -overwrite_original {filename}'
        subprocess.run(
            shlex.split(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            check=True
        )


class ImageProcessor(BaseProcessor):
    """Download and tag image from activity."""

    def __init__(self):
        """Create new instance."""
        pass

    def set_tags(self, filename, event_datetime, lat_lon):
        """See base class docstring."""
        tags = []

        # TODO - why does GPhotos not respect for PNG?
        # are the tags being set correctly in that case?

        if all(lat_lon):

            # localize timestamp based on gps data
            tf = TimezoneFinder()
            created_datetime = datetime.fromtimestamp(
                event_datetime.timestamp(),
                tz=pytz.timezone(
                    tf.timezone_at(lat=lat_lon[0], lng=lat_lon[1])
                )
            )

            # add gps data tags
            lat_hemi = 'S' if lat_lon[0] < 0 else 'N'
            lon_hemi = 'W' if lat_lon[1] < 0 else 'E'
            tags += [
                ('gpslatitude', lat_lon[0]),
                ('gpslongitude', lat_lon[1]),
                ('gpslatituderef', lat_hemi),
                ('gpslongituderef', lon_hemi)
            ]

        # add datetime and tz offset tags
        dt_str = datetime.strftime(created_datetime, '%Y:%m:%d %H:%M:%S')
        tz_str = datetime.strftime(created_datetime, '%z')
        tz_str = tz_str[:3] + ':' + tz_str[3:]
        tags += [
            ('ModifyDate', dt_str),
            ('OffsetTimeDigitized', tz_str)
        ]
        self.write_tags(filename, tags)

    def media_filename(self, download_dir, media_url, event_datetime):
        """See base class docstring."""
        file_id = None
        media_url = media_url.split('?')[0]
        url_parts = media_url.split('/')
        if media_url.endswith('jpg'):
            file_id = url_parts[-1]
        elif url_parts[-1] == 'data-media':
            file_id = url_parts[-2]
        else:
            raise Exception(f'Unexpected media_url format {media_url}')
        return os.path.join(
            download_dir,
            datetime.strftime(
                event_datetime,
                '%Y%m%d%H%M%SZ'
            ) + file_id
        )

    def get_url(self, event):
        """See base class docstring."""
        try:
            return event.get('media', {}).get('image_url')
        except AttributeError:
            pass
        return None


class VideoProcessor(BaseProcessor):
    """Download and tag video from activity."""

    def __init__(self):
        """Create new instance."""
        pass

    def set_tags(self, filename, event_datetime, lat_lon):
        """See base class docstring."""
        tags = []
        if all(lat_lon):

            # add gps tag
            tags.append(
                (
                    'Keys:GPSCoordinates',
                    f'{lat_lon[0]:.4f}, {lat_lon[1]:.4f}, 0'
                )
            )

        # add datetime tag (timezone not supported, gps is used for that)
        dt_str = datetime.strftime(event_datetime, '%Y:%m:%d %H:%M:%S')
        tags.append(('CreateDate', dt_str))
        self.write_tags(filename, tags)

    def media_filename(self, download_dir, media_url, event_datetime):
        """See base class docstring."""
        media_url = media_url.split('?')[0]
        video_uuid = media_url.split('/')[-2].replace('-', '')
        video_ext = media_url.split('/')[-1].split('.')[-1]
        return os.path.join(
            download_dir,
            datetime.strftime(
                event_datetime,
                '%Y%m%d%H%M%SZ'
            ) + video_uuid + '.' + video_ext
        )

    def get_url(self, event):
        """See base class docstring."""
        try:
            return event.get('video_info', {}).get('downloadable_url')
        except AttributeError:
            pass
        return None
