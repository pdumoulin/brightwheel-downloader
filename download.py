"""CLI to download activity metadata and media."""

import argparse
import json
import os
import sys
from datetime import datetime

from brightwheel import Client

from database import DB

from processors import ImageProcessor
from processors import VideoProcessor


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
        help='ignore stored auth and replace after login'
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
    media_subparser.add_argument(
        '-s',
        action='store_true',
        help='skip setting exif tags via exiftool'
    )
    media_subparser.add_argument(
        '-f',
        action='store_true',
        help='download even if file already exists'
    )
    media_subparser.add_argument(
        '--lat',
        type=float,
        required='--lon' in sys.argv,
        help='Latitude metadata to add, used for timezone offsetting'
    )
    media_subparser.add_argument(
        '--lon',
        type=float,
        required='--lat' in sys.argv,
        help='Longitude metadata to add, used for timezone offsetting'
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
    if not stored_auth or force_login:
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
    write_tags = not args.s
    force_dl = args.f
    latitude = args.lat
    longitude = args.lon

    # get activities needing to be processed
    activities = db.select_activities()
    dl_count = 0
    tag_count = 0

    # media types to process
    processors = [
        ImageProcessor(),
        VideoProcessor()
    ]

    # iterate over each student's data
    for activity in activities:
        activity_id = activity['id']
        student_id = activity['student_id']
        raw_data = json.loads(activity['json'])

        # setup download media dir scoped by student
        download_dir = os.path.join(base_download_dir, student_id)
        if not os.path.isdir(download_dir):
            os.makedirs(download_dir)

        # look for media that can be processed
        for processor in processors:
            (processed, downloaded, tagged) = processor.process(
                download_dir,
                raw_data,
                write_tags=write_tags,
                force_dl=force_dl,
                latitude=latitude,
                longitude=longitude
            )
            if processed:
                if downloaded:
                    dl_count += 1
                if tagged:
                    tag_count += 1

        # save that activity was processed
        db.update_activity(activity_id)

    print(f'Downloaded {dl_count}')
    print(f'Tagged     {tag_count}')
    print(f'Total      {len(activities)}')


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
        if student in f"{x['student']['first_name']} {x['student']['last_name']}" or x['student']['object_id'] == student  # noqa:E501
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
