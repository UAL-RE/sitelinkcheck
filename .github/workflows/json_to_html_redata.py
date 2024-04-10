#This script takes the base URL of the figshare API as an argument. It takes the output path and filename as the second argument.
#The base URL must contain at least one GET parameter, "institution", indicating the institution id
#The script retrieves all metadata for all items in the figshare instance and saves it
#to a single HTML page in which all URLs have been converted to links
import json
import requests
import re
import string
import sys
import os

def add_link_tags(text):
  """
  This function takes a string and wraps URLs in HTML anchor tags, excluding already wrapped ones.

  Args:
      text: The string to process.

  Returns:
      A new string with URLs converted to anchor tags (excluding already wrapped).
  """
  # Regular expression to match URLs not in anchor tags
  url_regex = r"(?<!href=\")(?P<url>(http|https|ftp)\://[^\s<\"]+)(?![^<]*</a>)"
  
  # Function to replace matched URLs with anchor tags
  def replace_url(matchobj):
    url = matchobj.group("url")
    if url[-1] in string.punctuation:
        #strip any punctuation at the end of the url
        url = url[0:-1]
    return f'<a href="{url}">{url}</a>'

  # Use re.sub to replace all URLs in the text
  return re.sub(url_regex, replace_url, text)

def retrieve_all_data(base_url, page_size=100):
   """Retrieves all paginated JSON data from the given URL and returns a single combined JSON array.

   Args:
       base_url (str): The base URL of the paginated resource.
       page_size (int, optional): The number of records to retrieve per page. Defaults to 100.

   Returns:
       list: The combined list of JSON objects from all pages.
   """

   all_data = []
   page = 1

   while True:
       print(f"Fetching page {page}")
       url = f"{base_url}&page={page}&page_size={page_size}&order=published_date&order_direction=desc"
       
       response = requests.get(url)
       response.raise_for_status()  # Raise an exception if the request fails

       data = response.json()
        
       # Check if there are any results on this page
       if not data:
           break

       all_data.extend(data)  # Append the data from this page to the overall list
       page+=1       

   return all_data

if __name__ == "__main__":
   base_url = sys.argv[1]
   outputpath = sys.argv[2] #e.g., ./data
   
   all_objects = retrieve_all_data(base_url)
   
   with open(outputpath, "w", encoding="utf-8") as file:
       file.write("<html>")
       for obj in all_objects:           
           url = obj["url_public_api"]
           
           print("Processing " + url)
           response = requests.get(url)
           json_data = response.json()
           
           # convert to string, unescaping any quotes in the json.
           jsonstr = add_link_tags(json.dumps(json_data).replace('\\"', '"'))
           
           file.write(jsonstr + "<br><br><br>")
       file.write("</html>")
       print(os.path.realpath(file.name))

   print("HTML created successfully!")
