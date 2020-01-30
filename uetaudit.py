# Automated UET Audit
# Version 0.1 (1/30/2020)
# Phillip Molock | phmolock@microsoft.com
# For a list of commands  to use with this script type python uetaudit.py --options 

# To do
# 4. Find a way to disable the crawling functionality 
# 5. Build out documentation 

from selenium import webdriver
from browsermobproxy import Server
from urllib.parse import urlparse
import time, os, csv, sys, getopt, re
from pprint import pprint
from random import randint, shuffle

settings = {
    'homepage': '',
    'waitTimePerPage': 10,
    'pagesToCrawl': 3,
    'requiredPagesToCrawl': [],
    'readURLsFromTxtFile?': False,
    'txtFileLocation': None,
    'outputDirectory': 'output',
    'outputToEmail?': False,
    'spider?': True,
    'version': 0.1
}

def readPagesFromText(txtFileLocation):
    requiredPages = []
    with open(txtFileLocation, 'r', errors='ignore') as txtIn:
        for line in txtIn:
            line = line.replace('\n','')
            requiredPages.append(line)
    return requiredPages

def mergeSettings():
    argv = sys.argv[1:]
    opts, args = getopt.getopt(argv, None, longopts=['homepage=','spider=','time=','file=', 'email=', 'pagecount=','options'])    
    for opt in opts:
        if opt[0] == '--homepage':
            parsedUrl = urlparse(opt[1])
            if parsedUrl.scheme != '' and parsedUrl.netloc != '' and re.match('.*\..*\..*', parsedUrl.netloc):
                settings['homepage'] = opt[1]
        elif opt[0] == '--pagecount':
            settings['pagesToCrawl'] = int(opt[1])
        elif opt[0] == '--file':
            settings['txtFileLocation'] = opt[1]
            settings['requiredPagesToCrawl'] = readPagesFromText(settings['txtFileLocation'])
        elif opt[0] == '--email':
            if opt[1].lower() == 'true' or opt[1].lower() == 'yes':
                settings['outputToEmail?'] = True
            if opt[1].lower() == 'false' or opt[1].lower() == 'no':
                settings['outputToEmail?'] = False
        elif opt[0] == '--options':
            printOptions()
            quit()
        
    if settings['homepage']  == '':
        print(f"\n--Error Starting the Script--\n[Error] Specify a homepage to audit using the full URL (https:// *AND* www.example.com):\n[Example Command]\tpython uetaudit.py --homepage https://www.bing.com\n")
        printOptions()
        quit()

    print(f"--UET Automated Audit--\n\tVersion:{settings['version']} (1/30/2020)\n\tFor a list of options: python uetaudit.py --options\n\n--Audit Details--\n\tAdvertiser Homepage: {settings['homepage']}\n\tPages to Crawl: {settings['pagesToCrawl']}\n\tText File: {settings['txtFileLocation']}\n\tRequired Pages: {settings['requiredPagesToCrawl']}\n\tOutput to Email: {settings['outputToEmail?']}")

def printOptions():
    print(f"--Command Options--\n\t--homepage\tSpecify URL of homepage you'd like to audit\n\t--pagecount\tThe number of pages you'd like to randomly crawl (above and beyond the homepage or pages you've specified in a txt file)\n\t--file\t\tThe location of a txt file containing URLs to crawl\n\t--email\t\tEnable/disable results in email format (True/False)\n\t--options\tList available command options")

def verifyHref(href, linksHistory, newLinks):
    hrefNetloc = urlparse(href).netloc
    homePageNetloc = urlparse(settings['homepage']).netloc
    if hrefNetloc == homePageNetloc and href not in linksHistory and href != settings['homepage'] and href not in newLinks and not re.match('.*(/help|/login|/faq|/contact|/contactus|/customerservice|/customer-service|/account)', href):
        return True
    else:
        return False

