# Automated UET Audit
# Version 1.12 (02/07/2020)
# Phillip Molock | phmolock@microsoft.com
# For a list of commands  to use with this script type python uetaudit.py --options 

# To do 
# 1. Factor in robots.txt 
# 2. Factor in sitemap.xml

from selenium import webdriver
from browsermobproxy import Server
from urllib.parse import urlparse
from pprint import pprint
from random import randint, shuffle
import time, os, csv, sys, getopt, re

# Overall script settings 
settings = {
    'homepage': None,
    'timePerPage': 20,
    'pagesToCrawl': 10,
    'requiredPagesToCrawl': None,
    'txtFileLocation': None,
    'outputDirectory': 'output',
    'logsDirectory': 'logs',
    'customer': None,
    'version': 1.12,
    'versionDate':'02/06/2020'
}

# Capture any non-critical errors for print out
logs = []

# Merge the arguments received from command line with script settings
def mergeSettings():
    # Collect provided options from command line input
    argv = sys.argv[1:]
    try:
        options, args = getopt.getopt(argv, None, longopts=['homepage=', 'file=', 'pagecount=', 'customer=', 'options'])  
    except Exception as e:
        print(f"\n--Error Starting the Script--\n\n[Python Error Specifics] {e}\n")
        printOptions()

    # Review provided options, updating settings dictionary  
    for option in options:
        specificOption = option[0]
        choice = option[1]
        if specificOption == '--homepage':
            # Verify the homepage provided at a minimum follows a basic URL Structure
            if re.match('(https://|http://).*\..*\..*',choice):
                parsedHomepageUrl = urlparse(choice)
                if parsedHomepageUrl.scheme != '' and parsedHomepageUrl.netloc != '' and re.match('.*\..*\..*', parsedHomepageUrl.netloc):
                    settings['homepage'] = choice
            else:
                print(f"\n--Error Starting the Script--\n[Error] The homepage provided is not in proper format https://www.bing.com\n\t[Example Command | Just a homepage]\tpython uetaudit.py --homepage https://www.bing.com\n\t[Example Command | Just a txt file]\tpython uetaudit.py --file urls.txt\n\t[Example Command | Homepage and txt file]\tpython uetaudit.py --homepage https://www.bing.com --file urls.txt\n")    
                printOptions()

        elif specificOption == '--pagecount':
            try:
                settings['pagesToCrawl'] = int(choice)
            except:
                print(f"\n--Error Starting the Script--\n\n[Error] The pagecount value of {choice} is not valid. Please provide the number of pages you'd like to randomly crawl in number format.\n[Example Command]\tpython uetaudit.py --homepage https://www.bing.com --pagecount 3\n")
                printOptions()
        elif specificOption =='--customer':
            # Sanitize input to remove any illegal filename characters
            sanitizedChoice = re.sub("\[|\\||^|\$|\.|\||\?|\*|\+|\(|\)|\"|\'|\n|\t", '', choice)
            settings['customer'] = sanitizedChoice
        elif specificOption == '--file':
            if choice.endswith('.txt'):
                settings['txtFileLocation'] = choice
                settings['requiredPagesToCrawl'] = readPagesFromText(settings['txtFileLocation'])
            else:
                print(f"\n--Error Starting the Script--\n\n[Error] Please specify a text file when using the --file option. The file name {choice} does not end in .txt\n")
                printOptions()
        elif specificOption == '--options':
            printOptions()
            
    # Confirm settings provide the minimum information (at least a homepage and/or required pages to crawl)   
    if not settings['homepage'] and not settings['requiredPagesToCrawl']:
        print(f"\n--Error Starting the Script--\n[Error] No homepage or text file of URLs specified. The script has no URLs to analyze. Please specify a home page or a text file of URLs (or both).\n\t[Example Command | Just a homepage]\tpython uetaudit.py --homepage https://www.bing.com\n\t[Example Command | Just a txt file]\tpython uetaudit.py --file urls.txt\n\t[Example Command | Homepage and txt file]\tpython uetaudit.py --homepage https://www.bing.com --file urls.txt\n")     
        printOptions()

    print(f"--UET Automated Audit--\n\tVersion: {settings['version']} {settings['versionDate']}\n\tFor a list of options: python uetaudit.py --options\n\n--Audit Details--\n\tAdvertiser Homepage: {settings['homepage']}\n\tPages to Crawl: {settings['pagesToCrawl']}\n\tText File: {settings['txtFileLocation']}\n\tCustomer Name: {getCustomerName()}")

