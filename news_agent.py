from duckduckgo_search import DDGS
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

def get_news_snippets(ticker):
    """
    Searches for news related to litigation, liquidity, and bankruptcy risk.
    """
    snippets = []
    query = f"{ticker} litigation lawsuit liquidity bankruptcy news"
    
    try:
        results = DDGS().text(query, max_results=5)
        if results:
            for result in results:
               snippets.append(f"Title: {result['title']}\nLink: {result['href']}\nSnippet: {result['body']}")
    except Exception as e:
        print(f"Error searching news for {ticker}: {e}")
        return ["Error fetching news."]
        
    return snippets

def summarize_news(ticker, snippets, api_key=None):
    """
    Summarizes the news snippets using OpenAI if an API key is provided.
    """
    if not snippets:
        return "No news found."
    
    joined_snippets = "\n\n".join(snippets)
    
    if not api_key:
        return "API Key not provided. Returning raw snippets:\n\n" + joined_snippets

    if OpenAI is None:
        return "OpenAI library not installed. Returning raw snippets:\n\n" + joined_snippets

    try:
        client = OpenAI(api_key=api_key)
        
        prompt = (
            f"You are a financial analyst. Analyze the following news snippets for {ticker} "
            f"regarding litigation, liquidity issues, and bankruptcy risk.\n\n"
            f"{joined_snippets}\n\n"
            f"Provide a concise summary of the risks."
        )
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful financial assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"Error summarizing news: {e}\n\nRaw Snippets:\n{joined_snippets}"

if __name__ == "__main__":
    ticker = "AAPL"
    snippets = get_news_snippets(ticker)
    print("Snippets found:", len(snippets))
    print(summarize_news(ticker, snippets))