def getNewLinks(links, linksHistory):
    newLinks = []
    randomLinks = []
    
    for link in links:
        href = link.get_attribute("href")
        if verifyHref(href, linksHistory, newLinks):
            newLinks.append(href)
    
    if len(newLinks) > 3:
        shuffle(newLinks)
        for link in newLinks:
            if len(randomLinks) < 3:
                if link not in randomLinks:
                    randomLinks.append(link)
            else:
                break
    else:
        return newLinks

    return randomLinks

def crawlLinkQueue():
    server = Server('browsermob-proxy-2.1.4\\bin\\browsermob-proxy.bat')
    server.start()
    proxy = server.create_proxy()
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument(f"--proxy-server={proxy.proxy}")
    chrome_options.add_argument(f"--ignore-certificate-errors")
    browser = webdriver.Chrome(options = chrome_options)
    linksHistory = []
    requiredLinksQueue = [settings['homepage']] + settings['requiredPagesToCrawl']
    linksQueue = []
    harDict = {}
    settings['pagesToCrawl'] += len(requiredLinksQueue)
    # Crawl required links, which is the home page plus any links imported from a file, builds initial random linksQueue
    for link in requiredLinksQueue:
        if link not in linksHistory:
            proxy.new_har(link)
            print(f"Crawling... {link}")
            browser.get(link)
            time.sleep(settings['waitTimePerPage'])
            links = browser.find_elements_by_xpath("//a[@href]")
            harDict[link] = []
            for entry in proxy.har['log']['entries']:
                if 'bat.bing.com/action' in entry['request']['url']:
                    harDict[link].append(entry)            
            newLinks = getNewLinks(links, linksHistory)
            linksQueue.extend(newLinks)
            linksHistory.append(link)
    # randomly crawl through the linksQueue (while adding to it) until you've hit the pagecount required 
    while True:
        if len(linksHistory) == settings['pagesToCrawl']:
            return harDict
        else:
            shuffle(linksQueue)
            link = linksQueue[0]
            if link not in linksHistory:
                proxy.new_har(link)
                print(f"Crawling... {link}")
                browser.get(link)
                time.sleep(settings['waitTimePerPage'])
                links = browser.find_elements_by_xpath("//a[@href]")
                harDict[link] = []
                for entry in proxy.har['log']['entries']:
                    if 'bat.bing.com/action' in entry['request']['url']:
                        harDict[link].append(entry)
                newLinks = getNewLinks(links, linksHistory)
                del(linksQueue[0])
                linksQueue.extend(newLinks)
                linksHistory.append(link)
                
                

