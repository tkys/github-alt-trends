import os
import requests
import json
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI  # Assuming OpenAI, adjust if using another LLM provider
from dotenv import load_dotenv

# Load environment variables (for API keys)
load_dotenv()

# --- Constants ---
GITHUB_API_URL = "https://api.github.com/search/repositories"
# Define AI/LLM exclusion keywords (adjust as needed)
AI_EXCLUDE_KEYWORDS = [
    "ai", "llm", "artificial-intelligence", "deep-learning",
    "machine-learning", "neural-network", "chatbot",
    "language-model", "nlp", "computer-vision"
]
# Filtering criteria
MIN_STARS_GAINED_LAST_7_DAYS = 50
MAX_CONTRIBUTORS = 3
OUTPUT_DIR = "docs"
TEMPLATE_DIR = "templates"
TEMPLATE_NAME = "index.html.j2"
OUTPUT_HTML_FILE = os.path.join(OUTPUT_DIR, "index.html")

# --- GitHub API Interaction ---
def fetch_trending_repositories():
    """Fetches potentially trending repositories from GitHub API."""
    # TODO: Implement logic to search for recently active/created repos
    # Consider searching based on creation date, update date, or specific topics
    # This needs refinement based on how to best discover potential candidates
    # For now, let's use a placeholder query (e.g., pushed within last month)
    # Search for repositories created in the last year with more than 20 stars
    one_year_ago = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
    query = f"stars:>20 created:>{one_year_ago}"
    params = {
        "q": query,
        "sort": "updated",
        "order": "desc",
        "per_page": 100 # Fetch a decent number to filter through
    }
    headers = {"Accept": "application/vnd.github.v3+json"}
    # Add GitHub token if available for higher rate limits
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    print(f"Fetching repositories with query: {query}")
    try:
        response = requests.get(GITHUB_API_URL, headers=headers, params=params)
        response.raise_for_status() # Raise an exception for bad status codes
        print(f"Fetched {len(response.json().get('items', []))} repositories.")
        return response.json().get("items", [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching GitHub repositories: {e}")
        return []

def get_repository_details(repo_api_url, repo_data_from_search):
    """Fetches detailed information (contributors, topics) for a single repository."""
    details = {
        "stars_last_7_days": -1, # Placeholder - Accurate calculation is complex via API
        "contributors_count": 999, # Default to a high number if fetch fails
        "topics": repo_data_from_search.get("topics", []) # Get topics from search results first
    }
    headers = {"Accept": "application/vnd.github.v3+json"}
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    # --- Fetch Contributors Count ---
    # Efficiently get count using pagination link header
    contributors_url = f"{repo_api_url}/contributors?per_page=1&anon=true"
    try:
        print(f"  - Fetching contributors count for {repo_data_from_search['html_url']}...")
        response = requests.get(contributors_url, headers=headers, timeout=10)
        response.raise_for_status()
        link_header = response.headers.get("Link")
        if link_header:
            # Find the 'last' page link and extract the page number
            links = requests.utils.parse_header_links(link_header)
            for link in links:
                if link.get("rel") == "last":
                    # Extract page number from url like ...?page=XXX
                    page_num_str = link["url"].split('page=')[-1].split('&')[0]
                    if page_num_str.isdigit():
                        details["contributors_count"] = int(page_num_str)
                        print(f"    - Contributors count: {details['contributors_count']}")
                        break
            else: # If 'last' link not found, it means only one page
                 # Check if the response body (first page) contains any contributors
                if response.json():
                    details["contributors_count"] = len(response.json()) # Should be 1 if not empty
                    print(f"    - Contributors count (single page): {details['contributors_count']}")
                else:
                     details["contributors_count"] = 0 # No contributors found
                     print(f"    - Contributors count (single page, empty): 0")

        else: # No Link header means 0 or 1 contributor if the body is not empty
            if response.json():
                 details["contributors_count"] = len(response.json()) # Should be 1
                 print(f"    - Contributors count (no link header): {details['contributors_count']}")
            else:
                 details["contributors_count"] = 0
                 print(f"    - Contributors count (no link header, empty): 0")


    except requests.exceptions.RequestException as e:
        print(f"    - Error fetching contributors for {repo_data_from_search['html_url']}: {e}")
        # Keep default high count

    # --- Fetch Topics (if not present in search results) ---
    # Usually included in search results, but fetch repo details as fallback if needed
    if not details["topics"]:
        try:
            print(f"  - Fetching repo details (for topics) for {repo_data_from_search['html_url']}...")
            response = requests.get(repo_api_url, headers=headers, timeout=10)
            response.raise_for_status()
            details["topics"] = response.json().get("topics", [])
            print(f"    - Topics: {details['topics']}")
        except requests.exceptions.RequestException as e:
            print(f"    - Error fetching repo details for {repo_data_from_search['html_url']}: {e}")


    # --- Star Growth (Placeholder/Alternative Idea) ---
    # Accurately getting stars gained in the last 7 days via API is complex and requires
    # many API calls (potentially hitting rate limits).
    # Possible alternatives:
    # 1. Use current star count + creation date: Filter for repos created recently (e.g., last year)
    #    with a minimum star count (e.g., > 100).
    # 2. Simplify the criteria: Just check if the current star count exceeds a threshold.
    # 3. Use external APIs/services (adds dependency).
    # For now, we'll keep the placeholder value (-1) and the filtering logic will need adjustment.
    print(f"  - Note: 'stars_last_7_days' is currently a placeholder (-1). Filtering logic needs adjustment.")


    return details

# --- Filtering Logic ---
def filter_repositories(repositories):
    """Filters repositories based on defined criteria."""
    filtered_repos = []
    client = None
    if os.getenv("OPENAI_API_KEY"): # Initialize LLM client only if key exists
        client = OpenAI()

    print(f"Filtering {len(repositories)} repositories...")
    count = 0
    for repo in repositories:
        count += 1
        print(f"\nProcessing repo {count}/{len(repositories)}: {repo.get('html_url', 'N/A')}")

        # Fetch detailed info (replace placeholder)
        # Pass the specific API URL and the repo data from search results
        details = get_repository_details(repo["url"], repo)

        # --- Stage 1: Keyword Filtering ---
        repo_topics = [topic.lower() for topic in details.get("topics", [])]
        repo_desc = (repo.get("description") or "").lower()
        found_keyword = False
        for keyword in AI_EXCLUDE_KEYWORDS:
            if keyword in repo_topics or keyword in repo_desc:
                print(f"  - Excluded by keyword: '{keyword}'")
                found_keyword = True
                break
        if found_keyword:
            continue
        print("  - Passed keyword filter.")

        # --- Check Growth and Contributor Criteria ---
        stars_gained = details.get("stars_last_7_days", 0)
        contributors = details.get("contributors_count", 999)

        # Star count filtering is now handled by the initial GitHub API query (stars:>20)
        # The 'stars_last_7_days' logic remains complex and is not implemented here.

        if contributors > MAX_CONTRIBUTORS:
            print(f"  - Excluded by contributors: {contributors} > {MAX_CONTRIBUTORS}")
            continue
        print(f"  - Passed contributors filter ({contributors}).")

        # --- Stage 2: LLM Filtering (if applicable and needed) ---
        # TODO: Decide when to apply LLM filtering (e.g., always after stage 1, or only if uncertain)
        # For now, let's assume we apply it if the client is available
        if client:
            print("  - Applying LLM filter...")
            is_ai_related = check_ai_related_with_llm(client, repo)
            if is_ai_related:
                print("  - Excluded by LLM filter.")
                continue
            print("  - Passed LLM filter.")
        else:
            print("  - LLM client not available, skipping LLM filter.")


        # If all filters passed
        print(f"  - Repository PASSED all filters: {repo.get('html_url', 'N/A')}")

        # Translate description if client is available
        original_description = repo.get("description", "No description provided.")
        translated_description = original_description
        if client:
             translated_description = translate_text_with_llm(client, original_description)

        filtered_repos.append({
            "name": repo.get("name", "Unknown"),
            "url": repo.get("html_url", "#"),
            "description": original_description,
            "description_ja": translated_description, # Add Japanese description
            "language": repo.get("language"),
            "stars": repo.get("stargazers_count"),
            "stars_last_7_days": stars_gained, # Add details used for filtering
            "contributors": contributors,
            "topics": details.get("topics", []) # Add topics here
        })

    print(f"\nFiltering complete. Found {len(filtered_repos)} matching repositories.")
    return filtered_repos

# --- LLM Interaction ---
def check_ai_related_with_llm(client, repo):
    """Uses LLM to determine if a repository is primarily AI/LLM related."""
    # Ensure client is initialized before calling this function
    if not client:
        print("    - LLM client not initialized. Skipping LLM check.")
        return False # Default to not excluding if client is missing

    repo_name = repo.get('name', 'Unknown Repo')
    print(f"    - Prompting LLM for: {repo_name}")

    # Construct the prompt
    prompt = f"""
    Analyze the following GitHub repository information:
    Name: {repo_name}
    Description: {repo.get('description', 'N/A')}
    Topics: {', '.join(repo.get('topics', []))}

    Is this repository primarily focused on AI, LLM, Machine Learning, Deep Learning,
    Natural Language Processing, or Computer Vision?
    Answer with only "Yes" or "No".
    """

    try:
        # --- Actual OpenAI API Call ---
        response = client.chat.completions.create(
            model="gpt-4o-mini", # Or another suitable model like gpt-3.5-turbo
            messages=[
                {"role": "system", "content": "You are a helpful assistant that determines if a GitHub repository is primarily focused on AI/LLM based on its metadata. Answer only with 'Yes' or 'No'."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0, # For deterministic output
            max_tokens=5
        )
        llm_response = response.choices[0].message.content.strip().lower()
        print(f"    - LLM Response: {llm_response}")
        # --- End Actual OpenAI API Call ---

        # Check response carefully
        if "yes" in llm_response:
            return True
        elif "no" in llm_response:
            return False
        else:
            print(f"    - Warning: Unexpected LLM response: '{llm_response}'. Defaulting to not excluding.")
            return False # Default to not excluding on unexpected response

    except Exception as e:
        print(f"    - Error during LLM check for {repo_name}: {e}")
        return False # Default to not excluding if LLM check fails

def translate_text_with_llm(client, text):
    """Uses LLM to translate text to Japanese."""
    if not client or not text:
        return text # Return original text if no client or text

    print(f"    - Translating description (first ~100 chars): {text[:100]}...")
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that translates English text to Japanese."},
                {"role": "user", "content": f"Translate the following GitHub repository description to Japanese:\n\n{text}"}
            ],
            temperature=0.7,
            max_tokens=200 # Adjust token limit as needed
        )
        translated_text = response.choices[0].message.content.strip()
        print(f"    - Translation: {translated_text[:100]}...")
        return translated_text
    except Exception as e:
        print(f"    - Error during translation: {e}")
        return text # Return original text on error


# --- HTML Generation ---
def generate_html(repositories):
    """Generates the static HTML file from a template."""
    if not os.path.exists(TEMPLATE_DIR):

        print(f"Error: Template directory '{TEMPLATE_DIR}' not found.")
        return
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created output directory: {OUTPUT_DIR}")

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    try:
        template = env.get_template(TEMPLATE_NAME)
    except Exception as e:
        print(f"Error loading template '{TEMPLATE_NAME}': {e}")
        return

    html_content = template.render(
        repositories=repositories,
        last_updated=datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    )

    try:
        with open(OUTPUT_HTML_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Successfully generated HTML file: {OUTPUT_HTML_FILE}")
    except IOError as e:
        print(f"Error writing HTML file '{OUTPUT_HTML_FILE}': {e}")


# --- Main Execution ---
if __name__ == "__main__":
    print("Starting GitHub Alt Trends generation...")
    # 1. Fetch repositories
    raw_repositories = fetch_trending_repositories()

    # 2. Filter repositories
    if raw_repositories:
        filtered_repositories = filter_repositories(raw_repositories)
    else:
        filtered_repositories = []

    # 3. Generate HTML
    generate_html(filtered_repositories)

    print("GitHub Alt Trends generation finished.")

