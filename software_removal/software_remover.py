#!/usr/bin/env python3
# Objective: Deletes unapproved applications from company devices
# Arek Smullen (arek.smullen@sheerid.com)
# SheerID 2025

from os import environ
import requests
from datetime import datetime
from csv import reader
from boto3 import client
import re
from json import loads

# TODO (arek): swap out AWS variables with Prod ones

# Globals
# bucket = "sheerid-logarchive-use1"
bucket = "arekgcpscoutsuite"
region = "us-east-1"
environ["AWS_DEFAULT_REGION"] = region
system_ids = []
app_list = []
reportFile = "apps.csv"

# TODO (arek): create function to run the command.


def get_secret():
    secret_name = "jc-api-key"
    region_name = "us-east-1"
    # Create a Secrets Manager client
    secrets_manager = client(service_name="secretsmanager", region_name=region_name)
    get_secret_value_response = secrets_manager.get_secret_value(SecretId=secret_name)
    secret = loads(get_secret_value_response["SecretString"])
    return secret["Jumpcloud-API-key"]


# grabs latest file from S3
def grab_file():
    # prefix = "it/software-inventory/"
    s3 = client("s3")
    # List all objects in the bucket with the specified prefix
    # response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    response = s3.list_objects_v2(Bucket=bucket)

    if "Contents" not in response:
        print(f"No files found in bucket {bucket} with prefix {prefix}")
        return None

    latest_file = None
    latest_date = None

    # Define a regex pattern to extract date from the file name
    pattern = re.compile(r"(\d{4}-\d{2}-\d{2})_software_report\.csv")

    for obj in response["Contents"]:
        file_name = obj["Key"]

        # Search for files matching the pattern
        match = pattern.search(file_name)
        if match:
            file_date = match.group(1)

            # Convert date string to a datetime object for comparison
            file_date_dt = datetime.strptime(file_date, "%Y-%m-%d")

            # Compare dates to find the most recent one
            if latest_date is None or file_date_dt > latest_date:
                latest_date = file_date_dt
                latest_file = file_name

    if not latest_file:
        print("No matching report files found.")
        return None

    s3.download_file(Bucket=bucket, Key=latest_file, Filename="./apps.csv")


def grab_apps_and_systems(file, list1, list2):
    with open(f"{file}", "r") as app_file:
        contents = reader(app_file)
        app_list = list1
        system_ids = list2
        for line in contents:
            app = line[2]
            system = line[0]
            if line[0] == "system_id":
                continue
            else:
                app_list.append(f'"{app}"')
                system_ids.append(system)
    app_list = set(app_list)
    system_ids = set(system_ids)


def create_jc_command(apps: list) -> str:
    apps = " ".join(apps)
    url = "https://console.jumpcloud.com/api/commands"
    cmd_string_one = f"""
    #!/bin/bash
    declare -a app_list
    app_list=({apps})"""

    cmd_string_two = """
    for app in ${app_list[@]}:
    do
        if [ -e /Applications/$app ]; then
          chmod 000 /Applications/$app
        else
          continue
        fi
    done
    """
    cmd_string = cmd_string_one + cmd_string_two
    payload = {
        "command": cmd_string,
        "commandType": "mac",
        "name": "test delete apps",
        "sudo": True,
        "user": "000000000000000000000000",
    }
    try:
        response = requests.request("POST", url=url, json=payload, headers=headers)
        response.raise_for_status()
        response = loads(response.text)
    except requests.exceptions.RequestException as e:
        print(f"Error creating Jumpcloud Command: {e}")

    return response["id"]


def bind_devices(id: str) -> str:
    url = f"https://console.jumpcloud.com/api/v2/commands/{id}/associations"
    try:
        for item in system_ids:
            payload = {"id": item, "op": "add", "type": "system"}
            requests.request("POST", url, json=payload, headers=headers)

    except Exception as e:
        print(f"Error binding system to command: {e}")
    return id


headers = {
    "x-api-key": get_secret(),
    "content": "application/json",
}

grab_file()
grab_apps_and_systems(reportFile, app_list, system_ids)
bind_devices(create_jc_command(app_list))