def analyzeQueryString(queryStrings):
    queryStringAnalysis = {
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

    for queryString in queryStrings:
        if queryString['name'] == 'evt':
            queryStringAnalysis['eventType'] = queryString['value']
        elif queryString['name'] == 'ti':
            queryStringAnalysis['tagId'] = queryString['value']
        elif queryString['name'] == 'ec':
            queryStringAnalysis['eventCategory'] = queryString['value']
        elif queryString['name'] == 'el':
            queryStringAnalysis['eventLabel'] = queryString['value']
        elif queryString['name'] == 'ev':
            queryStringAnalysis['eventValue'] = queryString['value']
        elif queryString['name'] == 'ea':
            queryStringAnalysis['eventAction'] = queryString['value']
        elif queryString['name'] == 'gv':
            queryStringAnalysis['goalValue'] = queryString['value']
        elif queryString['name'] == 'gc':
            queryStringAnalysis['goalCurrency'] = queryString['value']
        elif queryString['name'] == 'pagetype':
            queryStringAnalysis['pageType'] = queryString['value']
        elif queryString['name'] == 'prodid':
            queryStringAnalysis['prodId'] = queryString['value']
            

    return queryStringAnalysis

def createUetOpportunity(harAnalysis, httpRespStatusCode):
    opportunity=""
    evt = harAnalysis['eventType']
    ti = harAnalysis['tagId']
    ec = harAnalysis['eventCategory']
    el = harAnalysis['eventLabel']
    ea = harAnalysis['eventAction']
    ev = harAnalysis['eventValue']
    gv = harAnalysis['goalValue']
    gc = harAnalysis['goalCurrency']
    pageType = harAnalysis['pageType']
    prodId = harAnalysis['prodId']
    

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
            if pageType.lower() not in ['home','category','other','purchase','searchresults','product','cart']:
                opportunity += f"The pagetype {pageType} is not a valid pagetype. "
            if len(invalidProdIds) > 0:
                opportunity += f"The prodIds {invalidProdIds} are invalid (ASCII only, max length of 50 characters)."
        # Check if no pageType provided but prodId provided
        elif not pageType and prodId:
            opportunity += "ProdId provided but no pageType. "
        elif pageType and not prodId:
            opportunity += "pageType provided but no prodId. "

    return opportunity

def validateProdId(prodId):
    invalidProdIds = []
    prodIdSplit = prodId.split(',')
    for prodIdToCheck in prodIdSplit:
        if not prodIdToCheck.isascii():
            invalidProdIds.append(prodIdToCheck)
        elif len(prodIdToCheck) > 50:
            invalidProdIds.append(prodIdToCheck)
    return set(invalidProdIds)


def analyzeHarDict(harDict):
    reportResults = [['Page','TagId','Event Type','Query String Details','HTTP Response Code','Opportunity'],]
    for page, entries in harDict.items():
        pageLoadDetected = False
        if len(entries) == 0:
            # no UET detected on this page
            newReportRow = [
                page,
                '',
                '',
                '',
                'No UET tags detected. Please insure UET is properly placed on every page.'
            ]
            reportResults.append(newReportRow)

        for entry in entries:
            harAnalysis = analyzeQueryString(entry['request']['queryString'])
            evt = harAnalysis['eventType']
            ti = harAnalysis['tagId']
            ec = harAnalysis['eventCategory']
            el = harAnalysis['eventLabel']
            ea = harAnalysis['eventAction']
            ev = harAnalysis['eventValue']
            gv = harAnalysis['goalValue']
            gc = harAnalysis['goalCurrency']
            pageType = harAnalysis['pageType']
            prodId = harAnalysis['prodId']
            httpRespStatusCode = entry['response']['status']

            if evt == 'pageLoad':
                pageLoadDetected = True 
            
            newReportRow = [
                page,
                ti, 
                evt,
                f"{'ea='+ ea + ' ' if ea else ''}{'ev=' + ev + ' ' if ev else ''}{'ec=' + ec + ' ' if ec else ''}{'el=' + el + ' ' if el else ''}{'gv=' + gv + ' ' if gv else ''}{'gc=' + gc + ' ' if gc else ''}{'pagetype=' + pageType + ' ' if pageType else ''}{'prodid=' + prodId + ' ' if prodId else ''}",
                httpRespStatusCode,
                createUetOpportunity(harAnalysis, entry['response']['status'])
            ]
            reportResults.append(newReportRow)
        
        if not pageLoadDetected and len(entries) > 0:
            newReportRow = [
                page,
                '',
                '',
                '',
                'No UET pageLoad tag detected. Please insure UET is properly placed on every page.'
            ]
            reportResults.append(newReportRow)
            
    return reportResults

def createOutput(reportResults):
    try:
        os.mkdir(settings['outputDirectory'])
    except:
        pass
    customerName = urlparse(settings['homepage']).netloc.replace('.',' ')
    fileName = f"{settings['outputDirectory']}/UET Audit {customerName} {randint(0,10000)}.csv"
    print(f"\nWriting report... {fileName}")
    with open(fileName, 'w', newline='') as csvOut:
        csvWriter = csv.writer(csvOut, delimiter=',')
        for row in reportResults:
            csvWriter.writerow(row)

def main():
    mergeSettings()
    harDict = crawlLinkQueue()
    reportResults = analyzeHarDict(harDict)
    createOutput(reportResults)
    print(f"\nFinished. Please check {settings['outputDirectory']} for your results.")

            
            
if __name__ == "__main__":
    main()
