import sys
import os
import asyncio
import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import Stealth

async def check_links(input_file, output_report_file):
    # Absolute path for the local file
    file_path = f"file://{os.path.abspath(input_file)}"
    results = []

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True, channel='chromium')
        c = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36")
        page = await c.new_page()

        print(f"Reading file: {input_file}...")
        try:
            await page.goto(file_path)
        except Exception as e:
            print(f"Error loading the local file: {e}")
            await browser.close()
            return

        tables = await page.locator('table').all()

        urls = []
        for table in tables:
            data = {
                "url": None,
                "name": None,
                "parent_url": None
            }

            # Locate all rows within this specific table
            rows = await table.locator('tr').all()

            for row in rows:
                # Get all cells (td) in the row
                cells = await row.locator('td').all()
                if len(cells) != 2:
                    continue

                label = (await cells[0].inner_text()).strip()

                #Extract URL (strip backticks)
                if label == "URL":
                    raw_url = (await cells[1].inner_text()).strip()
                    data["url"] = raw_url.strip("`'").strip()

                # 2. Extract Name (strip backticks)
                elif label == "Name":
                    raw_name = (await cells[1].inner_text()).strip()
                    data["name"] = raw_name.strip("`'").strip()

                # 3. Extract Parent URL (find the href of the link)
                # Note: Playwright handles &nbsp; as a normal space in inner_text()
                elif "Parent" in label:
                    link = cells[1].locator('a').first
                    if (await link.count()) > 0:
                        data["parent_url"] = await link.get_attribute('href')

            # Add to results if we found valid data
            if data["url"] or data["name"]:
                urls.append(data)
        
        await page.close()
        
        print(f"Found {int(len(urls)/2)} URLs to check.")

        # Iterate through each URL found
        for url in urls:
            parent_url = url["parent_url"]
            name = url ["name"]
            url = url["url"]
            if not url:
                continue

            page = await c.new_page()

            print(f"Checking: {url}")
            try:
                result = await checkURL(page, url)
                result['parent_url'] = parent_url
                result['name'] = name
                results.append(result)
            except Exception as e:
                # http->https redirections don't work for some sites, even though they work in a regular browser
                if url.startswith('http://') and type(e) is PlaywrightTimeoutError:
                    result = await checkURL(page, url.replace('http://', 'https://', 1))
                    result['status'] = 'Warning'
                    result['details'] += ' The original link was http://. Checked the https version.'
                    result['parent_url'] = parent_url
                    result['name'] = name
                    results.append(result)
                else:
                    results.append({"url": url, "parent_url": parent_url, "name": name, "status": "Error", "details": str(e)})
            print(results[-1]['details'])
            await page.close()

        await browser.close()

    generate_report(results, output_report_file)
    
async def checkURL(page, url):
    # Attempt to navigate to the URL with a 10-second timeout
    response = await page.goto(url, timeout=10000, wait_until="load")
    if response and response.ok:
        result = {"url": url, "status": "Success", "details": f"Status {response.status}."}
    else:
        status_code = response.status if response else "No Response"
        response_body = str(await response.body())
        if "cloudflare" in response_body and "cRay" in response_body and "_cf_chl" in response_body:
            result = {"url": url, "status": "Warning", "details": f"Failed with status {status_code} but Cloudflare detected. Manual check required."}
        else:
            result = {"url": url, "status": "Error", "details": f"Failed with status {status_code}."}
    return result

def generate_report(results, output_report_file):
    output_file = os.path.abspath(output_report_file)
    
    html_content = f"""
    <html>
    <head>
        <title>Link Check Results</title>
        <style>
            table {{ border-collapse: collapse; width: 100%; font-family: sans-serif; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #f4f4f4; }}
            .success {{ color: green; font-weight: bold; }}
            .error {{ color: red; font-weight: bold; }}
            .warning {{ color: GoldenRod; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>URL Verification Report</h1>
        <p>Generated on {datetime.datetime.now()}</p>
        <table>
            <tr>
                <th>URL</th>
                <th>Result</th>
                <th>Details</th>
            </tr>
    """

    total_success = 0
    total_fail = 0
    total_warn = 0
    for row in results:
        if row['status'] == "Success":
            status_class = "success"
            total_success += 1
        elif row['status'] ==  "Error":
            status_class = "error"
            total_fail += 1
        elif row['status'] ==  "Warning":
            status_class = "warning"
            total_warn += 1
        if status_class == 'error' or status_class == 'warning' :
            html_content += f"""
                <tr>
                    <td>
                    <p><b>URL:</b> <a href="{row['url']}">{row['url']}</a></p>
                    <p><b>Parent:</b> <a href="{row['parent_url']}">{row['parent_url']}</a></p>
                    <p><b>Name:</b> {row['name']}</p></td>
                    <td class="{status_class}">{row['status']}</td>
                    <td>{row['details']}</td>
                </tr>
            """

    html_content += f"</table><p>Total errors: {total_fail}, total warnings: {total_warn} </p></body></html>"

    with open(output_file, "w") as f:
        f.write(html_content)
    
    print(f"\nScan complete. Results saved to: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python link_checker.py <path_to_html_file> <outputreportname>")
    else:
        asyncio.run(check_links(sys.argv[1], sys.argv[2]))
