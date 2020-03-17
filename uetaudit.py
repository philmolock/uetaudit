# Automated UET Audit
# Version 2.05 (03/17/2020)
# Phillip Molock | phmolock@microsoft.com
# For a list of commands  to use with this script type python uetaudit.py --options 

from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from urllib.parse import urlparse, unquote
from pprint import pprint
from random import randint, shuffle
from datetime import datetime
import time, os, csv, sys, getopt, re, json, requests
from getpass import getuser

# Overall script settings 
settings = {
    'homepage': None,
    'waitTimePerPage': 20,
    'pagesToCrawl': None,
    'txtFileLocation': None,
    'outputDirectory': 'output',
    'logsDirectory': 'logs',
    'customer': None,
    'version': 2.05,
    'versionDate':'03/17/2020'
}

# Capture any non-critical errors for print out
logs = []

# Tracking details for ATAM Script Tracker
class Atamlogger:
    def __init__(self, scriptid, scriptname, scriptowner, apikey):
        self.urlpath = 'https://techsolutionsapi.azurewebsites.net/v1/logs'
        self.headers = {'key': apikey}
        self.data = {'username': self.getUser(),
                    'scriptid': scriptid,
                    'scriptname': scriptname,
                    'scriptowner': scriptowner
                    }
        self.call()

    def call(self):
        try:
            r = requests.post(url=self.urlpath, headers=self.headers, json=self.data)
            print(r.text)
        except:
            print('error - request failed')

    def getUser(self):
        u = 'unknown'
        try:
            u = getuser()
        except:
            print('error - could not find username')
        finally:
            return u

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
                    choice = choice[:-1] if choice.endswith('/') else choice
                    settings['homepage'] = choice
            else:
                print(f"\n--Error Starting the Script--\n[Error] The homepage provided is not in proper format https://www.bing.com\n\t[Example Command | Just a homepage]\tpython uetaudit.py --homepage https://www.bing.com")    
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
            else:
                print(f"\n--Error Starting the Script--\n\n[Error] Please specify a text file when using the --file option. The file name {choice} does not end in .txt\n")
                printOptions()
        elif specificOption == '--options':
            printOptions()
            
    # Confirm settings provide the minimum information (at least a homepage and/or required pages to crawl)   
    if not settings['homepage'] and not settings['txtFileLocation']:
        print(f"\n--Error Starting the Script--\n[Error] No homepage or text file of URLs specified. The script has no URL(s) to analyze. Please specify a home page or a text file of URLs.\n\t[Example Command | Homepage plus crawl]\tpython uetaudit.py --homepage https://www.bing.com --pagecount 3\n\t[Example Command | A text file]\tpython uetaudit.py --file urls.txt")     
        printOptions()

    print(f"--UET Automated Audit--\n\tVersion: {settings['version']} {settings['versionDate']}\n\tFor a list of options: python uetaudit.py --options\n\n--Audit Details--\n\tAdvertiser Homepage: {settings['homepage']}\n\tPages to Crawl: {settings['pagesToCrawl']}\n\tText File: {settings['txtFileLocation']}\n\tCustomer Name: {getCustomerName()}")

# Read URLs from text file into requierdPages list
def getPagesFromTxtFile():
    pagesFromTxtFile = []
    try: 
        with open(settings['txtFileLocation'], 'r', errors='ignore') as txtIn:
            for line in txtIn:
                line = line.replace('\n','')
                pagesFromTxtFile.append(line)
    except Exception as e:
        print(f"\n--Error Starting the Script--\n\n[Error] There was an issue reading from {settings['txtFileLocation']}\nPlease insure you've provided the exact or relative path to the text file. It's recommended you place the text file in the same directory as the script.\n[Python Error Specifics] {e}\n")
        printOptions()
    return pagesFromTxtFile

# Print possible options you can include when running the script in the command shell
def printOptions():
    print(f"--Command Options--\n\t--homepage\tSpecify URL of homepage you'd like to audit\n\t--pagecount\tThe number of pages you'd like to randomly crawl\n\t--file\t\tThe location of a txt file containing URLs to crawl\n\t--customer\tCustomer name to be used with output file\n\t--options\tList available command options")
    quit()

