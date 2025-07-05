#!/usr/bin/env python3
"""
Performance benchmark script for the Document Search Application.
"""

import asyncio
import time
import statistics
import httpx
from concurrent.futures import ThreadPoolExecutor
import sys


async def benchmark_search(client: httpx.AsyncClient, query: str, iterations: int = 100):
    """Benchmark search performance."""
    response_times = []
    
    print(f"Benchmarking search for '{query}' ({iterations} iterations)...")
    
    for i in range(iterations):
        start_time = time.time()
        
        try:
            response = await client.get(
                "http://localhost:8000/api/v1/search",
                params={"q": query, "limit": 10}
            )
            
            if response.status_code == 200:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to ms
                response_times.append(response_time)
            else:
                print(f"Error response: {response.status_code}")
                
        except Exception as e:
            print(f"Request error: {e}")
        
        if (i + 1) % 10 == 0:
            print(f"  Completed {i + 1}/{iterations} requests")
    
    if response_times:
        avg_time = statistics.mean(response_times)
        median_time = statistics.median(response_times)
        p95_time = sorted(response_times)[int(0.95 * len(response_times))]
        min_time = min(response_times)
        max_time = max(response_times)
        
        print(f"\nResults for '{query}':")
        print(f"  Successful requests: {len(response_times)}/{iterations}")
        print(f"  Average response time: {avg_time:.1f} ms")
        print(f"  Median response time: {median_time:.1f} ms")
        print(f"  95th percentile: {p95_time:.1f} ms")
        print(f"  Min response time: {min_time:.1f} ms")
        print(f"  Max response time: {max_time:.1f} ms")
        print(f"  Requests per second: {1000 / avg_time:.1f}")
        
        return {
            "query": query,
            "successful_requests": len(response_times),
            "total_requests": iterations,
            "avg_time": avg_time,
            "median_time": median_time,
            "p95_time": p95_time,
            "min_time": min_time,
            "max_time": max_time,
            "rps": 1000 / avg_time
        }
    
    return None


async def concurrent_benchmark(concurrent_users: int = 10, requests_per_user: int = 10):
    """Benchmark concurrent search performance."""
    print(f"\nConcurrent benchmark: {concurrent_users} users, {requests_per_user} requests each")
    
    async def user_session(user_id: int):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response_times = []
            
            for i in range(requests_per_user):
                query = f"test user{user_id % 5}"  # Vary queries slightly
                start_time = time.time()
                
                try:
                    response = await client.get(
                        "http://localhost:8000/api/v1/search",
                        params={"q": query, "limit": 5}
                    )
                    
                    if response.status_code == 200:
                        end_time = time.time()
                        response_time = (end_time - start_time) * 1000
                        response_times.append(response_time)
                        
                except Exception as e:
                    print(f"User {user_id} error: {e}")
            
            return response_times
    
    # Create tasks for concurrent users
    start_time = time.time()
    tasks = [user_session(i) for i in range(concurrent_users)]
    results = await asyncio.gather(*tasks)
    end_time = time.time()
    
    # Aggregate results
    all_response_times = []
    for user_times in results:
        all_response_times.extend(user_times)
    
    total_duration = end_time - start_time
    total_requests = len(all_response_times)
    
    if all_response_times:
        avg_time = statistics.mean(all_response_times)
        median_time = statistics.median(all_response_times)
        p95_time = sorted(all_response_times)[int(0.95 * len(all_response_times))]
        
        print(f"\nConcurrent benchmark results:")
        print(f"  Total duration: {total_duration:.1f} seconds")
        print(f"  Total successful requests: {total_requests}")
        print(f"  Overall throughput: {total_requests / total_duration:.1f} requests/second")
        print(f"  Average response time: {avg_time:.1f} ms")
        print(f"  Median response time: {median_time:.1f} ms")
        print(f"  95th percentile: {p95_time:.1f} ms")


async def main():
    """Main benchmark function."""
    print("=== Document Search Performance Benchmark ===\n")
    
    # Check if the application is running
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8000/api/v1/health")
            if response.status_code not in [200, 503]:
                print("Application not responding correctly.")
                return
    except Exception as e:
        print(f"Cannot connect to application: {e}")
        print("Make sure the application is running on localhost:8000")
        return
    
    # Single-user benchmarks
    test_queries = [
        "email",
        "document test",
        "data analysis",
        "important contract",
        "user@domain.com"
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        benchmark_results = []
        
        for query in test_queries:
            result = await benchmark_search(client, query, iterations=50)
            if result:
                benchmark_results.append(result)
            print()
        
        # Summary of single-user tests
        if benchmark_results:
            avg_times = [r["avg_time"] for r in benchmark_results]
            overall_avg = statistics.mean(avg_times)
            best_rps = max(r["rps"] for r in benchmark_results)
            
            print("=== Single-User Benchmark Summary ===")
            print(f"Overall average response time: {overall_avg:.1f} ms")
            print(f"Best requests per second: {best_rps:.1f}")
            print(f"Meets <1s requirement: {'✓' if overall_avg < 1000 else '✗'}")
    
    # Concurrent user benchmark
    await concurrent_benchmark(concurrent_users=20, requests_per_user=5)
    
    print("\n=== Benchmark Complete ===")
    print("\nPerformance Requirements Check:")
    print("• Response time < 1 second: Check individual results above")
    print("• Support 100+ concurrent users: Scale test with more users if needed")
    print("• Handle 2000+ documents: Check with your actual document count")


if __name__ == "__main__":
    asyncio.run(main())
