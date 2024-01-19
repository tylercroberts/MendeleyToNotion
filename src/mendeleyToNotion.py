  
"""
Author: Nandita Bhaskhar
End-to-end script for getting updates from Mendeley on to the Notion Database of your choice
"""

import sys
sys.path.append('/')

import time
import arrow
from loguru import logger

from pathlib import Path

from mendeley import Mendeley
from mendeley.session import MendeleySession
from mendeley.auth import MendeleyAuthorizationCodeTokenRefresher, MendeleyAuthorizationCodeAuthenticator

from notion_client import Client

from lib.port_utils import startInteractiveMendeleyAuthorization
from lib.port_utils import portMendeleyDocsToNotion

from lib.utils import *

from globalStore import constants

# arguments
parser = argparse.ArgumentParser()
parser.add_argument('--forceNewLogin', default = False, type = strToBool,
                    help = 'Should it be an interactive session with new login or not')
parser.add_argument('--secretsFilePath', default = None, type = noneOrStr,
                    help = 'secrets file path to be written or overwritten')
parser.add_argument("--useEnvironmentVariables", default=False, type=strToBool,
                    help= "Use when running inside `vlt run` mode. Will use environment variables for config instead")
parser.add_argument("--mendeleyFilePath", default='file:///C:/Users/Tyler/Documents/Mendeley%20Desktop/',type=str,
                   help="""Enter the path that Mendeley stores your files in. Can find it via: 
                        Tools->Options->File Organizer in Mendeley Desktop (NOT Reference Manager)""")
# main script
if __name__ == "__main__":

    logger.info('\n\n==========================================================')
    start = arrow.get(time.time()).to('US/Pacific').format('YYYY-MM-DD HH:mm:ss ZZ')
    logger.info('Starting at ' + str(start) + '\n\n')

    # parse all arguments
    args = parser.parse_args()

    # read arguments
    forceNewLogin = args.forceNewLogin
    secretsFilePath = args.secretsFilePath
    useEnvironmentVariables = args.useEnvironmentVariables
    mendeleyFilePath = args.mendeleyFilePath

    # open secrets
    if useEnvironmentVariables:
        secrets = {
            "clientId": os.environ["MENDELEY_CLIENT_ID"],
            "clientSecret": os.environ["MENDELEY_CLIENT_SECRET"],
            "redirectURL": os.environ["MENDELEY_CLIENT_REDIRECT_URL"]
        }
        secrets_notion = {
            "notionToken": os.environ["MENDELEY_NOTION_SECRET"],
            "databaseID": os.environ["MENDELEY_NOTION_DATABASE_ID"]
        }

    else:
        with open(Path(os.getcwd()) / constants.MENDELEY_SECRET_FILE, "r") as f:
            secrets = json.load(f)
        with open(Path(os.getcwd()) / constants.NOTION_SECRET_FILE, "r") as f:
            secrets_notion = json.load(f)

    # initialize mendeley object
    mendeley = Mendeley(client_id=secrets["clientId"], client_secret = secrets["clientSecret"], redirect_uri= secrets["redirectURL"])

    # interactive authorization flow if force new login or if token is absent
    if forceNewLogin or ("token" not in secrets):
        if useEnvironmentVariables:
            secrets['token'] = startInteractiveMendeleyAuthorization(mendeley)
        else:
            startInteractiveMendeleyAuthorization(mendeley, secretsFilePath)


    assert 'token' in secrets, "Token missing from secrets"

    # start mendeley session
    session = MendeleySession(mendeley, secrets["token"])

    # initialize an authenticator and a refresher
    authenticator = MendeleyAuthorizationCodeAuthenticator(mendeley, session.state())
    refresher = MendeleyAuthorizationCodeTokenRefresher(authenticator)

    # extract refresh token using refresher and activate session
    session = MendeleySession(mendeley, session.token, refresher=refresher)

    # initialize notion client and determine notion DB
    notion = Client(auth = secrets_notion['notionToken'])
    notionDB_id = secrets_notion['databaseID']

    # get list of iterator objects
    obj = []
    for item in session.groups.iter():
        obj.append(item.documents)
    obj.append(session.documents)

    # start porting from mendeley to notion
    noneAU = []
    for ob in obj:
        tmp = portMendeleyDocsToNotion(ob, notion, notionDB_id, mendeleyFilePath, noneAU)
        noneAU += tmp

    # check the entries with no authors
    try:
        logger.debug("The following entries have no authors:")
        for it in noneAU:
            logger.debug(it.title)
    except:
        logger.error('All mendeley entries have non-empty authors')