def verifyHref(href, linksHistory, newLinks):
    hrefParse = urlparse(href)
    homePageParse = urlparse(settings['homepage'])
    sameNetloc = False
    pathOversaturated = False
    if hrefParse.netloc == homePageParse.netloc:        
        sameNetloc = True
    else:
        # some links will not have www.
        # break down href to netlocation by removing path and scheme and add www. to compare to homePage netloc
        trimmedHref = href.replace(hrefParse.path,'').replace(hrefParse.scheme,'').replace('://','')
        if 'www.' + trimmedHref == homePageParse.netloc:
            sameNetloc = True

    hrefPath = '/'.join(hrefParse.path.split('/')[:-1])
    if len(list(filter(lambda item: hrefPath in item, linksHistory))) > 5:
        pathOversaturated = True

    if (sameNetloc) and (not pathOversaturated) and (href not in set(linksHistory)) and (href != settings['homepage']) and (href not in set(newLinks)) and (not re.match('.*(/help|/login|/logon|/logonform|/form|/faq|/contact|/contactus|/customerservice|/customer-service|/account|/user|/logout|/careers)', href)) and (href != f"{settings['homepage']}/") and (not href.split('#')[0] == settings['homepage']) and (len(hrefParse.fragment) == 0):
        return True
    else:
        return False
# Get a new list of links to add to the linksQueue
def getNewLinks(links, linksHistory):
    newLinks = []
    randomLinks = []
    
    for link in links:
        try:
            href = link.get_attribute("href")
        except Exception as e:
            log = f"--Error While Running Script--\n\t[Error] Encountered error while trying to get href attribute of {link}. Skipping adding link.\n\t[Python Error] {e}"
            logs.append(log)
            continue
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

# Browse to a page and monitor the Chrome network performance for requests to bat.bing.com/action
def analyzePage(browser, page, **kwargs):
    startTime = datetime.now()
    returnNewLinks = kwargs.get('returnNewLinks', None)
    pageHistory = kwargs.get('pageHistory', None)
    uetEvents = []

    print(f"{page[:50]}...", end="\t")
    browser.get(page)
    time.sleep(randint(1,5))
    while (datetime.now() - startTime).seconds <= settings['waitTimePerPage']:
        documentReadyState = browser.execute_script("return document.readyState;") 
        uetq = browser.execute_script("if(typeof(uetq) == 'undefined'){return false;}else{return true;}") 
        if documentReadyState == 'complete' and uetq:
            for entry in browser.get_log('performance'):
                jsonEntry = json.loads(entry['message'])
                if jsonEntry['message']['method'].lower() == ('network.requestwillbesent'):
                    url = jsonEntry['message']['params']['request']['url']
                    if 'bat.bing.com/action' in url:
                        uetEvents.append(url)
            break
        else:
            time.sleep(5)
    print(f"{len(uetEvents)} UET Event{'s' if len(uetEvents) > 1 else ''}")
    if returnNewLinks and type(pageHistory) == list:
        potentialNewLinks = browser.find_elements_by_xpath("//a[@href]")
        newLinks = getNewLinks(potentialNewLinks, pageHistory)
        if len(newLinks) == 0:
            potentialNewLinks == browser.find_element_by_tag_name("a")
            newLinks = getNewLinks(potentialNewLinks, pageHistory)
        return uetEvents, newLinks
    else:
        return uetEvents