# Read URLs from text file into requierdPages list
def readPagesFromText(txtFileLocation):
    requiredPages = []
    try: 
        with open(txtFileLocation, 'r', errors='ignore') as txtIn:
            for line in txtIn:
                line = line.replace('\n','')
                requiredPages.append(line)
    except Exception as e:
        print(f"\n--Error Starting the Script--\n\n[Error] There was an issue reading from {txtFileLocation}\nPlease insure you've provided the exact or relative path to the text file. It's recommended you place the text file in the same directory as the script.\n[Python Error Specifics] {e}\n")
        printOptions()
    return requiredPages

# Print possible options you can include when running the script in the command shell
def printOptions():
    print(f"--Command Options--\n\t--homepage\tSpecify URL of homepage you'd like to audit\n\t--pagecount\tThe number of pages you'd like to randomly crawl\n\t--file\t\tThe location of a txt file containing URLs to crawl\n\t--customer\tCustomer name to be used with output file\n\t--options\tList available command options")
    quit()

# Verify that a link is acceptable for addition to the linksQueue
def verifyHref(href, linksHistory, newLinks):
    hrefNetloc = urlparse(href).netloc
    homePageNetloc = urlparse(settings['homepage']).netloc
    if hrefNetloc == homePageNetloc and href not in set(linksHistory) and href != settings['homepage'] and href not in set(newLinks) and not re.match('.*(/help|/login|/faq|/contact|/contactus|/customerservice|/customer-service|/account)', href) and href != f"{settings['homepage']}/":
        return True
    else:
        return False

# Get a new list of links to add to the linksQueue 
def getNewLinks(links, linksHistory):
    newLinks = []
    randomLinks = []
    
    for link in links:
        href = link.get_attribute("href")
        # print(f"Verifying {href}.. {verifyHref(href, linksHistory, newLinks)}")
        if verifyHref(href, linksHistory, newLinks):
            newLinks.append(href)
    
    if len(newLinks) > 3:
        shuffle(newLinks)
        for link in newLinks:
            if len(randomLinks) < 3:
                if link not in set(randomLinks):
                    randomLinks.append(link)
            else:
                break
    else:
        return newLinks

    return randomLinks

# Depending on homepage and/or txt file provided, build required pages to crawl list
def getRequiredLinkQueue():
    if not settings['homepage'] and not settings['requiredPagesToCrawl']:
        return []
    elif settings['homepage'] and not settings['requiredPagesToCrawl']:
        return [settings['homepage']]
    elif not settings['homepage'] and settings['requiredPagesToCrawl']:
       return settings['requiredPagesToCrawl']
    else:
        return [settings['homepage']] + settings['requiredPagesToCrawl']

def crawlLinkQueue():
    try:
        server = Server('browsermob-proxy-2.1.4\\bin\\browsermob-proxy.bat')
        server.start()
        proxy = server.create_proxy()
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument(f"--proxy-server={proxy.proxy}")
        chrome_options.add_argument(f"--ignore-certificate-errors")
        browser = webdriver.Chrome(options = chrome_options)
    except Exception as e:
        print(f"--Error While Running Script--\n\t[Error] Encountered error while starting local server, proxy server, or automated browser.\n\t[Python Error] {e}")
        server.stop()

    linksHistory = []
    requiredLinksQueue = getRequiredLinkQueue()
    linksQueue = []
    harDict = {}
    settings['pagesToCrawl'] += len(requiredLinksQueue)
    
    # Crawl required links, which is the home page plus any links imported from a file, builds initial random linksQueue
    for link in requiredLinksQueue:
        if link not in set(linksHistory):
            harDict[link] = []
            links = None
            proxy.new_har(link)
            print(f"\t[{len(linksHistory) + 1}] Crawling... {link}")

            try:
                browser.get(link)
            except Exception as e:
                log = f"--Error While Running Script--\n\t[Error] Encountered error while navigating automated browser to {link}. Skipping page.\n\t[Python Error] {e}"
                print(log)
                logs.append(log)
                continue

            time.sleep(settings['timePerPage'])

            try:
                links = browser.find_elements_by_xpath("//a[@href]")
            except Exception as e:
                    log = f"--Error While Running Script--\n\tIssue finding new links in {link}.\n\t[Python Error] {e}"
                    logs.append(log)
            
            for entry in proxy.har['log']['entries']:
                if 'bat.bing.com/action' in entry['request']['url']:
                    harDict[link].append(entry)

            newLinks = getNewLinks(links, linksHistory) if links else []
            linksQueue.extend(newLinks)
            linksHistory.append(link)
    
    # If you only provided a text file and no homepage, the links queue will be zero and we can return the current harDict
    if len(linksQueue) == 0:
        return harDict

    # Randomly crawl through the linksQueue (while adding new links to it) until you've hit the pagecount required 
    while True:
        if len(linksHistory) == settings['pagesToCrawl']:
            return harDict
        else:
            shuffle(linksQueue)
            link = linksQueue[0]
            harDict[link] = []
            links = None

            if link not in set(linksHistory):
                proxy.new_har(link)
                print(f"\t[{len(linksHistory) + 1}] Crawling... {link}")
                try:
                    browser.get(link)
                    time.sleep(settings['timePerPage'])
                except Exception as e:
                    log = f"--Error While Running Script--\n\t[Error] Encountered error while navigating automated browser to {link}. Skipping page.\n\t[Python Error] {e}"
                    print(log)
                    logs.append(log)
                    continue
                
                try:
                    links = browser.find_elements_by_xpath("//a[@href]")
                except Exception as e:
                    log = f"--Error While Running Script--\n\tIssue finding new links in {link}.\n\t[Python Error] {e}"
                    logs.append(log)
                
                for entry in proxy.har['log']['entries']:
                    if 'bat.bing.com/action' in entry['request']['url']:
                        harDict[link].append(entry)

                newLinks = getNewLinks(links, linksHistory) if links else []
                del(linksQueue[0])
                linksQueue.extend(newLinks)
                linksHistory.append(link)
                
