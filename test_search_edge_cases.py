import os
import json
from zendesk_mcp_server.zendesk_client import ZendeskClient
from dotenv import load_dotenv

load_dotenv()

# Initialize client
client = ZendeskClient(
    subdomain=os.getenv('ZENDESK_SUBDOMAIN'),
    email=os.getenv('ZENDESK_EMAIL'),
    token=os.getenv('ZENDESK_API_KEY')
)

def test_edge_case(name, **kwargs):
    try:
        result = client.search_tickets(**kwargs)
        print(f"✅ {name}: SUCCESS")
        print(f"   - Data type: {type(result)}")
        if isinstance(result, dict):
            print(f"   - Keys: {list(result.keys())}")
            if 'data' in result and 'tickets' in result['data']:
                print(f"   - Tickets returned: {len(result['data']['tickets'])}")
            elif 'tickets' in result:
                print(f"   - Tickets returned: {len(result['tickets'])}")
            else:
                print(f"   - No tickets key found")
        print()
    except Exception as e:
        print(f"❌ {name}: FAILED - {str(e)}")
        print()

# Test edge cases
print("=== Testing Edge Cases ===\n")

# Test 1: Minimal parameters
test_edge_case("Minimal Parameters", query="status:open")

# Test 2: All parameters specified
test_edge_case("All Parameters", 
               query="status:open", 
               limit=5, 
               compact=True, 
               include_description=False,
               sort_by="created_at",
               sort_order="desc",
               max_response_size=1000,
               summary_mode=False,
               categorize=True)

# Test 3: Summary mode only
test_edge_case("Summary Mode", query="status:open", summary_mode=True)

# Test 4: Large limit with size restriction
test_edge_case("Size Management", query="status:open", limit=50, max_response_size=2000)

# Test 5: Categorization with detailed data
test_edge_case("Categorization + Details", 
               query="status:open", 
               categorize=True, 
               compact=False, 
               include_description=True,
               limit=3)

# Test 6: Empty query (should still work with type:ticket prepended)
test_edge_case("Empty Query", query="")

print("=== All Tests Complete ===")