# Build out a dictionary of uet events for each page that needs to be audited
def getUetEventsByPage():
    uetEventsByPage = {}
    # Configure and open browser
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('log-level=3')
        # options.add_argument("--disable-extensions")
        # options.add_experimental_option("excludeSwitches", ["enable-automation"])
        # options.add_experimental_option('useAutomationExtension', False)
        caps = DesiredCapabilities.CHROME
        caps['goog:loggingPrefs'] = {'performance': 'ALL'}
        browser = webdriver.Chrome(desired_capabilities=caps, options=options)
    except Exception as e:
        print(f"--Error While Running Script--\n\t[Error] Encountered error while starting the automated browser.\n\t[Python Error] {e}")
    print("\n--Beginning Audit--\n")
    # Just analyzing the homepage
    if settings['homepage'] and not settings['pagesToCrawl'] and not settings['txtFileLocation']:
        print(f"[1/1]", end=' ')
        uetEventsByPage[settings['homepage']] = analyzePage(browser, settings['homepage'])
    # Analyzing the homepage and randomly crawling
    elif settings['homepage'] and settings['pagesToCrawl'] and not settings['txtFileLocation']:
        pageHistory = []
        pageQueue = [settings['homepage'],]
        pagesCrawled = 0
        while pagesCrawled <= settings['pagesToCrawl']:
            shuffle(pageQueue)
            currentPage = pageQueue[0]
            print(f"[{pagesCrawled + 1}/{settings['pagesToCrawl'] + 1}]", end=' ')
            uetEventsByPage[currentPage], newLinks = analyzePage(browser, currentPage, returnNewLinks = True, pageHistory = pageHistory)            
            pageHistory.append(currentPage)
            pageQueue.extend(newLinks)
            del(pageQueue[0])            
            pagesCrawled += 1
            if len(pageQueue) == 0:
                print(f"\tThere were no new links returned and zero links in the link queue. Quitting.")
                break
    # Analyzing pages in a txt file
    elif settings['txtFileLocation'] and not settings['homepage'] and not settings['pagesToCrawl']:
        pageQueue = getPagesFromTxtFile()
        pagesCrawled = 1
        for currentPage in pageQueue:
            print(f"[{pagesCrawled}/{len(pageQueue)}]", end=' ')
            uetEventsByPage[currentPage] = analyzePage(browser, currentPage)
            pagesCrawled += 1
    
    return uetEventsByPage

