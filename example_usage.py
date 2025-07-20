#!/usr/bin/env python3
"""
Example usage of the Burst-Fire Tee Time Booking system
"""

import asyncio
import json
from Automated_Tee_Time_Booking import BurstConfig, BurstFireTeeTimeBooker

async def main():
    """Example of how to use the burst booking system"""
    
    # Load configuration from file
    with open('config.json', 'r') as f:
        config_data = json.load(f)
    
    # Create burst configuration
    burst_cfg = config_data['burst_config']
    config = BurstConfig(
        burst_offsets=burst_cfg['burst_offsets'],
        retry_interval_ms=burst_cfg['retry_interval_ms'],
        max_retry_attempts=burst_cfg['max_retry_attempts'],
        max_concurrent_requests=burst_cfg['max_concurrent_requests'],
        booking_window_time=burst_cfg['booking_window_time'],
        cutoff_seconds=burst_cfg['cutoff_seconds']
    )
    
    # Setup credentials and targets
    credentials = config_data['credentials']
    target_times = config_data['target_times']
    
    print("Burst-Fire Tee Time Booking")
    print("=" * 40)
    print(f"Burst offsets: {config.burst_offsets}")
    print(f"Target times: {target_times}")
    print(f"Booking window: {config.booking_window_time}")
    print(f"Retry interval: {config.retry_interval_ms}ms")
    
    # Create booker instance
    booker = BurstFireTeeTimeBooker(config, credentials, target_times)
    
    try:
        print("\nInitializing session...")
        await booker.initialize_session()
        
        print("Executing burst strategy...")
        attempts = await booker.execute_burst_strategy("07-22-2025")
        
        # Report results
        successful = [a for a in attempts if a.success]
        print(f"\nResults: {len(successful)}/{len(attempts)} successful bookings")
        
        if successful:
            print("Successful bookings:")
            for attempt in successful:
                print(f"  - Offset {attempt.offset_ms:+d}ms: {attempt.response_time_ms:.2f}ms response")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        booker.cleanup()

if __name__ == "__main__":
    asyncio.run(main())