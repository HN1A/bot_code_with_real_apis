import sys
sys.path.append('/opt/.manus/.sandbox-runtime')
from data_api import ApiClient
import logging

logger = logging.getLogger(__name__)
client = ApiClient()

async def get_stock_chart_data(symbol: str, range: str = "1mo", interval: str = "1d") -> dict | None:
    """Fetches stock chart data from Yahoo Finance API."""
    try:
        logger.info(f"Fetching stock data for {symbol} with range={range}, interval={interval}")
        # Use default values for most parameters for simplicity initially
        stock_data = await client.call_api_async(
            'YahooFinance/get_stock_chart',
            query={'symbol': symbol, 'range': range, 'interval': interval, 'includeAdjustedClose': True}
        )
        
        if stock_data and stock_data.get("chart") and stock_data["chart"].get("result"):
            logger.info(f"Successfully fetched stock data for {symbol}")
            return stock_data["chart"]["result"][0] # Return the first result object
        else:
            logger.error(f"Failed to fetch valid stock data for {symbol}. Response: {stock_data}")
            return None
    except Exception as e:
        logger.error(f"Error calling Yahoo Finance API for {symbol}: {str(e)}")
        return None

# You can add functions for other Yahoo Finance APIs here later
# async def get_stock_holders_data(symbol: str) -> dict | None:
#     ...
# async def get_stock_insights_data(symbol: str) -> dict | None:
#     ...



async def get_stock_holders_data(symbol: str, region: str = "US") -> dict | None:
    """Fetches stock holder data from Yahoo Finance API."""
    try:
        logger.info(f"Fetching stock holders data for {symbol} in region {region}")
        holders_data = await client.call_api_async(
            'YahooFinance/get_stock_holders',
            query={'symbol': symbol, 'region': region}
        )
        
        if holders_data and holders_data.get("quoteSummary") and holders_data["quoteSummary"].get("result"):
            logger.info(f"Successfully fetched stock holders data for {symbol}")
            # Access the insiderHolders part
            insider_holders = holders_data["quoteSummary"]["result"][0].get("insiderHolders")
            if insider_holders:
                 return insider_holders
            else:
                 logger.warning(f"No insider holders data found for {symbol}")
                 return None
        else:
            logger.error(f"Failed to fetch valid stock holders data for {symbol}. Response: {holders_data}")
            return None
    except Exception as e:
        logger.error(f"Error calling Yahoo Finance Holders API for {symbol}: {str(e)}")
        return None

async def get_stock_insights_data(symbol: str) -> dict | None:
    """Fetches stock insights data from Yahoo Finance API."""
    try:
        logger.info(f"Fetching stock insights data for {symbol}")
        insights_data = await client.call_api_async(
            'YahooFinance/get_stock_insights',
            query={'symbol': symbol}
        )
        
        if insights_data and insights_data.get("finance") and insights_data["finance"].get("result"):
            logger.info(f"Successfully fetched stock insights data for {symbol}")
            return insights_data["finance"]["result"] # Return the main result object
        else:
            logger.error(f"Failed to fetch valid stock insights data for {symbol}. Response: {insights_data}")
            return None
    except Exception as e:
        logger.error(f"Error calling Yahoo Finance Insights API for {symbol}: {str(e)}")
        return None

async def get_stock_sec_filing_data(symbol: str, region: str = "US") -> dict | None:
    """Fetches stock SEC filing data from Yahoo Finance API."""
    try:
        logger.info(f"Fetching SEC filing data for {symbol} in region {region}")
        filing_data = await client.call_api_async(
            'YahooFinance/get_stock_sec_filing',
            query={'symbol': symbol, 'region': region}
        )
        
        if filing_data and filing_data.get("quoteSummary") and filing_data["quoteSummary"].get("result"):
            logger.info(f"Successfully fetched SEC filing data for {symbol}")
            # Access the secFilings part
            sec_filings = filing_data["quoteSummary"]["result"][0].get("secFilings")
            if sec_filings:
                return sec_filings
            else:
                logger.warning(f"No SEC filing data found for {symbol}")
                return None
        else:
            logger.error(f"Failed to fetch valid SEC filing data for {symbol}. Response: {filing_data}")
            return None
    except Exception as e:
        logger.error(f"Error calling Yahoo Finance SEC Filing API for {symbol}: {str(e)}")
        return None

async def get_stock_analyst_reports(symbol: str, region: str = "US") -> list | None:
    """Fetches analyst reports (what analysts are saying) from Yahoo Finance API."""
    try:
        logger.info(f"Fetching analyst reports for {symbol} in region {region}")
        report_data = await client.call_api_async(
            'YahooFinance/get_stock_what_analyst_are_saying',
            query={'symbol': symbol, 'region': region}
        )
        
        if report_data and report_data.get("result"):
            logger.info(f"Successfully fetched analyst reports for {symbol}")
            # The result is an array, potentially with multiple entries if multiple symbols were queried (though we query one)
            # We are interested in the 'hits' within the first result item
            if report_data["result"] and report_data["result"][0].get("hits"):
                return report_data["result"][0]["hits"]
            else:
                logger.warning(f"No analyst report hits found for {symbol}")
                return None
        else:
            logger.error(f"Failed to fetch valid analyst reports for {symbol}. Response: {report_data}")
            return None
    except Exception as e:
        logger.error(f"Error calling Yahoo Finance Analyst Reports API for {symbol}: {str(e)}")
        return None



async def get_linkedin_profile(username: str) -> dict | None:
    """Fetches LinkedIn profile data using the provided API."""
    try:
        logger.info(f"Fetching LinkedIn profile for username: {username}")
        profile_data = await client.call_api_async(
            'LinkedIn/get_user_profile_by_username',
            query={'username': username}
        )
        
        # Check if the API call was successful and data exists
        if profile_data and profile_data.get("success") and profile_data.get("data"):
            logger.info(f"Successfully fetched LinkedIn profile for {username}")
            return profile_data["data"] # Return the data part of the response
        elif profile_data and not profile_data.get("success"):
            logger.error(f"LinkedIn API returned an error for {username}: {profile_data.get('message')}")
            return None
        else:
            logger.error(f"Failed to fetch valid LinkedIn profile data for {username}. Response: {profile_data}")
            return None
    except Exception as e:
        logger.error(f"Error calling LinkedIn API for {username}: {str(e)}")
        return None