# Take a query string from the HAR and unpack into the individual parameters
def unpackQueryString(queryString):

    unpackedQueryString = {
        'eventType' : None,
        'tagId' : None,
        'eventCategory' : None,
        'eventLabel' : None,
        'eventValue' : None,
        'eventAction' : None,
        'goalValue' : None,
        'goalCurrency' : None,
        'pageType': None,
        'prodId': None,
    }

    for parameter in queryString:
        if parameter['name'] == 'evt':
            unpackedQueryString['eventType'] = parameter['value']
        elif parameter['name'] == 'ti':
            unpackedQueryString['tagId'] = parameter['value']
        elif parameter['name'] == 'ec':
            unpackedQueryString['eventCategory'] = parameter['value']
        elif parameter['name'] == 'el':
            unpackedQueryString['eventLabel'] = parameter['value']
        elif parameter['name'] == 'ev':
            unpackedQueryString['eventValue'] = parameter['value']
        elif parameter['name'] == 'ea':
            unpackedQueryString['eventAction'] = parameter['value']
        elif parameter['name'] == 'gv':
            unpackedQueryString['goalValue'] = parameter['value']
        elif parameter['name'] == 'gc':
            unpackedQueryString['goalCurrency'] = parameter['value']
        elif parameter['name'] == 'pagetype':
            unpackedQueryString['pageType'] = parameter['value']
        elif parameter['name'] == 'prodid':
            unpackedQueryString['prodId'] = parameter['value']

    return unpackedQueryString

# Take an unpackedQueryString, the httpRespStatusCode from bat.bing.com and create, if any, a UET opportunity for improvement
def createUetOpportunity(unpackedQueryString, httpRespStatusCode):
    opportunity=""
    evt = unpackedQueryString['eventType']
    ti = unpackedQueryString['tagId']
    ec = unpackedQueryString['eventCategory']
    el = unpackedQueryString['eventLabel']
    ea = unpackedQueryString['eventAction']
    ev = unpackedQueryString['eventValue']
    gv = unpackedQueryString['goalValue']
    gc = unpackedQueryString['goalCurrency']
    pageType = unpackedQueryString['pageType']
    prodId = unpackedQueryString['prodId']    

    # Check if bat.bing responded with HTTP Status Code not in the 200s
    if httpRespStatusCode not in range(200,299):
        opportunity += f"Http Status Code: {httpRespStatusCode}. "

    # Check if event type is custom
    if evt == 'custom':
        # Check if custom event is not a product audience push
        if not prodId and not pageType:
            if not ec and not el and not ea and not ev:
                opportunity += "This is a custom event, but no Event Action (ea), Event Category (ec), Event Label( el), or Event Value (ev) were provided. "
            if not gv:
                opportunity += "No variable revenue (gv) provided. "
            if gv and not gc:
                opportunity += "Variable revenue provided but no goal currency (gc). "
        # Check if prodId and pageType provided
        elif pageType and prodId:
            invalidProdIds = validateProdId(prodId)
            if pageType.lower() not in {'home','category','other','purchase','searchresults','product','cart'}:
                opportunity += f"The pagetype {pageType} is not a valid pagetype. "
            if len(invalidProdIds) > 0:
                opportunity += f"The prodIds {invalidProdIds} are invalid (ASCII only, max length of 50 characters)."
        # Check if no pageType provided but prodId provided
        elif not pageType and prodId:
            opportunity += "ProdId provided but no pageType. "
        elif pageType and not prodId:
            opportunity += "pageType provided but no prodId. "

    return opportunity

