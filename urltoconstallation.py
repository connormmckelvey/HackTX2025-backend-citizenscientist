import requests
import time
import os
import sys
from PIL import Image
from io import BytesIO
import json


ASTROMETRY_API_KEY = "ucszdpwdhrbixmha"
API_BASE_URL = "http://nova.astrometry.net/api/" 
POLL_INTERVAL_SECONDS = 30 


MAX_SUBMISSION_POLLS = 10
MAX_JOB_POLLS = 20


def login(api_key):
    """Logs in to Astrometry.net to obtain a session key."""
    print("Attempting to log in to Astrometry.net...")
    login_url = API_BASE_URL + "login"
    
    try:
        response = requests.post(login_url, data={'request-json': '{"apikey": "%s"}' % api_key})
        response.raise_for_status() # Raise exception for bad status codes
        
        result = response.json()
        
        if result.get("status") == "success":
            session_key = result.get("session")
            print(f"Login successful. Session Key: {session_key}")
            return session_key
        else:
            print(f"Login failed: {result.get('err', 'Unknown error')}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"An error occurred during login: {e}")
        sys.exit(1)

def upload_image(session_key, file_path):
    """Uploads the image file using the session key."""
    if not os.path.exists(file_path):
        print(f"Error: File not found at path: {file_path}")
        sys.exit(1)

    print(f"\nUploading file: {file_path}...")
    upload_url = API_BASE_URL + "upload"
    
    # Files are sent as multipart form data.
    files = {'file': open(file_path, 'rb')}
    
    # Other parameters, including the session key, are sent in the request-json payload.
    data = {
        'request-json': '{"session": "%s", "public": "y", "allow_modifications": "n"}' % session_key
    }

    try:
        response = requests.post(upload_url, data=data, files=files)
        response.raise_for_status()
        
        result = response.json()
        files['file'].close() # Close the file handle
        
        if result.get("status") == "success":
            submission_id = result.get("subid")
            return submission_id
        else:
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        sys.exit(1)
    except Exception as e:
        sys.exit(1)
        
def poll_submission_status(submission_id):
    status_url = f"https://nova.astrometry.net/api/submissions/{submission_id}"
    status_response = requests.get(status_url)
    response_json = status_response.json()
    if response_json.get("jobs"):
        return (response_json["jobs"][0])
    else:
        return None

def poll_job_status(job_id):
    job_url = API_BASE_URL + f"jobs/{job_id}"
    
    # Polling loop with a maximum retry limit
    for retry_count in range(MAX_JOB_POLLS):
        try:
            response = requests.get(job_url)
            response.raise_for_status()
            
            job_data = response.json()
            job_status = job_data.get("status")
            
            print(f"  > Job Status: {job_status}")
            
            if job_status == "success":
                print("Job successfully solved!")
                return True
            elif job_status in ["failure", "failed", "error"]:
                print(f"Job failed to solve the image. Check Astrometry.net for details.")
                return False
            
            print(f"Waiting {POLL_INTERVAL_SECONDS} seconds before checking again (Attempt {retry_count + 1}/{MAX_JOB_POLLS})...")
            time.sleep(POLL_INTERVAL_SECONDS)
            
        except requests.exceptions.RequestException as e:
            print(f"Network/API Error checking job status (Attempt {retry_count + 1}/{MAX_JOB_POLLS}): {e}. Retrying.")
            time.sleep(POLL_INTERVAL_SECONDS)
        except Exception as e:
            print(f"An unexpected error occurred during job polling: {e}. Aborting job check.")
            return False

    return False

def get_job_results(job_id):
    objects_url = API_BASE_URL + f"jobs/{job_id}/objects_in_field/"
    objects_response = requests.get(objects_url)
    objects_response.raise_for_status()

    objects_data = objects_response.json()
    # The response structure has a key 'objects_in_field' containing a list of strings
    objects_list = objects_data.get("objects_in_field", [])
    constellation = []
    try:
        if objects_list:
            # Save the celestial objects in a list
            celestial_objects = [obj for obj in objects_list]
            for obj in celestial_objects:
                if "constellation" in obj.lower():
                    parts = obj.split("constellation", 1)
                    if len(parts) > 1:
                        name_part = parts[1].strip()
                        if "(" in name_part:
                            constellation_name = name_part.split("(")[0].strip()
                        else:
                            constellation_name = name_part
                        constellation.append(constellation_name)

    except requests.exceptions.RequestException as e:
        celestial_objects = []
    
    return constellation

def setConstellation(imageJPEG):
    # 1. Login and get session key
    session_key = login(ASTROMETRY_API_KEY)
    if not session_key: return

    submission_id = upload_image(session_key, imageJPEG)
    if not submission_id: return
        
    time.sleep(30)
    job_id = poll_submission_status(submission_id) #14370871
    constellation = []
    if not job_id: 
        return []
    if poll_job_status(job_id):
        constellation = get_job_results(job_id)
    else:
        return []

    return constellation


def urlToConstellation(url):
    response = requests.get(url)
    if response.status_code == 200:
        img = Image.open(BytesIO(response.content))
        img.convert("RGB").save("downloaded_image.jpg", "JPEG")
        return "downloaded_image.jpg"


def addConstellationsToJsonFromJson(jsonData):
    for item in jsonData:
        imageURL = item.get('photo_url')
        print(imageURL)
        if imageURL:
            imageJPEG = urlToConstellation(imageURL)
            constellation = setConstellation(imageJPEG)
            item['constellation_names'] = constellation
    return jsonData

