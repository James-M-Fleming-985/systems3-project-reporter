import asyncio
from typing import Dict, List, Optional, Tuple
import logging
import io

from playwright.async_api import (
    async_playwright,
    Browser,
    Page,
    TimeoutError as PlaywrightTimeout
)
from PIL import Image

logger = logging.getLogger(__name__)


class ScreenshotService:
    """Service for capturing screenshots using Playwright."""
    
    def __init__(self):
        self.default_resolution = (1920, 1080)
        self.timeout = 5000  # milliseconds for Playwright
        self._browser: Optional[Browser] = None
        self._playwright = None
        
    async def _ensure_browser(self) -> Browser:
        """Ensure browser is initialized."""
        if self._browser is None or not self._browser.is_connected():
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )
        return self._browser
    
    async def capture_screenshot_async(
        self,
        url: str,
        hide_navigation: bool = False,
        resolution: Optional[Tuple[int, int]] = None,
        wait_for_selector: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
        cookies: Optional[List[Dict]] = None
    ) -> bytes:
        """
        Asynchronously capture a screenshot of the specified URL.
        
        Args:
            url: The URL to capture
            hide_navigation: Whether to hide navigation elements
            resolution: Custom resolution (width, height),
                defaults to 1920x1080
            wait_for_selector: CSS selector to wait for before capturing
            extra_headers: Additional HTTP headers to send with the request
            cookies: List of cookie dicts to set before navigation
            
        Returns:
            PNG image data as bytes
            
        Raises:
            PlaywrightTimeout: If the page takes too long to load
        """
        if resolution is None:
            resolution = self.default_resolution
            
        browser = await self._ensure_browser()
        page = None
        
        try:
            # Create new browser context with cookies if provided
            context = await browser.new_context(
                viewport={'width': resolution[0], 'height': resolution[1]}
            )
            
            # Set cookies if provided (for authentication)
            if cookies:
                await context.add_cookies(cookies)
                logger.info(f"Set {len(cookies)} cookies for authentication")
            
            # Create new page in this context
            page = await context.new_page()
            
            # Set extra headers if provided (e.g., X-Project-Code for project context)
            if extra_headers:
                await page.set_extra_http_headers(extra_headers)
                logger.info(f"Set extra headers: {extra_headers}")
            
            # Navigate to URL (metric data now passed as query param, not localStorage)
            await page.goto(
                url, wait_until='networkidle', timeout=self.timeout
            )
            
            # Special handling for metric trend charts - wait for Plotly to render
            if '/metrics/trend/' in url:
                logger.info("Detected metric trend chart, waiting for Plotly...")
                try:
                    # Wait for Plotly to signal completion via data-plotly-ready attribute
                    await page.wait_for_selector('body[data-plotly-ready="true"]', timeout=10000)
                    logger.info("✅ Plotly chart rendered (detected via data-plotly-ready)")
                except Exception as e:
                    logger.warning(f"Plotly ready signal timeout, capturing anyway: {e}")
                    # Fallback to small delay if signal doesn't arrive
                    await page.wait_for_timeout(2000)
            
            # Wait for Plotly charts on Gantt and other chart pages
            if '/gantt' in url or '/dashboard' in url or '/milestones' in url:
                logger.info("Waiting for Plotly charts to render...")
                try:
                    # Wait for any Plotly chart container to be populated
                    await page.wait_for_function(
                        """() => {
                            // Check if Plotly exists and has rendered charts
                            const plotDivs = document.querySelectorAll('.js-plotly-plot');
                            if (plotDivs.length > 0) {
                                // Check if at least one plot has data
                                for (const div of plotDivs) {
                                    if (div.data && div.data.length > 0) {
                                        return true;
                                    }
                                }
                            }
                            // Also check for SVG content in common chart containers
                            const ganttChart = document.getElementById('ganttChart');
                            if (ganttChart && ganttChart.querySelector('svg')) {
                                return true;
                            }
                            return false;
                        }""",
                        timeout=8000
                    )
                    logger.info("✅ Plotly charts detected as rendered")
                    # Give a bit more time for animations to complete
                    await page.wait_for_timeout(500)
                except Exception as e:
                    logger.warning(f"Plotly chart detection timeout: {e}")
                    # Fallback to longer delay
                    await page.wait_for_timeout(3000)
            
            # Wait for specific selector if provided
            if wait_for_selector:
                await page.wait_for_selector(
                    wait_for_selector, timeout=self.timeout
                )
            
            # Hide navigation if requested
            if hide_navigation:
                await self._hide_navigation_elements(page)
            
            # Additional wait for charts/dynamic content to render
            await page.wait_for_timeout(500)
            
            # Take screenshot
            screenshot = await page.screenshot(type='png', full_page=False)
            return screenshot
            
        except PlaywrightTimeout:
            logger.warning(f"Timeout capturing screenshot for {url}")
            return self._create_placeholder_image(resolution)
        except Exception as e:
            logger.error(f"Error capturing screenshot for {url}: {e}")
            return self._create_placeholder_image(resolution)
        finally:
            if page:
                await page.close()
            if 'context' in locals() and context:
                await context.close()
    
    def capture_screenshot(
        self,
        url: str,
        hide_navigation: bool = False,
        resolution: Optional[Tuple[int, int]] = None,
        wait_for_selector: Optional[str] = None
    ) -> bytes:
        """
        Synchronous wrapper for capture_screenshot_async.
        
        Args:
            url: The URL to capture
            hide_navigation: Whether to hide navigation elements
            resolution: Custom resolution (width, height),
                defaults to 1920x1080
            wait_for_selector: CSS selector to wait for before capturing
            
        Returns:
            PNG image data as bytes
        """
        return asyncio.run(
            self.capture_screenshot_async(
                url, hide_navigation, resolution, wait_for_selector
            )
        )
    
    async def capture_screenshots_parallel_async(
        self,
        urls: List[str],
        hide_navigation: bool = False,
        resolution: Optional[Tuple[int, int]] = None
    ) -> Dict[str, bytes]:
        """
        Asynchronously capture screenshots of multiple URLs in parallel.
        
        Args:
            urls: List of URLs to capture
            hide_navigation: Whether to hide navigation elements
            resolution: Custom resolution (width, height)
            
        Returns:
            Dictionary mapping URLs to PNG image data
        """
        # Create tasks for all URLs
        tasks = [
            self.capture_screenshot_async(url, hide_navigation, resolution)
            for url in urls
        ]
        
        # Run all tasks concurrently
        screenshots = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Build results dictionary
        results = {}
        for url, screenshot in zip(urls, screenshots):
            if isinstance(screenshot, Exception):
                logger.error(f"Error capturing {url}: {screenshot}")
                resolution_to_use = resolution or self.default_resolution
                results[url] = self._create_placeholder_image(
                    resolution_to_use
                )
            else:
                results[url] = screenshot
                
        return results
    
    def capture_screenshots_parallel(
        self,
        urls: List[str],
        hide_navigation: bool = False,
        resolution: Optional[Tuple[int, int]] = None
    ) -> Dict[str, bytes]:
        """
        Synchronous wrapper for capture_screenshots_parallel_async.
        
        Args:
            urls: List of URLs to capture
            hide_navigation: Whether to hide navigation elements
            resolution: Custom resolution (width, height)
            
        Returns:
            Dictionary mapping URLs to PNG image data
        """
        return asyncio.run(
            self.capture_screenshots_parallel_async(
                urls, hide_navigation, resolution
            )
        )
    
    async def _hide_navigation_elements(self, page: Page):
        """Hide navigation elements using JavaScript."""
        hide_script = """
        // Hide common navigation elements
        const selectors = [
            'nav', 'header', '.navigation', '.navbar',
            '#navigation', '#header', '.header', '.nav',
            '[role="navigation"]', '.menu', '#menu'
        ];
        
        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.style.display = 'none';
            });
        });
        """
        await page.evaluate(hide_script)
    
    def _create_placeholder_image(self, resolution: Tuple[int, int]) -> bytes:
        """Create a placeholder image for failed captures."""
        # Create a gray placeholder image with text
        img = Image.new('RGB', resolution, color='lightgray')
        
        # Convert to PNG bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()
    
    async def close(self):
        """Close browser and cleanup resources."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
    
    def __del__(self):
        """Cleanup on deletion."""
        if self._browser or self._playwright:
            try:
                asyncio.run(self.close())
            except Exception:
                pass


# Additional helper functions for test compatibility
def capture_dashboard_screenshot(url: str, **kwargs) -> bytes:
    """Convenience function to capture a dashboard screenshot."""
    service = ScreenshotService()
    return service.capture_screenshot(url, **kwargs)


def capture_multiple_screenshots(
    urls: List[str], **kwargs
) -> Dict[str, bytes]:
    """Convenience function to capture multiple screenshots."""
    service = ScreenshotService()
    return service.capture_screenshots_parallel(urls, **kwargs)
    service = ScreenshotService()
    return service.capture_screenshots_parallel(urls, **kwargs)
