import os
import re
import shutil
import subprocess
import zipfile

import requests
from loguru import logger
from tqdm import tqdm

USER_PLATFORM = "linux64"

def get_chrome_version():
    try:
        # Run the 'google-chrome --version' command and capture the output
        result = subprocess.check_output(['google-chrome', '--version'], stderr=subprocess.STDOUT, text=True)

        # Extract the version from the output
        version = result.strip().split()[-1]

        # Check if returned Chrome version string is valid
        if not is_valid_version(chromedriver_version=version):
            logger.error(f"Invalid Chrome version returned from subprocess: {version}")
            return None

        return version
    except subprocess.CalledProcessError as e:
        # Handle any errors, such as Chrome not being installed
        error_msg = f"Error: {e.output.strip()}"
        logger.error(error_msg)
        return None

def is_valid_version(chromedriver_version: str):
    version_pattern = r'\d+\.\d+\.\d+\.\d+'
    return re.match(version_pattern, chromedriver_version) is not None

def get_chromedriver_download_url(chrome_version: str, user_platform: str):
    latest_versions_url = "https://googlechromelabs.github.io/chrome-for-testing/latest-versions-per-milestone-with-downloads.json"
    resp = requests.get(latest_versions_url)
    
    if resp.status_code != 200:
        logger.error(f"Resp. status code is not equal to 200. Resp. status code: {resp.status_code}")
        return None

    chromedriver_major_version = chrome_version.split(".")[0]
    
    try:
        milestones_dict = resp.json()["milestones"]
    except KeyError:
        logger.warning("'milestones' key does not exist inside 'latest_versions_url' JSON response.")
        return None
    
    try:
        major_version_dict = milestones_dict[chromedriver_major_version]
    except KeyError:
        logger.warning(f"Major version key {chromedriver_major_version} does not exist inside 'latest_versions_url' JSON response.")
        return None
    
    try:
        downloads_list_of_dicts = major_version_dict["downloads"]["chrome"]
    except KeyError:
        logger.warning(f"'downloads' or 'chrome' key(s) does not exist inside 'latest_versions_url' JSON response.")
        return None

    download_url = None
    for dict_i in downloads_list_of_dicts:
        dict_i_platform = dict_i["platform"]
        if dict_i_platform.lower() == user_platform.lower():
            download_url = dict_i["url"]
            download_url = "/".join(download_url.split("/")[:-1]) + f"/chromedriver-{user_platform}.zip"
            break

    if not download_url:
        logger.error(f"Was unable to retrieve chromedriver download URL for Chrome major version '{major_version_dict}' and user platform '{user_platform}'")
    return download_url

def download_chromedriver(chromedriver_download_url: str):
    fn = chromedriver_download_url.split("/")[-1]

    with requests.get(chromedriver_download_url, stream=True) as resp:
        resp.raise_for_status()
        with open(fn, "wb") as f:
            pbar = tqdm(total=int(resp.headers.get("Content-Length", 0)) or None)  # Use 0 if Content-Length is not available
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    pbar.update(len(chunk))

    pbar.close()
    return fn

def extract_zipped_file(zip_fn: str):
    try:
        # Open the .zip file
        with zipfile.ZipFile(zip_fn, "r") as zip_ref:
            # Extract all the contents to the specified directory
            zip_ref.extractall("")
    except Exception as e:
        logger.error(f"Something went wrong while extracting file: {e}")
        return False

    zip_fn_wo_ext = zip_fn.split(".")[0]

    return os.path.join(zip_fn_wo_ext, "chromedriver")

def find_chromedriver_location():
    try:
        # Use the 'which' command to locate the Chromedriver executable
        result = subprocess.run(["which", "chromedriver"], capture_output=True, text=True, check=True)

        # Extract the directory where Chromedriver is located
        chromedriver_path = result.stdout.strip()

        return chromedriver_path
    except subprocess.CalledProcessError as e:
        # Handle any errors, such as Chromedriver not being found
        error_msg = f"Error: {e.stderr.strip()}"
        logger.error(error_msg)
        return None

def move_extracted_chromedriver(extracted_chromedriver_fp: str, os_chromedriver_location: str):
    try:
        shutil.copy(extracted_chromedriver_fp, os_chromedriver_location)

        # Set execute permission for the chromedriver executable
        os.chmod(os_chromedriver_location, 0o755)  # 0o755 represents rwxr-xr-x
        
        return True
    except Exception as e:
        error_msg = f"Error moving Chromedriver: {e}"
        logger.error(error_msg)
        return False

def main(user_platform=USER_PLATFORM):
    current_chrome_version = get_chrome_version()
    if not current_chrome_version:
        return
    
    chromedriver_download_url = get_chromedriver_download_url(chrome_version=current_chrome_version, user_platform=user_platform)
    if not chromedriver_download_url:
        return
    
    logger.info(f"Starting to download chromedriver (version: {current_chrome_version}, platform: {user_platform})")
    downloaded_fn = download_chromedriver(chromedriver_download_url=chromedriver_download_url)
    if not downloaded_fn:
        logger.error("Failed to download chromedriver")
        return
    else:
        logger.success("Successfully downloaded chromedriver")

    extracted_chromedriver_fp = extract_zipped_file(zip_fn=downloaded_fn)
    if not extracted_chromedriver_fp:
        return
       
    os_chromedriver_location = find_chromedriver_location()
    if not os_chromedriver_location:
        return
    
    final_status = move_extracted_chromedriver(extracted_chromedriver_fp=extracted_chromedriver_fp, os_chromedriver_location=os_chromedriver_location)
    if final_status:
        logger.success("Chromedriver successfully updated for your OS.")

if __name__ == "__main__":
    main()
