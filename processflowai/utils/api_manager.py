import asyncio
from typing import TypeVar, Callable, Awaitable, Any
from datetime import datetime, timedelta
import logging
import random

T = TypeVar('T')

logger = logging.getLogger(__name__)

class APIRateLimiter:
    def __init__(self, calls_per_minute: int = 15, max_retries: int = 3,
                 tokens_per_minute: int = 1_000_000, calls_per_day: int = 1500):
        self.calls_per_minute = calls_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.calls_per_day = calls_per_day
        self.max_retries = max_retries
        self.minute_calls = []
        self.day_calls = []
        self.minute_tokens = []
        
    async def execute(self, func: Callable[..., Awaitable[T]], *args, 
                     expected_tokens: int = 0, **kwargs) -> T:
        """
        Execute an API call with rate limiting and exponential backoff.
        
        Args:
            func: Async function to execute
            expected_tokens: Expected token usage for this call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result from the function call
        """
        retry_count = 0
        last_error = None
        
        while retry_count <= self.max_retries:
            try:
                await self._wait_if_needed(expected_tokens)
                result = await func(*args, **kwargs)
                self._record_call(expected_tokens)
                return result
                
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if "429" in str(e) or "Resource has been exhausted" in str(e):
                    # Calculate exponential backoff with jitter
                    base_wait = 2 ** retry_count
                    jitter = random.uniform(0, min(base_wait, 10))  # Cap jitter at 10 seconds
                    wait_time = base_wait + jitter
                    
                    logger.warning(f"Rate limit exceeded. Retrying in {wait_time:.2f} seconds... "
                                 f"(Attempt {retry_count} of {self.max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                    
                # For other errors, only retry if we haven't exceeded max_retries
                if retry_count <= self.max_retries:
                    logger.warning(f"Error occurred: {e}. Attempt {retry_count} of {self.max_retries}")
                    # Add a small delay for non-rate-limit errors
                    await asyncio.sleep(1)
                    continue
                    
                break
        
        # If we get here, we've exhausted all retries
        logger.error(f"Failed after {retry_count} attempts. Last error: {last_error}")
        raise last_error
    
    def _record_call(self, tokens: int = 0):
        """Record a successful API call and token usage"""
        now = datetime.now()
        
        # Record minute-based metrics
        self.minute_calls.append(now)
        if tokens > 0:
            self.minute_tokens.append((now, tokens))
            
        # Record daily calls
        self.day_calls.append(now)
        
        # Clean up old records
        self._cleanup_records()
        
        # Log current API usage
        self._log_usage()
    
    def _cleanup_records(self):
        """Clean up old records"""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)
        day_ago = now - timedelta(days=1)
        
        # Clean up minute-based records
        self.minute_calls = [call for call in self.minute_calls if call > minute_ago]
        self.minute_tokens = [(time, tokens) for time, tokens in self.minute_tokens 
                            if time > minute_ago]
        
        # Clean up daily records
        self.day_calls = [call for call in self.day_calls if call > day_ago]
    
    def _log_usage(self):
        """Log current API usage statistics"""
        minute_calls = len(self.minute_calls)
        day_calls = len(self.day_calls)
        minute_tokens = sum(tokens for _, tokens in self.minute_tokens)
        
        # Calculate usage percentages
        rpm_usage = (minute_calls / self.calls_per_minute) * 100
        tpm_usage = (minute_tokens / self.tokens_per_minute) * 100
        rpd_usage = (day_calls / self.calls_per_day) * 100
        
        # Log based on highest usage
        max_usage = max(rpm_usage, tpm_usage, rpd_usage)
        if max_usage > 90:
            logger.warning(
                f"Critical API usage: {minute_calls}/{self.calls_per_minute} RPM "
                f"({rpm_usage:.1f}%), {minute_tokens}/{self.tokens_per_minute} TPM "
                f"({tpm_usage:.1f}%), {day_calls}/{self.calls_per_day} RPD "
                f"({rpd_usage:.1f}%)"
            )
        elif max_usage > 75:
            logger.warning(
                f"High API usage: {minute_calls}/{self.calls_per_minute} RPM "
                f"({rpm_usage:.1f}%), {minute_tokens}/{self.tokens_per_minute} TPM "
                f"({tpm_usage:.1f}%), {day_calls}/{self.calls_per_day} RPD "
                f"({rpd_usage:.1f}%)"
            )
        else:
            logger.debug(
                f"Current API usage: {minute_calls}/{self.calls_per_minute} RPM, "
                f"{minute_tokens}/{self.tokens_per_minute} TPM, "
                f"{day_calls}/{self.calls_per_day} RPD"
            )
    
    async def _wait_if_needed(self, expected_tokens: int = 0):
        """Wait if we're approaching any rate limits"""
        while True:
            now = datetime.now()
            self._cleanup_records()
            
            # Check minute-based limits
            if len(self.minute_calls) >= self.calls_per_minute:
                wait_time = (self.minute_calls[0] + timedelta(minutes=1) - now).total_seconds()
                logger.info(f"RPM limit reached. Waiting {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)
                continue
                
            # Check token limit
            current_tokens = sum(tokens for _, tokens in self.minute_tokens)
            if current_tokens + expected_tokens > self.tokens_per_minute:
                wait_time = (self.minute_tokens[0][0] + timedelta(minutes=1) - now).total_seconds()
                logger.info(f"TPM limit approaching. Waiting {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)
                continue
                
            # Check daily limit
            if len(self.day_calls) >= self.calls_per_day:
                wait_time = (self.day_calls[0] + timedelta(days=1) - now).total_seconds()
                logger.error(f"Daily limit reached. Waiting {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)
                continue
                
            # If we get here, we're good to proceed
            break
