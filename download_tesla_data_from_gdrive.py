import io
from pathlib import Path
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from apiclient.http import MediaIoBaseDownload

DATADIR = Path('./tesla_gateway_data/')
FOLDERID = "11-VGNfbcMm1mzcr-F_Dm1SoiG3j_JrTW"

# If modifying these scopes, delete the file token.pickle.
# SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    """Shows basic usage of the Drive v3 API.
    """
    creds = None

    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if Path('token.pickle').is_file():
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('drive', 'v3', credentials=creds)

    kwargs = {
        "q": "'{}' in parents and trashed=false".format(FOLDERID),
        # Specify what you want in the response as a best practice.
        # This string will only get the files' ids, names, and the
        # ids of any folders that they are in.
        "fields": "nextPageToken,incompleteSearch,files(id,name)",
        # Add any other arguments to pass to list()
    }
    request = service.files().list(**kwargs)

    items = []
    while request is not None:
        response = request.execute()
        items.extend(response['files'])
        request = service.files().list_next(request, response)

    if not items:
        print('No remote files found.')

    uptodate = True
    for item in items:
        filename = item['name']
        if not (DATADIR / filename).is_file():
            uptodate = False
            print(f"Getting missing file '{filename}'")
            fileid = item['id']
            request = service.files().get_media(fileId=fileid)
            # fh = io.BytesIO()
            fh = open(DATADIR / filename, 'wb')
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                # print(f"Download {int(status.progress() * 100):d}%.")

    if uptodate is True:
        lastlocalfile = sorted(DATADIR.glob("20*.csv"))[-1]
        print(f"Folder is up-to-date ({lastlocalfile.name})")


if __name__ == '__main__':
    main()