# Validate a Product ID follows Microsoft Shopping Feed requirements
def validateProdId(prodId):
    invalidProdIds = []
    prodIdSplit = prodId.split(',')
    for prodIdToCheck in set(prodIdSplit):
        if not prodIdToCheck.isascii():
            invalidProdIds.append(prodIdToCheck)
        elif len(prodIdToCheck) > 50:
            invalidProdIds.append(prodIdToCheck)
    return set(invalidProdIds)

# Build out reportResults
def analyzeHarDict(harDict):
    reportResults = [['Page','TagId','Event Type','Query String Details','HTTP Response Code','Opportunity'],]
    for page, entries in harDict.items():
        pageLoadDetected = False
        # no UET detected on this page
        if len(entries) == 0:
            
            newReportRow = [
                page,
                '',
                '',
                '',
                '',
                f'No UET pageLoad tag detected. Either UET is not on the page or UET did not load within {settings["timePerPage"]} seconds.'
            ]
            reportResults.append(newReportRow)

        for entry in entries:
            unpackedQueryString = unpackQueryString(entry['request']['queryString'])
            evt = unpackedQueryString['eventType']
            ti = unpackedQueryString['tagId']
            ec = unpackedQueryString['eventCategory']
            el = unpackedQueryString['eventLabel']
            ea = unpackedQueryString['eventAction']
            ev = unpackedQueryString['eventValue']
            gv = unpackedQueryString['goalValue']
            gc = unpackedQueryString['goalCurrency']
            pageType = unpackedQueryString['pageType']
            prodId = unpackedQueryString['prodId']
            httpRespStatusCode = entry['response']['status']

            if evt == 'pageLoad':
                pageLoadDetected = True 
            
            newReportRow = [
                page,
                ti, 
                evt,
                f"{'ea='+ ea + ' ' if ea else ''}{'ev=' + ev + ' ' if ev else ''}{'ec=' + ec + ' ' if ec else ''}{'el=' + el + ' ' if el else ''}{'gv=' + gv + ' ' if gv else ''}{'gc=' + gc + ' ' if gc else ''}{'pagetype=' + pageType + ' ' if pageType else ''}{'prodid=' + prodId + ' ' if prodId else ''}",
                httpRespStatusCode,
                createUetOpportunity(unpackedQueryString, entry['response']['status'])
            ]
            reportResults.append(newReportRow)
        
        if not pageLoadDetected and len(entries) > 0:
            newReportRow = [
                page,
                '',
                '',
                '',
                '',
                f'No UET pageLoad tag detected. Either UET is not on the page or UET did not load within {settings["timePerPage"]} seconds.'
            ]
            reportResults.append(newReportRow)
            
    return reportResults

# Get customer name either from the homepage, --customer option, or return an empty string if nothing specified
def getCustomerName():
    if settings['customer']:
        return settings['customer']
    if not settings['customer'] and settings['homepage']:
        return urlparse(settings['homepage']).netloc.replace('.',' ')
    else:
        return ''

# Create final audit report
def createOutput(reportResults):
    try:
        os.mkdir(settings['outputDirectory'])
    except:
        pass
    customerName = getCustomerName()
    fileName = f"{settings['outputDirectory']}/UET Audit {customerName} {randint(0,10000)}.csv"
    print(f"\nWriting report... {fileName}")
    with open(fileName, 'w', newline='') as csvOut:
        csvWriter = csv.writer(csvOut, delimiter=',')
        for row in reportResults:
            csvWriter.writerow(row)

def createLogsOutput():
    try:
        os.mkdir(settings['logsDirectory'])
    except:
        pass
    customerName = getCustomerName()
    fileName = f"{settings['logsDirectory']}/Logs {customerName} {randint(0,10000)}.txt"
    with open(fileName, 'w',newline='') as txtOut:
        for log in logs:
            txtOut.write(log)
    return fileName

# Main
def main():
    mergeSettings()
    harDict = crawlLinkQueue()
    reportResults = analyzeHarDict(harDict)
    createOutput(reportResults)
    if len(logs) > 0:
        print(f"There were {len(logs)} non-critical errors detected during this audit. Please review {createLogsOutput()} for more details.")
    print(f"\nFinished. Please check {settings['outputDirectory']} for your results.")
      
if __name__ == "__main__":
    main()
