#!/usr/bin/env python3
"""
Test script for the Burst-Fire Tee Time Booking system
This script validates the timing, parallel execution, and retry logic
"""

import asyncio
import time
from datetime import datetime
import sys
import os

# Add the current directory to path so we can import our module
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Automated_Tee_Time_Booking import BurstConfig, BurstFireTeeTimeBooker, EnhancedLogger, BookingAttempt

class MockBooker(BurstFireTeeTimeBooker):
    """Mock version of the booker for testing without actual web requests"""
    
    def __init__(self, config: BurstConfig):
        self.config = config
        self.logger = EnhancedLogger()
        self.mock_responses = {}
        self.target_times = ["7:33", "7:42"]  # Add missing attribute
        
    async def initialize_session(self):
        """Mock session initialization"""
        self.logger.logger.info("Mock session initialized")
        
    async def _make_booking_request(self, target_date: str, tee_time: str):
        """Mock booking request with simulated response times"""
        # Simulate network latency
        await asyncio.sleep(0.01 + (time.time() % 0.005))  # 10-15ms simulated latency
        
        # Simulate different responses based on timing
        current_ms = int(time.time() * 1000) % 1000
        
        if current_ms < 100:  # Early requests get 400
            return False, 400, "booking not open yet"
        elif current_ms < 200:  # Some succeed
            return True, 200, None
        else:  # Later requests might fail due to capacity
            return False, 409, "no availability"
    
    def cleanup(self):
        """Mock cleanup"""
        pass

async def test_timing_precision():
    """Test the timing precision of burst offsets"""
    print("\n=== Testing Timing Precision ===")
    
    config = BurstConfig(burst_offsets=[-50, -25, 0, 25, 50])
    booker = MockBooker(config)
    
    # Record when each offset actually executes
    base_time = time.time() + 0.5  # 500ms from now
    execution_times = []
    
    async def timed_execution(offset_ms):
        execution_time = base_time + (offset_ms / 1000.0)
        wait_time = execution_time - time.time()
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        actual_time = time.time()
        return offset_ms, actual_time
    
    # Execute all timing offsets in parallel
    tasks = [timed_execution(offset) for offset in config.burst_offsets]
    results = await asyncio.gather(*tasks)
    
    # Analyze timing accuracy
    print(f"Base time: {base_time:.6f}")
    for offset_ms, actual_time in results:
        expected_time = base_time + (offset_ms / 1000.0)
        timing_error = (actual_time - expected_time) * 1000  # Convert to ms
        print(f"Offset {offset_ms:+3d}ms: Expected {expected_time:.6f}, Actual {actual_time:.6f}, Error {timing_error:+6.2f}ms")

async def test_parallel_execution():
    """Test parallel execution capabilities"""
    print("\n=== Testing Parallel Execution ===")
    
    config = BurstConfig(burst_offsets=[-30, -10, 10, 30])
    booker = MockBooker(config)
    
    # Test parallel booking attempts
    start_time = time.time()
    
    tasks = []
    for offset in config.burst_offsets:
        for tee_time in ["7:33", "7:42"]:
            task = booker._schedule_booking_attempt(start_time + 0.1, offset, "07-22-2025", tee_time)
            tasks.append(task)
    
    attempts = await asyncio.gather(*tasks)
    
    total_time = (time.time() - start_time) * 1000
    print(f"Executed {len(attempts)} requests in {total_time:.2f}ms")
    
    # Analyze results
    successful = [a for a in attempts if a.success]
    failed = [a for a in attempts if not a.success]
    
    print(f"Successful: {len(successful)}, Failed: {len(failed)}")
    
    if attempts:
        response_times = [a.response_time_ms for a in attempts]
        avg_response = sum(response_times) / len(response_times)
        print(f"Average response time: {avg_response:.2f}ms")

async def test_retry_logic():
    """Test the smart retry logic for 400 errors"""
    print("\n=== Testing Retry Logic ===")
    
    config = BurstConfig(retry_interval_ms=20, max_retry_attempts=5)
    booker = MockBooker(config)
    
    # Simulate a retry scenario
    start_time = time.time()
    success, status_code, error_msg = await booker._smart_retry("07-22-2025", "7:33", start_time)
    
    retry_time = (time.time() - start_time) * 1000
    print(f"Retry logic completed in {retry_time:.2f}ms")
    print(f"Final result: Success={success}, Status={status_code}, Error={error_msg}")

async def test_burst_strategy():
    """Test the complete burst strategy"""
    print("\n=== Testing Complete Burst Strategy ===")
    
    config = BurstConfig(
        burst_offsets=[-20, -10, 0, 10, 20],
        retry_interval_ms=25,
        max_retry_attempts=3
    )
    
    credentials = {"username": "test", "password": "test"}
    booker = MockBooker(config)
    
    # Override the timing calculation to execute immediately
    original_calc = booker._calculate_booking_time
    booker._calculate_booking_time = lambda: time.time() + 0.1  # 100ms from now
    
    # Execute a burst
    attempts = await booker.execute_burst_strategy("07-22-2025")
    
    # Summary
    successful = [a for a in attempts if a.success]
    print(f"Burst completed: {len(successful)}/{len(attempts)} successful")

def run_all_tests():
    """Run all test functions"""
    print("Burst-Fire Tee Time Booking - Test Suite")
    print("=" * 50)
    
    async def run_tests():
        await test_timing_precision()
        await test_parallel_execution() 
        await test_retry_logic()
        await test_burst_strategy()
        print("\n=== All Tests Completed ===")
    
    # Run the tests
    asyncio.run(run_tests())

if __name__ == "__main__":
    run_all_tests()