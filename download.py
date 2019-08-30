#!/usr/bin/env python3

import json
import os
import re
import requests
import shutil
import subprocess
from urllib.parse import urlsplit

import fdroidserver.common
import fdroidserver.index

index = {}
url = None

def main():
  with open("apks.json") as file:
    apks = json.load(file)
  if os.path.isfile("cache/versions.json"):
    with open("cache/versions.json") as file:
      versions = json.load(file)
  else:
    versions = {}
  for apk in apks:
    ver = ""
    ignore = True
    if "ignoreErrors" in apk:
      ignore = apk["ignoreErrors"]
    if "version" in apk:
      verObj = apk["version"]
      if "json" in verObj:
        ver = get_version_json(verObj["url"], verObj["json"])
      elif "regex" in verObj:
        ver = get_version_regex(verObj["url"], verObj["regex"])
      elif "fdroid" in verObj:
        ver = get_version_fdroid(apk["baseUrl"].format(ver="?fingerprint=" + verObj["fingerprint"]), verObj["fdroid"], ignore)
      if apk["name"] in versions and ver == versions[apk["name"]]:
        print("Using cached " + apk["name"])
        continue
      versions[apk["name"]] = ver
    print("Downloading " + apk["name"] + " " + ver)
    if "architectures" in apk:
      for arch in apk["architectures"]:
        download(apk["name"] + ".apk", apk["baseUrl"].format(arch=arch, ver=ver, ver_stripped=ver.lstrip("v")), ignore)
    else:
      download(apk["name"] + ".apk", apk["baseUrl"].format(ver=ver, ver_stripped=ver.lstrip("v")), ignore)
  for apk in apks:
    if not os.path.isfile("fdroid/repo/" + apk["name"] + ".apk"):
      download(apk["name"] + ".apk", "https://fdroid-repo.calyxinstitute.org/fdroid/repo/" + apk["name"] + ".apk" ,ignore)
  with open('cache/versions.json', 'w') as file:
    json.dump(versions, file, ensure_ascii=False)

def download(name, download_url, ignore):
  if download_url.endswith(".apk") or download_url.endswith(".apk.lz"):
    #if os.path.isfile("fdroid/repo/" + name):
    #  os.rename("fdroid/repo/" + name, "fdroid/repo/" + os.path.split(urlsplit(download_url).path)[-1])
    retcode = subprocess.call(["wget", "--progress=dot:mega", "-N", "-P", "fdroid/repo", download_url])
    if retcode == 0:
      apk = os.path.split(urlsplit(download_url).path)[-1]
      if download_url.endswith(".apk.lz"):
        subprocess.call(["lzip", "-d", "-f", "fdroid/repo/" + apk])
        apk = os.path.splitext(os.path.basename(apk))[0]
      os.rename("fdroid/repo/" + apk, "fdroid/repo/" + name)
  else:
    retcode = subprocess.call(["wget", "--progress=dot:mega", "-nc", "--content-disposition", "-P", "fdroid/repo", download_url])
  if not ignore and retcode != 0:
    raise Exception("Failed downloading " + download_url)

def get_version_regex(url, query):
  request = requests.get(url)
  regex = re.search(query, request.text)
  return regex.group(1)

def get_version_json(url, query):
  request = requests.get(url)
  version = request.json()
  if not isinstance(query, list):
    return version[query]
  for query_part in query:
    version = version[query_part]
  return version

def get_fdroid_index(new_url):
  global index
  global url
  if new_url == url and index is not None:
    return index
  fdroidserver.common.config = {}
  fdroidserver.common.config['jarsigner'] = shutil.which('jarsigner')
  try:
    print("Downloading F-Droid index from " + new_url)
    new_index, etag = fdroidserver.index.download_repo_index(new_url)
  except Exception as e:
    print(e)
    if index is not None:
      return index
    else:
      raise Exception("Failed to get F-Droid index from " + new_url)
  if new_index is not None:
    index = new_index
    url = new_url
  return index

def is_fdroid_apk_compatible(apk):
  if not 'nativecode' in apk:
    return True
  for abi in apk['nativecode']:
    if abi == "arm64-v8a":
      return True
    if abi == "armeabi-v7a":
      return True
    if abi == "armeabi":
      return True

def get_version_fdroid(url, query, ignore):
  data = get_fdroid_index(url)
  for app in data['apps']:
    if app['packageName'] == query:
      for apk in data['packages'][app['packageName']]:
        # No idea why suggestedVersionCode is a string
        if apk['versionCode'] >= int(app['suggestedVersionCode']):
          if is_fdroid_apk_compatible(apk):
            return apk['apkName']
      # Fallback to first compatible apk
      for apk in data['packages'][app['packageName']]:
        if is_fdroid_apk_compatible(apk):
          return apk['apkName']

if __name__ == "__main__":
  main()
