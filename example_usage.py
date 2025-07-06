#!/usr/bin/env python3
"""
Example usage script for the Document Search Application.

This script demonstrates how to use the API endpoints.
"""

import asyncio
import json
import sys
from pathlib import Path
import httpx
import time

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

BASE_URL = "http://localhost:8000"


async def main():
    """Main example function."""
    print("=== Document Search Application Example ===\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # 1. Check application health
        print("1. Checking application health...")
        try:
            response = await client.get(f"{BASE_URL}/api/v1/health")
            health_data = response.json()
            print(f"   Status: {health_data['status']}")
            print(f"   Services: {health_data['services']}")
            print(f"   Version: {health_data['version']}")
        except Exception as e:
            print(f"   Error: {e}")
            print("   Make sure the application is running on localhost:8000")
            return
        
        print()
        
        # 2. Get indexing statistics
        print("2. Getting indexing statistics...")
        try:
            response = await client.get(f"{BASE_URL}/api/v1/admin/stats")
            if response.status_code == 200:
                stats = response.json()
                print(f"   Total documents: {stats['total_documents']}")
                print(f"   Documents by type: {stats['documents_by_type']}")
                print(f"   Total size: {stats['total_size_mb']} MB")
            else:
                print(f"   Error getting stats: {response.status_code}")
        except Exception as e:
            print(f"   Error: {e}")
        
        print()
        
        # 3. Trigger reindexing (optional)
        print("3. Triggering document reindexing...")
        print("   Note: This will run in the background")
        try:
            response = await client.post(f"{BASE_URL}/api/v1/admin/reindex")
            if response.status_code == 200:
                result = response.json()
                print(f"   {result['message']}")
            else:
                print(f"   Error: {response.status_code}")
        except Exception as e:
            print(f"   Error: {e}")
        
        print()
        
        # Wait a moment for potential indexing
        print("4. Waiting for indexing to potentially complete...")
        await asyncio.sleep(15)
        
        # 5. Perform various searches
        search_queries = [
            "email",
            "document",
            "test",
            "data",
            "mail.com",
            "contract"
        ]
        
        print("5. Performing example searches...")
        for query in search_queries:
            print(f"\n   Searching for: '{query}'")
            try:
                # Use the detailed search endpoint for structured results
                response = await client.get(
                    f"{BASE_URL}/api/v1/search_detailed",
                    params={"q": query, "limit": 5}
                )
                
                if response.status_code == 200:
                    search_results = response.json()
                    print(f"   Found {search_results['total_hits']} results in {search_results['execution_time_ms']}ms")
                    
                    for i, result in enumerate(search_results['results'][:3], 1):
                        print(f"     {i}. {result['file_name']} (score: {result['score']:.2f})")
                        if result['highlights']:
                            print(f"        Highlight: {result['highlights'][0][:100]}...")
                else:
                    print(f"   Search failed: {response.status_code}")
                    
            except Exception as e:
                print(f"   Search error: {e}")
        
        print()
        
        # 5b. Also demonstrate simple search endpoint
        print("5b. Testing simple search endpoint (returns file paths only)...")
        try:
            response = await client.get(
                f"{BASE_URL}/api/v1/search",
                params={"q": "test", "limit": 3}
            )
            
            if response.status_code == 200:
                file_paths = response.json()  # This is a simple list of strings
                print(f"   Simple search found {len(file_paths)} files:")
                for i, path in enumerate(file_paths[:3], 1):
                    print(f"     {i}. {path}")
            else:
                print(f"   Simple search failed: {response.status_code}")
                
        except Exception as e:
            print(f"   Simple search error: {e}")
        
        print()
        
        # 6. Search with filters
        print("6. Searching with file type filters...")
        file_types = ["pdf", "txt", "csv", "png"]
        
        for file_type in file_types:
            try:
                response = await client.get(
                    f"{BASE_URL}/api/v1/search_detailed",
                    params={"q": "test", "file_type": file_type, "limit": 3}
                )
                
                if response.status_code == 200:
                    results = response.json()
                    print(f"   {file_type.upper()} files: {results['total_hits']} results")
                else:
                    print(f"   Error searching {file_type} files: {response.status_code}")
                    
            except Exception as e:
                print(f"   Error: {e}")
        
        print()
        
        # 7. Advanced search examples
        print("7. Advanced search examples...")
        
        advanced_queries = [
            {"q": "important document", "min_score": 0.5},
            {"q": "data analysis", "limit": 20},
            {"q": "@gmail.com OR @email.com", "file_type": "csv"}
        ]
        
        for query_params in advanced_queries:
            try:
                response = await client.get(f"{BASE_URL}/api/v1/search_detailed", params=query_params)
                
                if response.status_code == 200:
                    results = response.json()
                    print(f"   Query: {query_params}")
                    print(f"   Results: {results['total_hits']} documents")
                else:
                    print(f"   Query failed: {query_params}")
                    
            except Exception as e:
                print(f"   Error: {e}")
        
        print()
        
        # 8. Get processing status
        print("8. Getting processing status...")
        try:
            response = await client.get(f"{BASE_URL}/api/v1/admin/status")
            if response.status_code == 200:
                status = response.json()
                print(f"   Indexing stats: {status['indexing_stats']['total_documents']} documents")
                print(f"   Services health: {status['services_health']}")
            else:
                print(f"   Error getting status: {response.status_code}")
        except Exception as e:
            print(f"   Error: {e}")
    
    print()
    print("=== Example Complete ===")
    print()
    print("Next steps:")
    print("• Add your documents to Google Cloud Storage")
    print("• Configure the application with your GCS bucket details")
    print("• Trigger reindexing to process your documents")
    print("• Use the search API in your applications")
    print()
    print("API Documentation: http://localhost:8000/docs")


if __name__ == "__main__":
    asyncio.run(main())
