"""CLI to download activity metadata and media."""

import argparse
import io
import json
import os
from datetime import datetime

from PIL import Image

from brightwheel import Client

from database import DB

import requests


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


def main():
    """Entrypoint."""
    default_app_data_filename = os.path.join(SCRIPT_DIR, 'database/.app_data')
    default_media_dir = os.path.join(SCRIPT_DIR, 'media')

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--app-data',
        default=default_app_data_filename,
        help='filename to store app data in sqlite'
    )

    subparser = parser.add_subparsers(dest='command')

    # parser options for saving activity feed metadata
    metadata_subparser = subparser.add_parser(
        'metadata',
        help='download metadata from activity feed',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    metadata_subparser.add_argument(
        '--login',
        required=True,
        help='guardian login to API'
    )
    metadata_subparser.add_argument(
        '--student',
        required=True,
        help='student name substring to select'
    )
    metadata_subparser.add_argument(
        '--start-date',
        required=False,
        type=lambda d: datetime.strptime(d, '%Y-%m-%d'),
        help='UTC start date window to query YYYY-MM-DD default: today'
    )
    metadata_subparser.add_argument(
        '--end-date',
        required=False,
        type=lambda d: datetime.strptime(d, '%Y-%m-%d'),
        help='UTC end date window to query YYYY-MM-DD (inclusive)'
    )
    metadata_subparser.add_argument(
        '-n',
        action='store_true',
        help='do not allow interactive login'
    )
    metadata_subparser.add_argument(
        '-l',
        action='store_true',
        help='ignore stored auth'
    )
    metadata_subparser.add_argument(
        '-f',
        action='store_true',
        help='clear all data for student before saving again'
    )
    metadata_subparser.set_defaults(func=dl_metadata)

    # parser options for downloading media
    media_subparser = subparser.add_parser(
        'media',
        help='download media based on cached metadata',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    media_subparser.add_argument(
        '--dl-dir',
        default=default_media_dir,
        help='directory to download media into'
    )
    media_subparser.set_defaults(func=dl_media)

    # parse and save args
    args = parser.parse_args()

    # call func related to command
    if 'func' not in args:
        parser.print_help()
        exit(1)

    db = DB(args.app_data)

    args.func(args, db)


def dl_metadata(args, db):
    """Download metadata into db."""
    login = args.login
    student = args.student
    start_date = args.start_date
    end_date = args.end_date
    headless = args.n
    clear_events = args.f
    force_login = args.l

    # initialize and authenticate client
    stored_auth = db.select_cookie(login)
    client = Client(
        login,
        auth=stored_auth,
        headless=headless,
        force_login=force_login
    )
    if not stored_auth:
        db.insert_cookie(
            login,
            client.session_auth()
        )

    # get uuid for student
    student_id = fetch_student_id(client, student)

    # remove cached data for student
    if clear_events:
        db.delete_activities(student_id)

    # default to today
    if not start_date:
        start_date = datetime.today().strftime('%Y-%m-%d')

    # load activies metadata with images into app data
    save_metadata(client, db, student_id, start_date, end_date)


def save_metadata(client, db, student_id, start_date, end_date):
    """Insert metadata into db.

    Args:
        client (brightwheel.Client): API client
        db (database.DB): sqlite interface
        student_id (str): UUID for student
        start_date (str): YYYY-MM-DD fetch data after
        end_date (str): YYYY-MM-DD fetch data before (inclusive)

    Returns:
        None
    """
    page = 0
    page_size = 25
    result_count = 0
    new_count = 0
    skip_count = 0
    while True:
        print(f'Fetching activities page={page}...')
        batch = client.get_students_activities(
            student_id,
            start_date=start_date,
            end_date=end_date,
            page=page,
            page_size=page_size
        )['activities']
        for activity in batch:

            # skip activities with video still being processed
            video_info = activity['video_info']
            if video_info:
                if video_info['transcoding_status'] != 'complete':
                    skip_count += 1
                    continue

            added = db.insert_activity(student_id, activity)
            if added:
                new_count += 1
        result_count += len(batch)
        if len(batch) < page_size:
            break
        page += 1
    print(f'Not Ready {skip_count}')
    print(f'Added     {new_count}')
    print(f'Total     {result_count}')


def dl_media(args, db):
    """Download media based on unprocessed data in db."""
    base_download_dir = args.dl_dir

    # copy events to avoid modify while iterating
    activities = db.select_activities()
    dl_count = 0

    # iterate over each student's data
    for activity in activities:
        activity_id = activity['id']
        student_id = activity['student_id']
        raw_data = json.loads(activity['json'])

        # setup download image dir scoped by student
        download_dir = os.path.join(base_download_dir, student_id)
        if not os.path.isdir(download_dir):
            os.makedirs(download_dir)

        # convert from str to datetime
        event_datetime = datetime.strptime(
            raw_data['event_date'],
            '%Y-%m-%dT%H:%M:%S.%f%z'
        )

        # images
        media = raw_data['media']
        if media:
            image_url = media.get('image_url')
            if image_url:

                # calculate filename
                download_filename = os.path.join(
                    download_dir,
                    datetime.strftime(
                        event_datetime,
                        '%Y%m%d%H%M%SZ'
                    ) + image_url.split('/')[-1].split('?')[0]
                )
                download_image(
                    image_url,
                    download_filename,
                    event_datetime
                )
                dl_count += 1

        # videos
        video_info = raw_data['video_info']
        if video_info:

            video_url = video_info.get('downloadable_url')
            if video_url:

                # calculate filename
                video_uuid = video_url.split('/')[-2].replace('-', '')
                video_ext = video_url.split('/')[-1].split('.')[-1]
                download_filename = os.path.join(
                    download_dir,
                    datetime.strftime(
                        event_datetime,
                        '%Y%m%d%H%M%SZ'
                    ) + video_uuid + '.' + video_ext
                )
                download_video(video_url, download_filename)
                dl_count += 1

        # save that activity was processed
        db.update_activity(activity_id)

    print(f'Downloaded {dl_count}')
    print(f'Total      {len(activities)}')


def download_video(url, filename):
    """Save video to disk.

    Args:
        url (str): URL of video
        filename (str): file to download video into
    """
    print(f'Downloading from {url} to {filename}')
    response = requests.get(url, stream=True)
    with open(filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=16*1024):
            f.write(chunk)


def download_image(url, filename, created_datetime):
    """Save image to disk, editing exif data.

    Args:
        url (str): URL of image
        filename (str): file to download image into
        create_datetime (datetime): exif data to inject
    """
    print(f'Downloading from {url} to {filename}')
    raw_data = io.BytesIO()
    response = requests.get(url, stream=True)

    # stream image data into bytes
    for chunk in response.iter_content(chunk_size=16*1024):
        raw_data.write(chunk)

    # google photos expected format
    created_str = datetime.strftime(created_datetime, '%Y:%m:%d %H:%M:%S')

    # update created date
    im = Image.open(raw_data)
    exif = im.getexif()
    exif.update(
        [
            (306, created_str),    # Exif.Image.DateTime
            (34858, '+00:00')      # Exif.Image.TimeZoneOffset
        ]
    )
    im.save(filename, exif=exif)


def fetch_student_id(client, student):
    """Results student name substring to UUID.

    Args:
        client (brightwheel.Client): API client
        student (str): substring student name to match

    Returns:
        str: UUID of student

    """
    # get list of students guardian has
    students = client.get_guardians_students()['students']
    if not students:
        exit('Unable to find any students!')

    # filter one student out
    matched_students = [
        x
        for x in students
        if student in f"{x['student']['first_name']} {x['student']['last_name']}"  # noqa:E501
    ]
    if not matched_students:
        exit(f'Unable to find "{student}"!')
    elif len(matched_students) > 1:
        exit(f'Found too many students matching "{student}"!')

    # extract id to use in feed request
    student_id = matched_students[0]['student']['object_id']
    print(f'Found {student} with id={student_id}')
    return student_id


if __name__ == '__main__':
    main()