# Analyze uetevents from a page and return rows to output to the final report
def analyzeUetEvents(uetEvents, page):
    pageLoadDetected = False
    outputRows = []
    for uetEvent in uetEvents:
        analyzedUetEvent = {
            'tagId': None,
            'eventType': None,
            'eventAction': None,
            'eventCategory': None,
            'eventLabel': None,
            'eventValue': None,
            'goalValue': None,
            'goalCurrency': None,
            'prodId': None,
            'pageType': None,
            'opportunity': '',
        }
        # Pull tagId from ? front portion 
        analyzedUetEvent['tagId'] = uetEvent.split('?')[1].split('&')[0].split('ti=')[1]
        
        # Split uet event by & to review parameters
        uetEventSplit = uetEvent.split('&')
        for parameter in uetEventSplit:
            if parameter.startswith('evt='):
                analyzedUetEvent['eventType'] = unquote(parameter.split('evt=')[1])
            if parameter.startswith('ea='):
                analyzedUetEvent['eventAction'] = unquote(parameter.split('ea=')[1])
            if parameter.startswith('ec='):
                analyzedUetEvent['eventCategory'] = unquote(parameter.split('ec=')[1])
            if parameter.startswith('el='):
                analyzedUetEvent['eventLabel'] = unquote(parameter.split('el=')[1])
            if parameter.startswith('ev='):
                analyzedUetEvent['eventValue'] = unquote(parameter.split('ev=')[1])
            if parameter.startswith('gv='):
                analyzedUetEvent['goalValue'] = unquote(parameter.split('gv=')[1])
            if parameter.startswith('gc='):
                analyzedUetEvent['goalCurrency'] = unquote(parameter.split('gc=')[1])
            if parameter.startswith('prodid='):
                analyzedUetEvent['prodId'] = unquote(parameter.split('prodid=')[1])
            if parameter.startswith('pagetype='):
                analyzedUetEvent['pageType'] = unquote(parameter.split('pagetype=')[1])
        
        # Check for pageLoad
        if analyzedUetEvent['eventType'] == 'pageLoad':
            pageLoadDetected = True

        # pageType but no prodId
        if analyzedUetEvent['pageType'] and not analyzedUetEvent['prodId']:
            analyzedUetEvent['opportunity'] += "Product Audiences: pageType provided but no productId. "
        
        # no pageType but prodId
        if not analyzedUetEvent['pageType'] and analyzedUetEvent['prodId']:
            analyzedUetEvent['opportunity'] += "Product Audiences: productId provided but no pageType. "
        
        # goalCurrency but no goalValue
        if analyzedUetEvent['goalCurrency'] and not analyzedUetEvent['goalValue']:
            analyzedUetEvent['opportunity'] += "Variable Revenue: goalCurrency provided but no goalValue. "

        # custom event but at a minimum no goalVlaue
        if analyzedUetEvent['eventType'] == "custom" and not analyzedUetEvent['goalValue'] and not analyzedUetEvent['eventAction'] and not analyzedUetEvent['eventCategory'] and not analyzedUetEvent['eventLabel'] and not analyzedUetEvent['eventValue'] and not analyzedUetEvent['pageType'] and not analyzedUetEvent['prodId']:
            analyzedUetEvent['opportunity'] += "Custom Event: The event type is custom, but no additional values were provided (such as an eventAction or goalValue."
        
        # Put Custom Event Parameters into string
        customEventParameters = f"{'ea=' + analyzedUetEvent['eventAction'] + ' ' if analyzedUetEvent['eventAction'] else ''}{'ec=' + analyzedUetEvent['eventCategory'] + ' ' if analyzedUetEvent['eventCategory'] else ''}{'el=' + analyzedUetEvent['eventLabel'] + ' ' if analyzedUetEvent['eventLabel'] else ''}{'ev=' + analyzedUetEvent['eventValue'] + ' ' if analyzedUetEvent['eventValue'] else ''}{'gv=' + analyzedUetEvent['goalValue'] + ' ' if analyzedUetEvent['goalValue'] else ''}{'gc=' + analyzedUetEvent['goalCurrency'] + ' ' if analyzedUetEvent['goalCurrency'] else ''}{'pagetype=' + analyzedUetEvent['pageType'] + ' ' if analyzedUetEvent['pageType'] else ''}{'prodid=' + analyzedUetEvent['prodId'] + ' ' if analyzedUetEvent['prodId'] else ''}"
        
        # Add to outputRows which will be returned
        outputRows.append([page, analyzedUetEvent['tagId'], analyzedUetEvent['eventType'], customEventParameters, analyzedUetEvent['opportunity']])
    if not pageLoadDetected:
        outputRows.insert(0,[page,'','','','','No UET detected on page. Please make sure all pages are tagged with a UET pageLoad event.'])
    return outputRows

# Build the report generating output rows and writing to the report
def createReport(uetEventsByPage):
    try:
        os.mkdir(settings['outputDirectory'])
    except:
        pass
    customerName = getCustomerName()
    fileName = f"{settings['outputDirectory']}/UET Audit {customerName} {randint(100,999)}.csv"
    print(f"\nWriting report... {fileName}")
    with open(fileName, 'w', newline='') as csvOut:
        csvWriter = csv.writer(csvOut, delimiter=',')
        csvWriter.writerow(['Page','TagId', 'Event Type','Custom Event Parameters','Opportunity'])
        for page, uetEvents in uetEventsByPage.items():
            if len(uetEvents) == 0:
                csvWriter.writerow([page,'','','','','No UET detected on page. Please make sure all pages are tagged with a UET pageLoad event.'])
            else:
                outputRows = analyzeUetEvents(uetEvents, page)
                for outputRow in outputRows:
                    csvWriter.writerow(outputRow)
                
# Get customer name either from the homepage, --customer option, or return an empty string if nothing specified
def getCustomerName():
    if settings['customer']:
        return settings['customer']
    if not settings['customer'] and settings['homepage']:
        return urlparse(settings['homepage']).netloc.replace('.',' ')
    else:
        return ''

# if any logs exist, write them to a log output file
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
    print(f"Length of logs: {len(logs)}")
    return fileName

# Main
def main():
    l = Atamlogger(1001, 'uetaudit', 'phmolock', '82302af0')
    mergeSettings()
    uetEventsByPage = getUetEventsByPage()
    createReport(uetEventsByPage)
    createLogsOutput()
      
if __name__ == "__main__":
    main()
