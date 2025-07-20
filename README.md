# Automated Tee Time Booking with Burst-Fire Strategy ⛳️

This program provides an advanced automated tee time booking system with burst-fire strategy for maximum competitive advantage. It's designed to handle high-demand booking scenarios with millisecond precision timing and parallel execution.

## 🚀 New Features

### Burst-Fire Strategy
- **Precise Millisecond Timing**: Execute multiple booking attempts at precise offsets around the booking window
- **Default Strategy**: T-70ms, T-40ms, T-10ms, T+10ms, T+40ms, T+70ms
- **Configurable Offsets**: Easily customize timing based on your network conditions

### Parallel Execution
- **True Parallelization**: Send all requests simultaneously using asyncio.gather()
- **Multiple Time Slots**: Book multiple preferred times (e.g., 7:33, 7:42) in parallel
- **Eliminated Delays**: No more sequential 25ms delays that waste precious time

### Smart Retry Logic
- **400 Error Handling**: Automatically retry when server returns "booking not open yet"
- **Intelligent Timing**: 30-50ms retry intervals with cutoff protection
- **Persistent Attempts**: Continue retrying until success or timeout

### Enhanced Logging
- **Millisecond Precision**: All timestamps include millisecond accuracy
- **Performance Tracking**: Round-trip latency and response time monitoring
- **Burst Analytics**: Summary statistics for timing optimization

### Easy Configuration
- **JSON Configuration**: All parameters easily adjustable via config.json
- **Fine-tuning Support**: Optimize based on network conditions and server behavior
- **Multiple Execution Modes**: Test mode and scheduled mode

## 📦 Installation

```bash
pip install -r requirements.txt
```

## ⚙️ Configuration

Edit `config.json` to customize your booking strategy:

```json
{
  "burst_config": {
    "burst_offsets": [-70, -40, -10, 10, 40, 70],
    "retry_interval_ms": 35,
    "max_retry_attempts": 50,
    "booking_window_time": "23:00:00",
    "cutoff_seconds": 30
  },
  "target_times": ["7:33", "7:42"],
  "credentials": {
    "username": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD"
  }
}
```

## 🎯 Usage

### Scheduled Booking (Recommended)
```bash
python3 Automated_Tee_Time_Booking.py --schedule
```
Runs automatically at 22:59:55 daily (5 seconds before booking window opens)

### Test Mode
```bash
python3 Automated_Tee_Time_Booking.py --test
```
Execute a test booking immediately to validate configuration

### Custom Configuration
```bash
python3 Automated_Tee_Time_Booking.py --config custom_config.json
```

### Programmatic Usage
```python
import asyncio
from Automated_Tee_Time_Booking import BurstConfig, BurstFireTeeTimeBooker

config = BurstConfig(burst_offsets=[-50, 0, 50])
credentials = {"username": "user", "password": "pass"}
booker = BurstFireTeeTimeBooker(config, credentials, ["7:33"])

# Run burst booking
attempts = await booker.execute_burst_strategy("07-22-2025")
```

## 📊 Performance Metrics

The system provides detailed timing analytics:
- **Timing Accuracy**: Sub-millisecond precision (typically <1ms error)
- **Response Times**: Track individual request performance
- **Success Rates**: Monitor booking success across different offsets
- **Network Latency**: Round-trip time measurements

## ⚠️ Ethical Considerations

This tool demonstrates advanced web automation techniques but should be used responsibly:
- ⚠️ **High-demand courses**: Consider the fairness impact on other golfers
- 🎓 **Educational use**: Great for learning Selenium and async programming
- 🏌️ **Personal use**: Intended for individual booking assistance
- 📊 **Testing**: Excellent for performance and timing analysis

## 🛠️ Technical Details

### Architecture
- **Selenium WebDriver**: Login and session management
- **AsyncIO**: Parallel request execution
- **AioHTTP**: High-performance HTTP requests
- **Precision Timing**: Microsecond-level scheduling

### Timing Strategy
1. **Pre-execution**: Initialize session 5 seconds before window
2. **Burst Window**: Execute all offsets within ~140ms total
3. **Retry Logic**: Intelligent 400 error handling
4. **Cutoff Protection**: Stop attempts after 30 seconds

### Error Handling
- Network timeouts and connection errors
- Server-side rate limiting
- Booking window timing variations
- Session authentication issues

## 📝 Customization

You'll need to adapt the web element selectors based on your golf course's website structure. Key areas to modify:

1. **Login Elements**: Update username/password field selectors
2. **Booking API**: Modify the booking request payload
3. **Time Selection**: Adjust time slot selectors
4. **Date Handling**: Customize date format and selection

## 🔧 Development

### Running Tests
```bash
python3 test_burst_booking.py
```

### Adding New Features
The modular design makes it easy to extend:
- Custom timing strategies
- Additional retry policies  
- Enhanced analytics
- Multiple course support

## 📄 Requirements

- Python 3.8+
- Chrome/Chromium browser
- Network connection with stable latency
- Valid golf course website credentials

---

**Note**: This tool showcases advanced automation techniques. Please use responsibly and in accordance with your golf course's terms of service. 🏌️‍♂️⛳️