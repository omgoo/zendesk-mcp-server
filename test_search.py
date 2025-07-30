import os
import json
from zendesk_mcp_server.zendesk_client import ZendeskClient

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Initialize client
client = ZendeskClient(
    subdomain=os.getenv('ZENDESK_SUBDOMAIN'),
    email=os.getenv('ZENDESK_EMAIL'),
    token=os.getenv('ZENDESK_API_KEY')
)

def print_result(name, result):
    print(f"\n=== {name} ===")
    print(json.dumps(result, indent=2))
    print("\n")

# Test 1: Basic search with defaults
print_result("Basic Search", 
    client.search_tickets(query="status:open")
)

# Test 2: Detailed search with full descriptions
print_result("Detailed Search",
    client.search_tickets(
        query="status:open",
        compact=False,
        include_description=True,
        limit=5
    )
)

# Test 3: Summary mode for large datasets
print_result("Summary Mode",
    client.search_tickets(
        query="status:open",
        summary_mode=True
    )
)

# Test 4: Categorized search
print_result("Categorized Search",
    client.search_tickets(
        query="status:open",
        categorize=True,
        limit=10
    )
)

# Test 5: Pagination test
print_result("Pagination Test",
    client.search_tickets(
        query="status:open",
        limit=5,
        page=2
    )
)

# Test 6: Size management test
print_result("Size Management Test",
    client.search_tickets(
        query="status:open",
        include_description=True,
        max_response_size=1000  # Very small to force truncation
    )
)