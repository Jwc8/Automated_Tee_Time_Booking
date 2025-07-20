from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException

import schedule
import asyncio
import aiohttp
import logging
import time
import datetime
from datetime import date, datetime as dt
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import sys


@dataclass
class BurstConfig:
    """Configuration for burst-fire booking strategy"""
    # Timing offsets in milliseconds relative to booking window
    burst_offsets: List[int] = None
    # Retry configuration for 400 errors
    retry_interval_ms: int = 35  # 30-50ms as specified
    max_retry_attempts: int = 50
    # Parallel execution settings
    max_concurrent_requests: int = 10
    # Timing precision
    booking_window_time: str = "23:00:00"  # When bookings open
    cutoff_seconds: int = 30  # Stop trying after this many seconds
    
    def __post_init__(self):
        if self.burst_offsets is None:
            # Default burst strategy: T-70ms, T-40ms, T-10ms, T+10ms, T+40ms, T+70ms
            self.burst_offsets = [-70, -40, -10, 10, 40, 70]

@dataclass
class BookingAttempt:
    """Represents a single booking attempt with timing data"""
    timestamp: float
    offset_ms: int
    response_time_ms: float
    status_code: Optional[int] = None
    success: bool = False
    error_message: Optional[str] = None
    round_trip_latency_ms: Optional[float] = None

class EnhancedLogger:
    """Enhanced logging with millisecond precision and performance tracking"""
    
    def __init__(self, log_level=logging.INFO):
        self.logger = logging.getLogger('TeeTimeBooking')
        self.logger.setLevel(log_level)
        
        # Create formatter with millisecond precision
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        file_handler = logging.FileHandler('tee_time_booking.log')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
    
    def log_attempt(self, attempt: BookingAttempt):
        """Log a booking attempt with full timing details"""
        self.logger.info(
            f"Attempt at offset {attempt.offset_ms:+d}ms: "
            f"Status={attempt.status_code}, "
            f"ResponseTime={attempt.response_time_ms:.2f}ms, "
            f"RTT={attempt.round_trip_latency_ms:.2f}ms, "
            f"Success={attempt.success}"
        )
        
        if attempt.error_message:
            self.logger.warning(f"Error: {attempt.error_message}")
    
    def log_burst_summary(self, attempts: List[BookingAttempt]):
        """Log summary of burst attempts"""
        successful = [a for a in attempts if a.success]
        failed = [a for a in attempts if not a.success]
        
        self.logger.info(f"Burst Summary: {len(successful)} successful, {len(failed)} failed")
        
        if successful:
            fastest = min(successful, key=lambda x: x.response_time_ms)
            self.logger.info(f"Fastest successful: {fastest.response_time_ms:.2f}ms at offset {fastest.offset_ms:+d}ms")
        
        # Log timing statistics
        response_times = [a.response_time_ms for a in attempts if a.response_time_ms]
        if response_times:
            avg_response = sum(response_times) / len(response_times)
            self.logger.info(f"Average response time: {avg_response:.2f}ms")


class BurstFireTeeTimeBooker:
    """Enhanced tee time booker with burst-fire strategy and parallel execution"""
    
    def __init__(self, config: BurstConfig, credentials: Dict[str, str], target_times: List[str] = None):
        self.config = config
        self.credentials = credentials
        self.target_times = target_times or ["7:33", "7:42"]  # High-demand slots
        self.logger = EnhancedLogger()
        self.driver = None
        self.session_cookies = None
        self.booking_url = None
        
    async def initialize_session(self):
        """Initialize Selenium session and extract booking details"""
        self.logger.logger.info("Initializing Selenium session...")
        
        # Initialize Chrome driver with optimized options
        options = webdriver.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-logging")
        options.add_argument("--silent")
        
        self.driver = webdriver.Chrome(options=options)
        
        try:
            # Login and navigate to booking page
            await self._login_and_navigate()
            
            # Extract cookies and booking URL for API calls
            self.session_cookies = self.driver.get_cookies()
            self.booking_url = self._extract_booking_api_url()
            
            self.logger.logger.info("Session initialized successfully")
            
        except Exception as e:
            self.logger.logger.error(f"Failed to initialize session: {e}")
            if self.driver:
                self.driver.quit()
            raise
    
    async def _login_and_navigate(self):
        """Handle login and navigation to booking page"""
        self.driver.get("https://golf.com")
        
        # Wait for page load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        
        # Login
        username_field = self.driver.find_element(By.NAME, "username")
        password_field = self.driver.find_element(By.NAME, "password")
        
        username_field.send_keys(self.credentials["username"])
        password_field.send_keys(self.credentials["password"])
        
        sign_in_button = self.driver.find_element(By.NAME, "login_button")
        sign_in_button.click()
        
        # Wait for login to complete
        time.sleep(2)
        
        # Navigate to booking section
        try:
            navbar_toggle = self.driver.find_element(By.CLASS_NAME, "navbar-toggle")
            navbar_toggle.click()
            self.driver.refresh()
        except Exception:
            pass  # Menu might not be needed on all sites
    
    def _extract_booking_api_url(self) -> str:
        """Extract the actual booking API URL by analyzing network requests"""
        # This would normally require selenium-wire or monitoring network traffic
        # For now, we'll use a common booking endpoint pattern
        current_url = self.driver.current_url
        base_url = current_url.split('/')[0:3]  # protocol + domain
        return f"{''.join(base_url)}/api/booking/book"
    
    async def execute_burst_strategy(self, target_date: str) -> List[BookingAttempt]:
        """Execute the burst-fire booking strategy"""
        self.logger.logger.info(f"Preparing burst strategy for {target_date}")
        
        # Calculate precise timing
        booking_time = self._calculate_booking_time()
        
        # Prepare all booking requests
        booking_tasks = []
        for offset_ms in self.config.burst_offsets:
            for tee_time in self.target_times:
                task = self._schedule_booking_attempt(
                    booking_time, offset_ms, target_date, tee_time
                )
                booking_tasks.append(task)
        
        self.logger.logger.info(f"Scheduled {len(booking_tasks)} parallel booking attempts")
        
        # Execute all requests in parallel
        start_time = time.time()
        results = await asyncio.gather(*booking_tasks, return_exceptions=True)
        total_time = (time.time() - start_time) * 1000
        
        # Process results
        attempts = [r for r in results if isinstance(r, BookingAttempt)]
        exceptions = [r for r in results if isinstance(r, Exception)]
        
        if exceptions:
            self.logger.logger.warning(f"Encountered {len(exceptions)} exceptions during burst")
        
        self.logger.log_burst_summary(attempts)
        self.logger.logger.info(f"Total burst execution time: {total_time:.2f}ms")
        
        return attempts
    
    def _calculate_booking_time(self) -> float:
        """Calculate the exact timestamp for booking window"""
        today = dt.now()
        booking_time_parts = self.config.booking_window_time.split(':')
        
        booking_datetime = today.replace(
            hour=int(booking_time_parts[0]),
            minute=int(booking_time_parts[1]),
            second=int(booking_time_parts[2]),
            microsecond=0
        )
        
        return booking_datetime.timestamp()
    
    async def _schedule_booking_attempt(self, base_time: float, offset_ms: int, 
                                      target_date: str, tee_time: str) -> BookingAttempt:
        """Schedule and execute a single booking attempt"""
        # Calculate exact execution time
        execution_time = base_time + (offset_ms / 1000.0)
        
        # Wait until execution time
        current_time = time.time()
        wait_time = execution_time - current_time
        
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        
        # Execute booking attempt
        attempt_start = time.time()
        
        attempt = BookingAttempt(
            timestamp=attempt_start,
            offset_ms=offset_ms,
            response_time_ms=0.0
        )
        
        try:
            # Perform the actual booking request
            success, status_code, error_msg = await self._make_booking_request(target_date, tee_time)
            
            response_time = (time.time() - attempt_start) * 1000
            
            attempt.response_time_ms = response_time
            attempt.status_code = status_code
            attempt.success = success
            attempt.error_message = error_msg
            attempt.round_trip_latency_ms = response_time  # Simplified for now
            
            # Implement smart retry logic for 400 errors
            if status_code == 400 and "booking not open" in (error_msg or "").lower():
                self.logger.logger.info(f"Received 400 'booking not open' at offset {offset_ms}ms, retrying...")
                success, final_status, final_error = await self._smart_retry(target_date, tee_time, attempt_start)
                attempt.success = success
                attempt.status_code = final_status
                attempt.error_message = final_error
            
            self.logger.log_attempt(attempt)
            
        except Exception as e:
            attempt.error_message = str(e)
            self.logger.logger.error(f"Exception in booking attempt: {e}")
        
        return attempt
    
    async def _make_booking_request(self, target_date: str, tee_time: str) -> Tuple[bool, int, Optional[str]]:
        """Make the actual HTTP booking request"""
        
        # Convert cookies to aiohttp format
        cookie_dict = {}
        if self.session_cookies:
            for cookie in self.session_cookies:
                cookie_dict[cookie['name']] = cookie['value']
        
        # Prepare booking payload
        booking_data = {
            "date": target_date,
            "time": tee_time,
            "players": 1,
            "course": "default"  # This would be configured based on actual site
        }
        
        async with aiohttp.ClientSession(cookies=cookie_dict) as session:
            try:
                async with session.post(
                    self.booking_url,
                    json=booking_data,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    
                    response_text = await response.text()
                    
                    if response.status == 200:
                        return True, response.status, None
                    else:
                        return False, response.status, response_text
                        
            except aiohttp.ClientError as e:
                return False, 0, str(e)
    
    async def _smart_retry(self, target_date: str, tee_time: str, initial_start: float) -> Tuple[bool, int, Optional[str]]:
        """Implement smart retry logic for 400 'booking not open' errors"""
        
        retry_count = 0
        cutoff_time = initial_start + self.config.cutoff_seconds
        
        while retry_count < self.config.max_retry_attempts and time.time() < cutoff_time:
            await asyncio.sleep(self.config.retry_interval_ms / 1000.0)
            
            success, status_code, error_msg = await self._make_booking_request(target_date, tee_time)
            retry_count += 1
            
            # Success or different error - stop retrying
            if success or status_code != 400:
                return success, status_code, error_msg
            
            # Continue retrying if still getting 400 "booking not open"
            if "booking not open" not in (error_msg or "").lower():
                return success, status_code, error_msg
        
        return False, 400, f"Max retries ({retry_count}) reached or cutoff time exceeded"
    
    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            self.driver = None


async def run_burst_booking(config_file: str = "config.json"):
    """Main function to execute burst-fire booking strategy"""
    
    try:
        # Load configuration from file
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        # Configuration
        burst_cfg = config_data.get('burst_config', {})
        config = BurstConfig(
            burst_offsets=burst_cfg.get('burst_offsets', [-70, -40, -10, 10, 40, 70]),
            retry_interval_ms=burst_cfg.get('retry_interval_ms', 35),
            max_retry_attempts=burst_cfg.get('max_retry_attempts', 50),
            booking_window_time=burst_cfg.get('booking_window_time', "23:00:00"),
            cutoff_seconds=burst_cfg.get('cutoff_seconds', 30)
        )
        
        # Credentials
        credentials = config_data.get('credentials', {
            "username": "USERNAME",
            "password": "PASSWORD"
        })
        
        # Target times
        target_times = config_data.get('target_times', ["7:33", "7:42"])
        
        # Booking settings
        booking_settings = config_data.get('booking_settings', {})
        days_in_advance = booking_settings.get('days_in_advance', 2)
        
    except FileNotFoundError:
        print(f"Configuration file {config_file} not found. Using default settings.")
        # Use default configuration
        config = BurstConfig()
        credentials = {"username": "USERNAME", "password": "PASSWORD"}
        target_times = ["7:33", "7:42"]
        days_in_advance = 2
    except json.JSONDecodeError:
        print(f"Error parsing {config_file}. Using default settings.")
        config = BurstConfig()
        credentials = {"username": "USERNAME", "password": "PASSWORD"}
        target_times = ["7:33", "7:42"]
        days_in_advance = 2
    
    # Calculate target booking date
    target_date = (date.today() + datetime.timedelta(days=days_in_advance)).strftime("%m-%d-%Y")
    
    booker = BurstFireTeeTimeBooker(config, credentials, target_times)
    
    try:
        # Initialize session
        await booker.initialize_session()
        
        # Execute burst strategy
        attempts = await booker.execute_burst_strategy(target_date)
        
        # Check for successful bookings
        successful_attempts = [a for a in attempts if a.success]
        
        if successful_attempts:
            booker.logger.logger.info(f"SUCCESS! Secured {len(successful_attempts)} tee time(s)")
            for attempt in successful_attempts:
                booker.logger.logger.info(f"  - Booked at offset {attempt.offset_ms:+d}ms")
        else:
            booker.logger.logger.warning("No successful bookings in this burst")
        
        return successful_attempts
        
    except Exception as e:
        booker.logger.logger.error(f"Fatal error during booking: {e}")
        raise
    finally:
        booker.cleanup()

def book_tee_time_automated(config_file: str = "config.json"):
    """Legacy function wrapper for backward compatibility"""
    booker = None
    try:
        # Run the async booking process
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(run_burst_booking(config_file))
        return result
        
    except Exception as e:
        print(f"Booking failed: {e}")
        return None

def schedule_burst_booking(config_file: str = "config.json"):
    """Schedule the burst booking to run at the optimal time"""
    
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        schedule_cfg = config_data.get('schedule', {})
        run_time = schedule_cfg.get('run_time', "22:59:55")
    except:
        run_time = "22:59:55"
    
    # Schedule to run just before the booking window opens
    schedule.every().day.at(run_time).do(lambda: book_tee_time_automated(config_file))
    
    print("Burst-fire tee time booking scheduled")
    print(f"Run time: {run_time} daily")
    print("Use --test to run immediately or check logs for results")

# Main execution
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Automated Tee Time Booking with Burst-Fire Strategy")
    parser.add_argument("--test", action="store_true", help="Run a test booking attempt now")
    parser.add_argument("--schedule", action="store_true", help="Run scheduled booking (default)")
    parser.add_argument("--config", type=str, default="config.json", help="Path to custom configuration file")
    
    args = parser.parse_args()
    
    if args.test:
        print("Running test booking...")
        asyncio.run(run_burst_booking(args.config))
    else:
        # Default: run scheduled booking
        schedule_burst_booking(args.config)
        
        print("Scheduler started. Press Ctrl+C to exit.")
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nScheduler stopped.")